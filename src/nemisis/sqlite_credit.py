"""Trusted SQLite crash supervisor and worker.

The kernel: seed a database, spawn the handler in its own process group, pause at every store
commit, kill at the capsule's boundary, replay in a fresh worker, and probe durable state through
read-only connections. Everything about *which* database, store, event, and rule is a
:class:`nemisis.scenario.Scenario`; the kernel reads it and never special-cases one.
"""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import inspect
import json
import os
import platform
import signal
import socket
import sqlite3
import subprocess
import sys
import threading
import uuid
from collections.abc import Callable, Mapping
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from time import monotonic
from typing import cast
from urllib.parse import quote

from nemisis.crash_models import (
    MAX_SWEEP_COMMITS,
    AnchorBinding,
    AnchorResolutionStatus,
    AttemptReceipt,
    CrashObservation,
    CreditSnapshot,
    ExecutionStatus,
    FaultBoundary,
    IntegrityStatus,
    NoFaultReplayReceipt,
    ReproCapsule,
    RetryContract,
    TimelineEntry,
    TimelineState,
    WorkerSpawnReceipt,
    WorldRole,
    classify_delivery,
    classify_final,
)
from nemisis.hashing import canonical_json, sha256_bytes, sha256_json, sha256_tree
from nemisis.models import TruthLabel
from nemisis.safety import safe_relative_path
from nemisis.scenario import MAX_MESSAGE_BYTES, Event, Scenario, StoreBase, worker_send
from nemisis.scenarios import scenario_for
from nemisis.scenarios.sqlite_credit_v1 import STORE_REMEDY, CreditStore

RUNNER_ID = "sqlite-credit-runner-v1"
RUNNER_VERSION = "1"


class _AttemptFailure(RuntimeError):
    def __init__(
        self,
        status: ExecutionStatus,
        detail: str,
        *,
        integrity: IntegrityStatus = IntegrityStatus.INCOMPLETE,
    ) -> None:
        super().__init__(detail)
        self.status = status
        self.detail = detail[:1_000]
        self.integrity = integrity


class AnchorResolutionError(ValueError):
    """An accepted supported target did not map uniquely in one exact tree."""

    def __init__(
        self,
        status: AnchorResolutionStatus,
        matched_paths: tuple[str, ...],
        detail: str,
    ) -> None:
        super().__init__(detail)
        self.status = status
        self.matched_paths = matched_paths


class _Drain:
    """Read one worker stream to EOF on a thread, hashing it, so the worker never blocks on a
    full pipe. EOF arrives only when every holder of the write end has closed it, which is how
    surviving descendants are detected."""

    def __init__(self, stream: object) -> None:
        self.digest = hashlib.sha256()
        self._stream = stream
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self) -> None:
        # Raw bytes only: a text wrapper could raise UnicodeDecodeError on one stray byte, end
        # this thread early, and make a pipe still held by a child look closed.
        read = getattr(self._stream, "read", None)
        if read is None:
            return
        with suppress(OSError, ValueError):  # ValueError: stream closed by the controller
            while chunk := read(65_536):
                self.digest.update(chunk if isinstance(chunk, bytes) else chunk.encode())
        with suppress(OSError, ValueError):
            close = getattr(self._stream, "close", None)
            if close is not None:
                close()

    def finished(self, timeout: float) -> bool:
        self.thread.join(timeout)
        return not self.thread.is_alive()


@dataclass
class _Spawn:
    index: int
    phase: str
    process: subprocess.Popen[bytes]
    channel: socket.socket
    worker_nonce: str
    session_id: str
    started_at: datetime
    event_digest: str
    receive_buffer: bytearray = field(default_factory=bytearray)
    operations: list[str] = field(default_factory=list)
    ended_at: datetime | None = None
    stdout_digest: str = field(default_factory=lambda: sha256_bytes(b""))
    stderr_digest: str = field(default_factory=lambda: sha256_bytes(b""))
    drains: tuple[_Drain, _Drain] | None = None

    def __post_init__(self) -> None:
        if self.process.stdout is not None and self.process.stderr is not None:
            self.drains = (_Drain(self.process.stdout), _Drain(self.process.stderr))


def initial_database_digest(scenario: Scenario, event: Mapping[str, object]) -> str:
    """Digest the trusted logical seed independently from SQLite file layout."""
    return sha256_json(scenario.seed_identity(scenario.normalize_event(event)))


def runner_environment_digest() -> str:
    """Bind the capsule to the trusted runner and relevant local runtime."""
    return sha256_json(
        {
            "machine": platform.machine(),
            "platform": platform.system(),
            "python": platform.python_version(),
            "pydantic": version("pydantic"),
            "runner": sha256_bytes(Path(__file__).read_bytes()),
            "runner_id": RUNNER_ID,
            "runner_version": RUNNER_VERSION,
            "sqlite": sqlite3.sqlite_version,
        }
    )


def capsule_event(capsule: ReproCapsule) -> Event:
    """The exact event a capsule replays, in the shape its scenario validates."""
    return scenario_for(capsule.scenario_id).normalize_event(
        {
            "account_id": capsule.account_id,
            "amount_cents": capsule.amount_cents,
            "event_id": capsule.event_id,
        }
    )


def bind_anchor(
    contract: RetryContract,
    source_tree: Path,
    *,
    source_ref: str | None = None,
    resolved_source_identity: str | None = None,
) -> AnchorBinding:
    """Resolve exactly one accepted synchronous two-argument handler."""
    if not contract.accepted:
        raise ValueError("retry contract has not been accepted")
    try:
        scenario = scenario_for(contract.scenario_id)
    except ValueError:
        scenario = None
    if (
        scenario is None
        or contract.adapter_id != scenario.adapter_id
        or contract.fault_intent_id != scenario.fault_intent_id
        or contract.probe_id != scenario.probe_id
        or contract.predicate_ids != (scenario.predicate_id,)
        or contract.target != scenario.target
    ):
        raise ValueError("retry contract uses an unsupported trusted catalog binding")
    root = source_tree.resolve()
    module_name, symbol = contract.target.split(":", 1)
    module_path = Path(*module_name.split("."))
    candidates = (root / module_path.with_suffix(".py"), root / module_path / "__init__.py")
    matches = [path for path in candidates if path.is_file() and not path.is_symlink()]
    relative_matches = tuple(path.relative_to(root).as_posix() for path in matches)
    if not matches:
        raise AnchorResolutionError(
            AnchorResolutionStatus.ZERO_MATCHES,
            (),
            "supported target has no file binding in the exact tree",
        )
    if len(matches) > 1:
        raise AnchorResolutionError(
            AnchorResolutionStatus.MULTIPLE_MATCHES,
            relative_matches,
            "supported target has multiple file bindings in the exact tree",
        )
    path = matches[0]
    try:
        tree = ast.parse(path.read_bytes(), filename=str(path))
    except (OSError, SyntaxError, UnicodeDecodeError) as error:
        raise AnchorResolutionError(
            AnchorResolutionStatus.INVALID_MATCH,
            relative_matches,
            "target handler is not valid UTF-8 Python",
        ) from error
    definitions = [
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == symbol
    ]
    if not definitions:
        raise AnchorResolutionError(
            AnchorResolutionStatus.ZERO_MATCHES,
            (),
            f"supported target has no top-level `def {symbol}` in the exact tree (an alias or "
            "re-export is not a binding)",
        )
    if len(definitions) > 1:
        raise AnchorResolutionError(
            AnchorResolutionStatus.MULTIPLE_MATCHES,
            (relative_matches[0], relative_matches[0]),
            "supported target has multiple top-level handler bindings in the exact tree",
        )
    if isinstance(definitions[0], ast.AsyncFunctionDef):
        raise AnchorResolutionError(
            AnchorResolutionStatus.INVALID_MATCH,
            relative_matches,
            "target handler must be synchronous",
        )
    arguments = definitions[0].args
    if (
        len(arguments.posonlyargs) + len(arguments.args) != 2
        or arguments.vararg is not None
        or arguments.kwarg is not None
        or arguments.kwonlyargs
        or arguments.defaults
    ):
        raise AnchorResolutionError(
            AnchorResolutionStatus.INVALID_MATCH,
            relative_matches,
            "target handler must accept exactly (store, event)",
        )
    relative = path.relative_to(root).as_posix()
    safe_relative_path(relative)
    binding_tree_digest = sha256_tree(root, ignored_names=frozenset({"__pycache__"}))
    return AnchorBinding.with_digest(
        contract_digest=contract.digest,
        scenario_id=contract.scenario_id,
        source_ref=source_ref or binding_tree_digest,
        resolved_source_identity=resolved_source_identity or binding_tree_digest,
        tree_digest=binding_tree_digest,
        handler_path=relative,
        handler_symbol=symbol,
        adapter_id=contract.adapter_id,
        fault_intent_id=contract.fault_intent_id,
    )


def execute_attempt(
    *,
    capsule: ReproCapsule,
    binding: AnchorBinding,
    source_tree: Path,
    work_dir: Path,
    role: WorldRole | str,
    execution_nonce: str,
    timeout_seconds: float = 10.0,
    transport: TruthLabel = TruthLabel.LOCAL,
    kill_after_commit: int | None = None,
) -> AttemptReceipt:
    """Kill one worker at its durable effect (or after commit N), then replay in a fresh worker."""
    started_at = datetime.now(UTC)
    timeline = [TimelineEntry(state=TimelineState.PREFLIGHT, timestamp=started_at)]
    spawns: list[_Spawn] = []
    pre: CreditSnapshot | None = None
    checkpoint: CreditSnapshot | None = None
    post_kill: CreditSnapshot | None = None
    final: CreditSnapshot | None = None
    initial_file_digest: str | None = None
    status = ExecutionStatus.COMPLETED
    integrity = IntegrityStatus.VALID
    observation = CrashObservation.NOT_OBSERVED
    failure_detail: str | None = None
    checkpoint_reached = False
    kill_signal: int | None = None
    replay_acknowledged = False
    database_id = f"db-{uuid.uuid4().hex}"
    tree_after: str | None = None
    root = source_tree.resolve()
    database = work_dir.resolve() / f"{database_id}.sqlite3"
    try:
        scenario = _scenario(capsule)
        event = capsule_event(capsule)
        _preflight(
            scenario, capsule, binding, root, work_dir.resolve(), execution_nonce, timeout_seconds
        )
        work_dir.mkdir(parents=True, exist_ok=False)
        initial_file_digest = _seed_database(scenario, database, event)
        timeline.append(_entry(TimelineState.DATABASE_SEEDED, database_id))
        pre = _probe(scenario, database, event)
        timeline.append(_entry(TimelineState.PRE_CRASH_PROBED))

        first = _spawn_worker(
            scenario=scenario,
            capsule=capsule,
            binding=binding,
            source_tree=root,
            database=database,
            execution_nonce=execution_nonce,
            index=1,
            phase="first",
        )
        spawns.append(first)
        timeline.append(_entry(TimelineState.FIRST_WORKER_STARTED, str(first.process.pid)))
        _expect_hello(first, capsule, execution_nonce, timeout_seconds)
        checkpoint = _wait_for_checkpoint(
            scenario,
            first,
            database,
            event,
            capsule.fault_boundary,
            timeout_seconds,
            previous=pre,
            kill_after_commit=kill_after_commit,
        )
        checkpoint_reached = True
        timeline.append(_entry(TimelineState.CHECKPOINT_REACHED, checkpoint.digest))
        _kill_and_wait(first, timeout_seconds)
        kill_signal = signal.SIGKILL
        timeline.append(_entry(TimelineState.WORKER_KILLED, str(first.process.returncode)))
        post_kill = _probe(scenario, database, event)
        _require_others_untouched(scenario, database, event)
        if post_kill.digest != checkpoint.digest:
            raise _AttemptFailure(
                ExecutionStatus.INTEGRITY_ERROR,
                "durable checkpoint changed after worker death",
                integrity=IntegrityStatus.INVALID,
            )
        timeline.append(_entry(TimelineState.POST_KILL_PROBED, post_kill.digest))

        replay_worker = _spawn_worker(
            scenario=scenario,
            capsule=capsule,
            binding=binding,
            source_tree=root,
            database=database,
            execution_nonce=execution_nonce,
            index=2,
            phase="replay",
        )
        spawns.append(replay_worker)
        timeline.append(_entry(TimelineState.REPLAY_WORKER_STARTED, str(replay_worker.process.pid)))
        _expect_hello(replay_worker, capsule, execution_nonce, timeout_seconds)
        final = _finish_replay(
            scenario,
            replay_worker,
            capsule,
            execution_nonce,
            timeout_seconds,
            database=database,
            event=event,
            previous=post_kill,
        )
        replay_acknowledged = True
        timeline.append(_entry(TimelineState.EVENT_REPLAYED, capsule.event_digest))
        timeline.append(_entry(TimelineState.FINAL_STATE_PROBED, final.digest))
        tree_after = sha256_tree(root, ignored_names=frozenset({"__pycache__"}))
        if tree_after != binding.tree_digest:
            raise _AttemptFailure(
                ExecutionStatus.INTEGRITY_ERROR,
                "source tree changed during trusted execution",
                integrity=IntegrityStatus.INVALID,
            )
        _require_only_the_store_wrote(work_dir.resolve(), database)
        observation = classify_final(final, scenario.effect_delta(event))
    except _AttemptFailure as error:
        status, integrity, failure_detail = error.status, error.integrity, error.detail
    except (OSError, sqlite3.Error, ValueError) as error:
        status = ExecutionStatus.SETUP_ERROR
        integrity = IntegrityStatus.INCOMPLETE
        failure_detail = f"{type(error).__name__}: {str(error)[:800]}"

    status, integrity, failure_detail = _after_cleanup(
        _cleanup(spawns), status, integrity, failure_detail
    )
    ended_at = datetime.now(UTC)
    timeline.append(
        TimelineEntry(
            state=TimelineState.COMPLETE
            if status is ExecutionStatus.COMPLETED
            else TimelineState.FAILED,
            timestamp=ended_at,
            detail=(failure_detail or observation.value)[:500],
        )
    )
    spawn_receipts = tuple(_spawn_receipt(item, capsule.event_digest) for item in spawns)
    return AttemptReceipt.with_digest(
        receipt_id=f"attempt-{uuid.uuid4().hex}",
        role=WorldRole(role),
        transport=transport,
        execution_status=status,
        integrity_status=integrity,
        observation=observation,
        capsule_digest=capsule.digest,
        contract_digest=capsule.contract_digest,
        binding_digest=binding.digest,
        tree_digest=binding.tree_digest,
        post_execution_tree_digest=tree_after,
        environment_digest=capsule.environment_digest,
        event_digest=capsule.event_digest,
        amount_cents=capsule.amount_cents,
        initial_database_digest=capsule.initial_database_digest,
        initial_database_file_digest=initial_file_digest,
        database_id=database_id,
        execution_nonce=execution_nonce,
        started_at=started_at,
        ended_at=ended_at,
        timeline=tuple(timeline),
        spawns=spawn_receipts,
        pre_crash_snapshot=pre,
        checkpoint_snapshot=checkpoint,
        post_kill_snapshot=post_kill,
        final_snapshot=final,
        checkpoint_reached=checkpoint_reached,
        first_worker_operations=tuple(spawns[0].operations[:MAX_SWEEP_COMMITS]) if spawns else (),
        kill_after_commit=kill_after_commit,
        kill_signal=int(kill_signal) if kill_signal is not None else None,
        replay_acknowledged=replay_acknowledged,
        failure_detail=failure_detail,
    )


def execute_no_fault_replay(
    *,
    capsule: ReproCapsule,
    binding: AnchorBinding,
    source_tree: Path,
    work_dir: Path,
    execution_nonce: str,
    timeout_seconds: float = 10.0,
    role: WorldRole | str = WorldRole.BASE,
) -> NoFaultReplayReceipt:
    """Deliver the event twice in fresh workers with no kill, recording every store commit."""
    started_at = datetime.now(UTC)
    spawns: list[_Spawn] = []
    initial: CreditSnapshot | None = None
    first_delivery: CreditSnapshot | None = None
    final: CreditSnapshot | None = None
    initial_file_digest: str | None = None
    tree_after: str | None = None
    status = ExecutionStatus.COMPLETED
    integrity = IntegrityStatus.VALID
    observation = CrashObservation.NOT_OBSERVED
    failure_detail: str | None = None
    database_id = f"db-{uuid.uuid4().hex}"
    root = source_tree.resolve()
    database = work_dir.resolve() / f"{database_id}.sqlite3"
    try:
        scenario = _scenario(capsule)
        event = capsule_event(capsule)
        _preflight(
            scenario, capsule, binding, root, work_dir.resolve(), execution_nonce, timeout_seconds
        )
        work_dir.mkdir(parents=True, exist_ok=False)
        initial_file_digest = _seed_database(scenario, database, event)
        initial = _probe(scenario, database, event)

        first = _spawn_worker(
            scenario=scenario,
            capsule=capsule,
            binding=binding,
            source_tree=root,
            database=database,
            execution_nonce=execution_nonce,
            index=1,
            phase="first",
        )
        spawns.append(first)
        _expect_hello(first, capsule, execution_nonce, timeout_seconds)
        first_delivery = _finish_replay(
            scenario,
            first,
            capsule,
            execution_nonce,
            timeout_seconds,
            database=database,
            event=event,
            previous=initial,
        )

        replay_worker = _spawn_worker(
            scenario=scenario,
            capsule=capsule,
            binding=binding,
            source_tree=root,
            database=database,
            execution_nonce=execution_nonce,
            index=2,
            phase="replay",
        )
        spawns.append(replay_worker)
        _expect_hello(replay_worker, capsule, execution_nonce, timeout_seconds)
        final = _finish_replay(
            scenario,
            replay_worker,
            capsule,
            execution_nonce,
            timeout_seconds,
            database=database,
            event=event,
            previous=first_delivery,
        )
        tree_after = sha256_tree(root, ignored_names=frozenset({"__pycache__"}))
        if tree_after != binding.tree_digest:
            raise _AttemptFailure(
                ExecutionStatus.INTEGRITY_ERROR,
                "source tree changed during no-fault replay",
                integrity=IntegrityStatus.INVALID,
            )
        _require_only_the_store_wrote(work_dir.resolve(), database)
        observation = classify_delivery(first_delivery, final, scenario.effect_delta(event))
    except _AttemptFailure as error:
        status, integrity, failure_detail = error.status, error.integrity, error.detail
    except (OSError, sqlite3.Error, ValueError) as error:
        status = ExecutionStatus.SETUP_ERROR
        integrity = IntegrityStatus.INCOMPLETE
        failure_detail = f"{type(error).__name__}: {str(error)[:800]}"

    status, integrity, failure_detail = _after_cleanup(
        _cleanup(spawns), status, integrity, failure_detail
    )
    return NoFaultReplayReceipt.with_digest(
        receipt_id=f"no-fault-{uuid.uuid4().hex}",
        role=WorldRole(role),
        execution_status=status,
        integrity_status=integrity,
        observation=observation,
        parent_capsule_digest=capsule.digest,
        contract_digest=capsule.contract_digest,
        binding_digest=binding.digest,
        tree_digest=binding.tree_digest,
        post_execution_tree_digest=tree_after,
        environment_digest=capsule.environment_digest,
        event_digest=capsule.event_digest,
        amount_cents=capsule.amount_cents,
        initial_database_digest=capsule.initial_database_digest,
        initial_database_file_digest=initial_file_digest,
        database_id=database_id,
        execution_nonce=execution_nonce,
        started_at=started_at,
        ended_at=datetime.now(UTC),
        spawns=tuple(_spawn_receipt(item, capsule.event_digest) for item in spawns),
        first_delivery_operations=(
            tuple(spawns[0].operations[:MAX_SWEEP_COMMITS]) if spawns else ()
        ),
        first_delivery_commit_count=len(spawns[0].operations) if spawns else 0,
        replay_operations=(
            tuple(spawns[1].operations[:MAX_SWEEP_COMMITS]) if len(spawns) > 1 else ()
        ),
        replay_commit_count=len(spawns[1].operations) if len(spawns) > 1 else 0,
        initial_snapshot=initial,
        first_delivery_snapshot=first_delivery,
        final_snapshot=final,
        failure_detail=failure_detail,
    )


def _scenario(capsule: ReproCapsule) -> Scenario:
    try:
        return scenario_for(capsule.scenario_id)
    except ValueError as error:
        raise _AttemptFailure(ExecutionStatus.UNSUPPORTED, str(error)) from error


def _require_only_the_store_wrote(work_dir: Path, database: Path) -> None:
    """Refuse handlers that keep durable state beside the database.

    Kill points are store commits. A dedup file or journal written in the worker's directory has
    crash windows the sweep cannot reach, so such a handler cannot earn a verdict. Writes elsewhere
    on the machine are outside what local mode can see and are a documented boundary.
    """
    expected = {database.name, f"{database.name}-wal", f"{database.name}-shm"}
    extra = sorted(
        path.relative_to(work_dir).as_posix()
        for path in work_dir.rglob("*")
        if path.name not in expected and not path.is_dir()
    )
    if extra:
        shown = ", ".join(extra[:5]) + (", …" if len(extra) > 5 else "")
        raise _AttemptFailure(
            ExecutionStatus.UNSUPPORTED,
            f"the handler wrote durable files outside the store ({shown}); kill points are store "
            "commits, so crash windows around that state cannot be reached and no verdict is "
            "issued",
        )


def _after_cleanup(
    cleanup_error: str | None,
    status: ExecutionStatus,
    integrity: IntegrityStatus,
    failure_detail: str | None,
) -> tuple[ExecutionStatus, IntegrityStatus, str | None]:
    """A cleanup problem fails a completed run; it never hides an earlier failure."""
    if cleanup_error is None:
        return status, integrity, failure_detail
    if status is ExecutionStatus.COMPLETED:
        return ExecutionStatus.CLEANUP_ERROR, IntegrityStatus.INCOMPLETE, cleanup_error
    return status, integrity, f"{failure_detail}; cleanup: {cleanup_error}"[:1_000]


def _preflight(
    scenario: Scenario,
    capsule: ReproCapsule,
    binding: AnchorBinding,
    source_tree: Path,
    work_dir: Path,
    execution_nonce: str,
    timeout_seconds: float,
) -> None:
    if (
        os.name != "posix"
        or not hasattr(os, "killpg")
        or not hasattr(signal, "SIGKILL")
        or sys.version_info < (3, 12)
    ):
        raise _AttemptFailure(
            ExecutionStatus.UNSUPPORTED, "POSIX Python 3.12+ with SIGKILL required"
        )
    if timeout_seconds <= 0:
        raise _AttemptFailure(ExecutionStatus.SETUP_ERROR, "timeout must be positive")
    if not execution_nonce or len(execution_nonce) > 120:
        raise _AttemptFailure(ExecutionStatus.SETUP_ERROR, "invalid execution nonce")
    if not source_tree.is_dir() or work_dir.is_relative_to(source_tree):
        raise _AttemptFailure(
            ExecutionStatus.SETUP_ERROR, "database work directory must be external"
        )
    if binding.contract_digest != capsule.contract_digest:
        raise _AttemptFailure(
            ExecutionStatus.INTEGRITY_ERROR,
            "anchor contract differs from capsule",
            integrity=IntegrityStatus.INVALID,
        )
    if binding.tree_digest != sha256_tree(source_tree, ignored_names=frozenset({"__pycache__"})):
        raise _AttemptFailure(
            ExecutionStatus.INTEGRITY_ERROR,
            "anchor tree digest differs from source tree",
            integrity=IntegrityStatus.INVALID,
        )
    if capsule.environment_digest != runner_environment_digest():
        raise _AttemptFailure(
            ExecutionStatus.INTEGRITY_ERROR,
            "capsule runner environment differs from this runner",
            integrity=IntegrityStatus.INVALID,
        )
    if capsule.initial_database_digest != initial_database_digest(scenario, capsule_event(capsule)):
        raise _AttemptFailure(
            ExecutionStatus.INTEGRITY_ERROR,
            "capsule initial database digest changed",
            integrity=IntegrityStatus.INVALID,
        )


def _seed_database(scenario: Scenario, path: Path, event: Mapping[str, object]) -> str:
    normalized = scenario.normalize_event(event)
    with sqlite3.connect(path) as connection:
        if connection.execute("PRAGMA journal_mode=WAL").fetchone() != ("wal",):
            raise sqlite3.OperationalError("SQLite WAL mode unavailable")
        connection.execute("PRAGMA synchronous=FULL")
        if connection.execute("PRAGMA synchronous").fetchone() != (2,):
            raise sqlite3.OperationalError("SQLite FULL synchronous mode unavailable")
        scenario.seed(connection, normalized)
        connection.commit()
        connection.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
        connection.execute("PRAGMA journal_mode=DELETE").fetchone()
    if Path(f"{path}-wal").exists() or Path(f"{path}-shm").exists():
        raise sqlite3.OperationalError("seed database retained WAL sidecars")
    return sha256_bytes(path.read_bytes())


def _read_only(path: Path) -> sqlite3.Connection:
    uri = f"file:{quote(str(path.resolve()))}?mode=ro"
    connection = sqlite3.connect(uri, uri=True, timeout=5)
    connection.execute("PRAGMA query_only=ON")
    return connection


def _probe_others(scenario: Scenario, path: Path, event: Mapping[str, object]) -> str:
    """Digest every row that is not this event's: they must never change during a run."""
    normalized = scenario.normalize_event(event)
    with _read_only(path) as connection:
        return sha256_json(scenario.others(connection, normalized))


def _require_others_untouched(
    scenario: Scenario, database: Path, event: Mapping[str, object]
) -> None:
    """Every row that is not this event's must still be exactly as seeded."""
    if _probe_others(scenario, database, event) != scenario.seeded_others_digest:
        raise _AttemptFailure(
            ExecutionStatus.INTEGRITY_ERROR,
            "rows that belong to other accounts or events changed during the run; something "
            "wrote around the trusted store",
            integrity=IntegrityStatus.INVALID,
        )


def _probe(scenario: Scenario, path: Path, event: Mapping[str, object]) -> CreditSnapshot:
    normalized = scenario.normalize_event(event)
    try:
        with _read_only(path) as connection:
            return scenario.probe(connection, normalized)
    except sqlite3.OperationalError as error:
        raise _AttemptFailure(
            ExecutionStatus.PROBE_ERROR, "read-only state probe was incomplete"
        ) from error


def _spawn_worker(
    *,
    scenario: Scenario,
    capsule: ReproCapsule,
    binding: AnchorBinding,
    source_tree: Path,
    database: Path,
    execution_nonce: str,
    index: int,
    phase: str,
) -> _Spawn:
    parent, child = socket.socketpair()
    worker_nonce, session_id = uuid.uuid4().hex, uuid.uuid4().hex
    argv = [
        sys.executable,
        "-I",
        "-B",
        "-m",
        "nemisis.sqlite_credit",
        "_worker",
        scenario.scenario_id,
        str(source_tree),
        binding.handler_path,
        binding.handler_symbol,
        str(database),
        canonical_json(capsule_event(capsule)).decode(),
        execution_nonce,
        worker_nonce,
        session_id,
        str(child.fileno()),
    ]
    try:
        process = subprocess.Popen(
            argv,
            cwd=database.parent,
            env={
                "PATH": os.environ.get("PATH", ""),
                "PYTHONDONTWRITEBYTECODE": "1",
                "PYTHONHASHSEED": "0",
                "PYTHONNOUSERSITE": "1",
            },
            pass_fds=(child.fileno(),),
            start_new_session=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except OSError as error:
        parent.close()
        child.close()
        status = ExecutionStatus.LAUNCH_ERROR if index == 1 else ExecutionStatus.RESTART_ERROR
        raise _AttemptFailure(status, f"worker launch failed ({type(error).__name__})") from error
    child.close()
    return _Spawn(
        index=index,
        phase=phase,
        process=process,
        channel=parent,
        worker_nonce=worker_nonce,
        session_id=session_id,
        started_at=datetime.now(UTC),
        event_digest=capsule.event_digest,
    )


def _expect_hello(
    spawn: _Spawn, capsule: ReproCapsule, execution_nonce: str, timeout_seconds: float
) -> None:
    message = _receive(spawn.channel, spawn.receive_buffer, timeout_seconds)
    expected = {
        "event_digest": capsule.event_digest,
        "execution_nonce": execution_nonce,
        "ipc_session_id": spawn.session_id,
        "pgid": spawn.process.pid,
        "pid": spawn.process.pid,
        "type": "hello",
        "worker_nonce": spawn.worker_nonce,
    }
    if message != expected:
        raise _AttemptFailure(
            ExecutionStatus.PROTOCOL_ERROR, "worker handshake did not match spawn"
        )
    try:
        pgid = os.getpgid(spawn.process.pid)
    except OSError as error:
        raise _AttemptFailure(
            ExecutionStatus.PROTOCOL_ERROR, "worker process group disappeared"
        ) from error
    if pgid != spawn.process.pid:
        raise _AttemptFailure(
            ExecutionStatus.PROTOCOL_ERROR, "worker lacks a private process group"
        )


def _wait_for_checkpoint(
    scenario: Scenario,
    spawn: _Spawn,
    database: Path,
    event: Mapping[str, object],
    fault_boundary: FaultBoundary,
    timeout_seconds: float,
    *,
    previous: CreditSnapshot,
    kill_after_commit: int | None = None,
) -> CreditSnapshot:
    normalized = scenario.normalize_event(event)
    deadline = monotonic() + timeout_seconds
    while True:
        message = _receive(spawn.channel, spawn.receive_buffer, max(0.001, deadline - monotonic()))
        kind = message.get("type")
        if kind == "commit":
            snapshot = _attributed_probe(scenario, database, event, previous, message, spawn=spawn)
            spawn.operations.append(str(message.get("operation")))
            previous = snapshot
            if kill_after_commit is not None:
                if len(spawn.operations) == kill_after_commit:
                    return snapshot
                _send(spawn.channel, {"type": "continue"})
                continue
            if scenario.checkpoint_reached(snapshot, normalized, fault_boundary):
                return snapshot
            _send(spawn.channel, {"type": "continue"})
        elif kind in {"done", "error"}:
            if kind == "done" and not spawn.operations:
                detail = _no_commit_detail(scenario, database, event, previous)
            elif kind == "done":
                detail = (
                    f"the handler finished without ever committing the {scenario.effect_noun} "
                    f"(commits seen: {', '.join(spawn.operations)}); check it "
                    f"{_verb(scenario)} at all before crash-testing it"
                )
            else:
                detail = (
                    f"the handler raised {message.get('error', 'an exception')} before the "
                    f"durable {scenario.effect_noun} checkpoint"
                )
            raise _AttemptFailure(ExecutionStatus.CHECKPOINT_NOT_REACHED, detail)
        else:
            raise _AttemptFailure(ExecutionStatus.PROTOCOL_ERROR, "unexpected worker message")


def _verb(scenario: Scenario) -> str:
    return {"credit": "credits"}.get(scenario.effect_noun, f"makes its {scenario.effect_noun}")


def _no_commit_detail(
    scenario: Scenario, database: Path, event: Mapping[str, object], seeded: CreditSnapshot
) -> str:
    """The worker finished without one store commit: say whether it wrote around the store.

    The textbook atomic fix written as one raw SQL transaction lands here. It is correct and it is
    unjudgeable, because no kill can be placed inside a write the store did not make; the judge
    who wrote it is told the store call that expresses the same fix.
    """
    store = scenario.store_class.__name__
    after = _probe(scenario, database, event)
    if (
        after.digest == seeded.digest
        and _probe_others(scenario, database, event) == scenario.seeded_others_digest
    ):
        return (
            f"the handler finished without a single {store} commit and left the database as "
            f"seeded, so there is no durable {scenario.effect_noun} to crash-test"
        )
    return (
        f"the handler changed the database without a single {store} commit (this event now "
        f"shows balance {after.account_balance_cents} cents, {after.event_ledger_count} ledger "
        f"row(s), {after.event_marker_count} marker), so the money moved through a connection "
        f"CrashCheck does not own and no kill point exists inside that write. "
        f"{scenario.store_remedy}"
    )


def _kill_and_wait(spawn: _Spawn, timeout_seconds: float) -> None:
    try:
        os.killpg(spawn.process.pid, signal.SIGKILL)
    except OSError as error:
        raise _AttemptFailure(ExecutionStatus.KILL_ERROR, "process-group SIGKILL failed") from error
    try:
        return_code = spawn.process.wait(timeout=timeout_seconds)
    except subprocess.TimeoutExpired as error:
        raise _AttemptFailure(ExecutionStatus.WAIT_ERROR, "killed worker was not reaped") from error
    if return_code != -signal.SIGKILL:
        raise _AttemptFailure(ExecutionStatus.WAIT_ERROR, "worker did not exit from SIGKILL")
    _collect(spawn)


def _finish_replay(
    scenario: Scenario,
    spawn: _Spawn,
    capsule: ReproCapsule,
    execution_nonce: str,
    timeout_seconds: float,
    *,
    database: Path,
    event: Mapping[str, object],
    previous: CreditSnapshot,
) -> CreditSnapshot:
    """Drive one worker to completion; every durable change must be a store commit it reported."""
    deadline = monotonic() + timeout_seconds
    while True:
        message = _receive(spawn.channel, spawn.receive_buffer, max(0.001, deadline - monotonic()))
        kind = message.get("type")
        if kind == "commit":
            previous = _attributed_probe(scenario, database, event, previous, message, spawn=spawn)
            spawn.operations.append(str(message.get("operation")))
            _send(spawn.channel, {"type": "continue"})
            continue
        if kind == "error":
            raise _AttemptFailure(
                ExecutionStatus.REPLAY_ERROR,
                f"the handler raised {message.get('error', 'an exception')} during the "
                f"{spawn.phase} delivery; a redelivery must return normally to be exactly once",
            )
        expected = {
            "event_digest": capsule.event_digest,
            "execution_nonce": execution_nonce,
            "type": "done",
        }
        if message != expected:
            raise _AttemptFailure(ExecutionStatus.PROTOCOL_ERROR, "replay completion was malformed")
        break
    try:
        return_code = spawn.process.wait(timeout=max(1.0, deadline - monotonic()))
    except subprocess.TimeoutExpired as error:
        raise _AttemptFailure(
            ExecutionStatus.TIMEOUT,
            f"the {spawn.phase} delivery worker reported done but did not exit; a non-daemon "
            "thread or child kept it alive",
        ) from error
    _collect(spawn)
    if return_code != 0:
        raise _AttemptFailure(ExecutionStatus.REPLAY_ERROR, "replay worker returned nonzero")
    final = _probe(scenario, database, event)
    _require_others_untouched(scenario, database, event)
    if final.digest != previous.digest:
        raise _AttemptFailure(
            ExecutionStatus.INTEGRITY_ERROR,
            "the database changed after the worker's last reported store commit; something wrote "
            "around the trusted store (an exit hook, a thread, a child, or a direct connection). "
            + scenario.store_remedy,
            integrity=IntegrityStatus.INVALID,
        )
    return final


def _attributed_probe(
    scenario: Scenario,
    database: Path,
    event: Mapping[str, object],
    previous: CreditSnapshot,
    message: Mapping[str, object],
    *,
    spawn: _Spawn | None = None,
) -> CreditSnapshot:
    """Probe after a reported commit and refuse any change the named operation cannot explain.

    A handler that writes to the database through its own connection never pauses the
    controller, so its effect would surface here as an unattributed delta. That is an integrity
    failure, not a verdict: the kill point can no longer be trusted to sit where the money moved.
    """
    normalized = scenario.normalize_event(event)
    operation = message.get("operation")
    snapshot = _probe(scenario, database, event)
    _require_others_untouched(scenario, database, event)
    expected = scenario.store_operations.get(str(operation))
    if expected is None:
        raise _AttemptFailure(
            ExecutionStatus.PROTOCOL_ERROR,
            f"worker reported an unknown store operation {operation!r}",
        )
    observed = (
        snapshot.account_balance_cents - previous.account_balance_cents,
        snapshot.event_ledger_count - previous.event_ledger_count,
        snapshot.event_ledger_total_cents - previous.event_ledger_total_cents,
        snapshot.event_marker_count - previous.event_marker_count,
    )
    wanted = expected(normalized)
    if observed != wanted:
        raise _AttemptFailure(
            ExecutionStatus.INTEGRITY_ERROR,
            f"the durable change after {operation} was not the one {operation} makes: the probe "
            f"saw balance {observed[0]:+d}, ledger rows {observed[1]:+d}, marker {observed[3]:+d} "
            f"for this event, not balance {wanted[0]:+d}, ledger rows {wanted[1]:+d}, marker "
            f"{wanted[3]:+d}; either something wrote around the trusted store or a store call "
            f"was made with values that are not this event's. {scenario.store_remedy}",
            integrity=IntegrityStatus.INVALID,
        )
    return snapshot


def _receive(
    channel: socket.socket, buffer: bytearray, timeout_seconds: float
) -> dict[str, object]:
    deadline = monotonic() + timeout_seconds
    try:
        while (newline := buffer.find(b"\n")) < 0:
            if len(buffer) > MAX_MESSAGE_BYTES:
                raise _AttemptFailure(
                    ExecutionStatus.PROTOCOL_ERROR, "worker message was oversized"
                )
            remaining = deadline - monotonic()
            if remaining <= 0:
                raise _AttemptFailure(ExecutionStatus.TIMEOUT, "worker IPC timed out")
            channel.settimeout(remaining)
            chunk = channel.recv(min(1024, MAX_MESSAGE_BYTES + 1 - len(buffer)))
            if not chunk:
                raise _AttemptFailure(ExecutionStatus.IPC_ERROR, "worker closed IPC unexpectedly")
            buffer.extend(chunk)
    except TimeoutError as error:
        raise _AttemptFailure(ExecutionStatus.TIMEOUT, "worker IPC timed out") from error
    if newline > MAX_MESSAGE_BYTES:
        raise _AttemptFailure(ExecutionStatus.PROTOCOL_ERROR, "worker message was oversized")
    data = bytes(buffer[:newline])
    del buffer[: newline + 1]
    try:
        value = json.loads(data)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise _AttemptFailure(
            ExecutionStatus.PROTOCOL_ERROR, "worker message was not JSON"
        ) from error
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise _AttemptFailure(ExecutionStatus.PROTOCOL_ERROR, "worker message was not an object")
    return value


def _send(channel: socket.socket, value: Mapping[str, object]) -> None:
    try:
        channel.sendall(canonical_json(value) + b"\n")
    except OSError as error:
        raise _AttemptFailure(
            ExecutionStatus.IPC_ERROR, "controller could not acknowledge worker"
        ) from error


def _cleanup(spawns: list[_Spawn]) -> str | None:
    failure: str | None = None
    for spawn in spawns:
        try:
            spawn.channel.close()
            # Deliberately unconditional: a /dev/null descendant can outlive a reaped leader in
            # the same group (tested). The window for PID reuse between reap and this call is
            # microseconds; containment wins that trade.
            with suppress(ProcessLookupError, PermissionError):
                os.killpg(spawn.process.pid, signal.SIGKILL)
            if spawn.process.poll() is None:
                spawn.process.wait(timeout=2)
            _collect(spawn)
        except _AttemptFailure as error:
            failure = error.detail
        except (OSError, subprocess.SubprocessError) as error:
            failure = f"worker cleanup failed ({type(error).__name__})"
    return failure


def _collect(spawn: _Spawn) -> None:
    if spawn.ended_at is not None:
        return
    descendants_survived = False
    if spawn.drains is None:
        raise _AttemptFailure(
            ExecutionStatus.CLEANUP_ERROR, "worker output streams were not captured"
        )
    if not all(drain.finished(1) for drain in spawn.drains):
        descendants_survived = True
        with suppress(ProcessLookupError, PermissionError):
            os.killpg(spawn.process.pid, signal.SIGKILL)
        if not all(drain.finished(2) for drain in spawn.drains):
            spawn.ended_at = datetime.now(UTC)
            for stream in (spawn.process.stdout, spawn.process.stderr):
                with suppress(OSError):
                    if stream is not None:
                        stream.close()
            raise _AttemptFailure(
                ExecutionStatus.CLEANUP_ERROR,
                "a child process inherited the worker's stdout/stderr and outlived the kill; "
                "detached helpers must not share the worker's pipes",
            )
    if spawn.process.poll() is None:
        try:
            spawn.process.wait(timeout=2)
        except subprocess.TimeoutExpired as error:
            raise _AttemptFailure(
                ExecutionStatus.CLEANUP_ERROR, "worker did not exit after its output closed"
            ) from error
    spawn.stdout_digest = spawn.drains[0].digest.hexdigest()
    spawn.stderr_digest = spawn.drains[1].digest.hexdigest()
    spawn.ended_at = datetime.now(UTC)
    if descendants_survived:
        raise _AttemptFailure(
            ExecutionStatus.CLEANUP_ERROR,
            "worker descendants survived their supervisor and were killed; a fire-and-forget "
            "child that shares the worker's stdout/stderr is not exactly-once evidence",
        )


def _spawn_receipt(spawn: _Spawn, event_digest: str) -> WorkerSpawnReceipt:
    ended = spawn.ended_at or datetime.now(UTC)
    return WorkerSpawnReceipt(
        spawn_index=spawn.index,
        phase="first" if spawn.phase == "first" else "replay",
        pid=spawn.process.pid,
        process_group_id=spawn.process.pid,
        worker_nonce=spawn.worker_nonce,
        ipc_session_id=spawn.session_id,
        event_digest=event_digest,
        started_at=spawn.started_at,
        ended_at=ended,
        exit_code=spawn.process.returncode if spawn.process.returncode is not None else -999,
        stdout_excerpt="",
        stderr_excerpt="",
        stdout_digest=spawn.stdout_digest,
        stderr_digest=spawn.stderr_digest,
    )


def _entry(state: TimelineState, detail: str = "") -> TimelineEntry:
    return TimelineEntry(state=state, timestamp=datetime.now(UTC), detail=detail)


def _worker(argv: list[str]) -> int:
    if len(argv) != 10:
        return 2
    (
        scenario_id,
        source,
        handler_path,
        symbol,
        database,
        event_json,
        execution_nonce,
        nonce,
        session_id,
        fd,
    ) = argv
    channel = socket.socket(fileno=int(fd))
    scenario = scenario_for(scenario_id)
    event = scenario.normalize_event(json.loads(event_json))
    event_digest = sha256_json(event)
    try:
        worker_send(
            channel,
            {
                "event_digest": event_digest,
                "execution_nonce": execution_nonce,
                "ipc_session_id": session_id,
                "pgid": os.getpgrp(),
                "pid": os.getpid(),
                "type": "hello",
                "worker_nonce": nonce,
            },
        )
        handler = _load_handler(Path(source), handler_path, symbol)
        store = scenario.store_class(Path(database), channel, event)
        handler(store, event)
        worker_send(
            channel,
            {"event_digest": event_digest, "execution_nonce": execution_nonce, "type": "done"},
        )
        return 0
    except Exception as error:  # Candidate exceptions are bounded protocol evidence.
        with suppress(OSError):
            worker_send(channel, {"error": type(error).__name__, "type": "error"})
        return 3
    finally:
        channel.close()


def _load_handler(
    source: Path, relative: str, symbol: str
) -> Callable[[StoreBase, dict[str, str | int]], object]:
    root = source.resolve()
    path = (root / safe_relative_path(relative)).resolve()
    if not path.is_relative_to(root) or not path.is_file() or path.is_symlink():
        raise ValueError("bound handler path changed")
    module_name = relative.removesuffix(".py").replace("/", ".").removesuffix(".__init__")
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ValueError("bound handler could not be loaded")
    module = importlib.util.module_from_spec(spec)
    _append_source_path(root)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    handler = getattr(module, symbol, None)
    if not callable(handler) or len(inspect.signature(handler).parameters) != 2:
        raise ValueError("bound handler is not callable as (store, event)")
    return cast(Callable[[StoreBase, dict[str, str | int]], object], handler)


def _append_source_path(root: Path) -> None:
    value = str(root)
    if value not in sys.path:
        sys.path.append(value)


def _main() -> int:
    if len(sys.argv) >= 2 and sys.argv[1] == "_worker":
        return _worker(sys.argv[2:])
    return 2


if __name__ == "__main__":
    raise SystemExit(_main())


__all__ = [
    "MAX_MESSAGE_BYTES",
    "RUNNER_ID",
    "RUNNER_VERSION",
    "STORE_REMEDY",
    "AnchorResolutionError",
    "CreditStore",
    "bind_anchor",
    "capsule_event",
    "execute_attempt",
    "execute_no_fault_replay",
    "initial_database_digest",
    "runner_environment_digest",
]
