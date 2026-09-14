from __future__ import annotations

import ctypes
import errno
import os
import signal
import socket
import sqlite3
import subprocess
import sys
from collections.abc import Iterator
from contextlib import closing, contextmanager, suppress
from datetime import UTC, datetime
from pathlib import Path
from time import monotonic, sleep
from typing import cast

import pytest

from nemisis.crash_fixture import ATOMIC_REF, BUGGY_REF, materialize_fixture
from nemisis.crash_models import (
    AnchorResolutionStatus,
    AttemptReceipt,
    CrashObservation,
    ExecutionStatus,
    FaultBoundary,
    IntegrityStatus,
    ReproCapsule,
    WorldRole,
)
from nemisis.crashcheck import _audited_contract, _seal_capsule
from nemisis.hashing import canonical_json, sha256_bytes
from nemisis.scenarios.sqlite_credit_v1 import SCENARIO as CREDIT
from nemisis.sqlite_runner import (
    _HEADER_PRAGMAS,
    WORKER_TIMEOUT_VARIABLE,
    AnchorResolutionError,
    _AttemptFailure,
    _attributed_probe,
    _cleanup,
    _collect,
    _kill_and_wait,
    _ledger,
    _probe,
    _read_content,
    _read_only,
    _receive,
    _require_unchanged,
    _seed_database,
    _Spawn,
    _spawn_receipt,
    _xattrs,
    bind_anchor,
    execute_attempt,
    worker_timeout_seconds,
)


def test_anchor_resolution_distinguishes_zero_one_and_multiple(tmp_path: Path) -> None:
    contract = _audited_contract(CREDIT)
    zero = tmp_path / "zero"
    zero.mkdir()
    with pytest.raises(AnchorResolutionError) as missing:
        bind_anchor(contract, zero)
    assert missing.value.status is AnchorResolutionStatus.ZERO_MATCHES
    assert missing.value.matched_paths == ()

    one = materialize_fixture(BUGGY_REF, tmp_path / "one").path
    assert bind_anchor(contract, one).handler_path == "app/credits.py"

    multiple = materialize_fixture(BUGGY_REF, tmp_path / "multiple").path
    package = multiple / "app/credits"
    package.mkdir()
    (package / "__init__.py").write_bytes((multiple / "app/credits.py").read_bytes())
    with pytest.raises(AnchorResolutionError) as ambiguous:
        bind_anchor(contract, multiple)
    assert ambiguous.value.status is AnchorResolutionStatus.MULTIPLE_MATCHES
    assert ambiguous.value.matched_paths == ("app/credits.py", "app/credits/__init__.py")


def test_anchor_resolution_marks_an_async_handler_invalid(tmp_path: Path) -> None:
    contract = _audited_contract(CREDIT)
    source = materialize_fixture(BUGGY_REF, tmp_path / "async-handler").path
    (source / "app/credits.py").write_text(
        "async def apply_credit(store, event):\n    return None\n",
        encoding="utf-8",
    )

    with pytest.raises(AnchorResolutionError) as invalid:
        bind_anchor(contract, source)

    assert invalid.value.status is AnchorResolutionStatus.INVALID_MATCH
    assert invalid.value.matched_paths == ("app/credits.py",)


def test_anchor_resolution_counts_handler_definitions(tmp_path: Path) -> None:
    contract = _audited_contract(CREDIT)
    missing = materialize_fixture(BUGGY_REF, tmp_path / "missing-handler").path
    (missing / "app/credits.py").write_text(
        "def another_handler(store, event):\n    return None\n",
        encoding="utf-8",
    )
    with pytest.raises(AnchorResolutionError) as zero:
        bind_anchor(contract, missing)
    assert zero.value.status is AnchorResolutionStatus.ZERO_MATCHES
    assert zero.value.matched_paths == ()

    duplicate = materialize_fixture(BUGGY_REF, tmp_path / "duplicate-handler").path
    with (duplicate / "app/credits.py").open("a", encoding="utf-8") as source:
        source.write(
            "\n"
            + "\n".join(
                "def apply_credit(store, event):\n    return None" for _duplicate in range(8)
            )
            + "\n"
        )
    with pytest.raises(AnchorResolutionError) as multiple:
        bind_anchor(contract, duplicate)
    assert multiple.value.status is AnchorResolutionStatus.MULTIPLE_MATCHES
    assert multiple.value.matched_paths == ("app/credits.py", "app/credits.py")


def test_attributed_probe_accepts_only_the_delta_its_operation_explains(tmp_path: Path) -> None:
    event = {"account_id": "acct_7", "amount_cents": 2500, "event_id": "evt_1042"}
    database = tmp_path / "probe.sqlite3"
    _seed_database(CREDIT, database, event)
    seeded = _ledger(CREDIT, database, event)

    # Nothing changed, and mark_processed claims a marker: unattributed.
    with pytest.raises(
        _AttemptFailure, match="was not the one mark_processed makes"
    ) as unattributed:
        _attributed_probe(CREDIT, database, event, seeded, {"operation": "mark_processed"})
    assert unattributed.value.status is ExecutionStatus.INTEGRITY_ERROR
    assert unattributed.value.integrity is IntegrityStatus.INVALID

    with pytest.raises(_AttemptFailure, match="unknown store operation") as unknown:
        _attributed_probe(CREDIT, database, event, seeded, {"operation": "transfer"})
    assert unknown.value.status is ExecutionStatus.PROTOCOL_ERROR

    import sqlite3

    with sqlite3.connect(database) as connection:
        connection.execute("INSERT INTO processed_events(event_id) VALUES ('evt_1042')")
        connection.commit()
    marked = _attributed_probe(CREDIT, database, event, seeded, {"operation": "mark_processed"})
    assert marked.snapshot.event_marker_count == 1

    # The four numbers match the operation, but a table appeared: still unattributed.
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE inflight(event_id TEXT PRIMARY KEY)")
        connection.execute(
            "UPDATE accounts SET balance_cents = balance_cents + 2500 WHERE account_id = 'acct_7'"
        )
        connection.execute(
            "INSERT INTO credit_ledger(event_id, account_id, amount_cents) "
            "VALUES ('evt_1042', 'acct_7', 2500)"
        )
        connection.commit()
    with pytest.raises(_AttemptFailure, match="the schema changed") as shadow:
        _attributed_probe(CREDIT, database, event, marked, {"operation": "credit"})
    assert shadow.value.integrity is IntegrityStatus.INVALID


def test_store_requires_exact_types_and_values(tmp_path: Path) -> None:
    from nemisis.scenarios.sqlite_credit_v1 import CreditStore

    event: dict[str, str | int] = {
        "account_id": "acct_7",
        "amount_cents": 2500,
        "event_id": "evt_1042",
    }
    database = tmp_path / "store.sqlite3"
    _seed_database(CREDIT, database, event)
    controller, worker = socket.socketpair()
    store = CreditStore(database, worker, event)

    class Lying(str):
        def __eq__(self, other: object) -> bool:
            return True

        def __hash__(self) -> int:
            return 0

    try:
        for bad in (
            lambda: store.mark_processed(None),  # type: ignore[arg-type]
            lambda: store.processed(Lying("other")),
            lambda: store.credit(Lying("shadow"), "evt_1042", 2500),
            lambda: store.credit("acct_7", "evt_1042", True),
            lambda: store.credit("acct_7", "evt_1042", 2500.0),  # type: ignore[arg-type]
            lambda: store.credit_and_mark("acct_7", b"evt_1042", 2500),  # type: ignore[arg-type]
        ):
            with pytest.raises(ValueError, match="outside the accepted contract"):
                bad()
        assert store.processed("evt_1042") is False
        assert _probe(CREDIT, database, event).event_marker_count == 0
    finally:
        controller.close()
        worker.close()


def test_receive_preserves_a_coalesced_second_frame() -> None:
    controller, worker = socket.socketpair()
    buffer = bytearray()
    try:
        worker.sendall(
            canonical_json({"type": "hello"}) + b"\n" + canonical_json({"type": "commit"}) + b"\n"
        )

        assert _receive(controller, buffer, 1, what="a frame", budget=1) == {"type": "hello"}
        assert _receive(controller, buffer, 1, what="a frame", budget=1) == {"type": "commit"}
        assert not buffer
    finally:
        controller.close()
        worker.close()


def test_a_timeout_names_what_did_not_arrive_and_the_knob() -> None:
    """A flaky run must be diagnosable from its own message: which phase, which budget."""
    controller, worker = socket.socketpair()
    try:
        with pytest.raises(_AttemptFailure) as failure:
            _receive(controller, bytearray(), 0.05, what="the first worker's hello", budget=0.05)
    finally:
        controller.close()
        worker.close()
    assert failure.value.status is ExecutionStatus.TIMEOUT
    assert failure.value.detail == (
        "the first worker's hello did not arrive within 0.05 s; NEMISIS_WORKER_TIMEOUT_SECONDS "
        "raises the budget on a slow machine"
    )


@pytest.mark.parametrize(
    ("raw", "expected"),
    [(None, 10.0), ("30", 30.0), (" 2.5 ", 2.5), ("1", 1.0), ("600", 600.0)],
)
def test_worker_timeout_knob_accepts_seconds_between_one_and_six_hundred(
    monkeypatch: pytest.MonkeyPatch, raw: str | None, expected: float
) -> None:
    if raw is None:
        monkeypatch.delenv(WORKER_TIMEOUT_VARIABLE, raising=False)
    else:
        monkeypatch.setenv(WORKER_TIMEOUT_VARIABLE, raw)
    assert worker_timeout_seconds() == expected


@pytest.mark.parametrize("raw", ["0", "-1", "0.5", "601", "abc", "", "nan", "inf", "10s"])
def test_worker_timeout_knob_refuses_instead_of_clamping(
    monkeypatch: pytest.MonkeyPatch, raw: str
) -> None:
    monkeypatch.setenv(WORKER_TIMEOUT_VARIABLE, raw)
    with pytest.raises(ValueError, match="NEMISIS_WORKER_TIMEOUT_SECONDS must be a number"):
        worker_timeout_seconds()


def _execute_fixture(
    tmp_path: Path, fixture_ref: str, fault_boundary: FaultBoundary
) -> AttemptReceipt:
    contract = _audited_contract(CREDIT)
    sealed = _seal_capsule(contract)
    capsule = ReproCapsule.with_digest(
        **sealed.model_dump(mode="python", exclude={"digest", "fault_boundary"}),
        fault_boundary=fault_boundary,
    )
    source = materialize_fixture(fixture_ref, tmp_path / "source")
    binding = bind_anchor(contract, source.path)

    return execute_attempt(
        capsule=capsule,
        binding=binding,
        source_tree=source.path,
        work_dir=tmp_path / "world",
        role=WorldRole.BASE,
        execution_nonce="focused-runtime-check",
    )


def test_buggy_fixture_duplicates_at_effect_commit(tmp_path: Path) -> None:
    receipt = _execute_fixture(tmp_path, BUGGY_REF, FaultBoundary.EFFECT_COMMIT)

    assert receipt.execution_status is ExecutionStatus.COMPLETED
    assert receipt.integrity_status is IntegrityStatus.VALID
    assert receipt.observation is CrashObservation.DUPLICATE_EFFECT
    assert receipt.checkpoint_snapshot is not None
    assert receipt.checkpoint_snapshot.event_marker_count == 0


def test_buggy_fixture_is_exactly_once_at_marker_commit(tmp_path: Path) -> None:
    receipt = _execute_fixture(tmp_path, BUGGY_REF, FaultBoundary.MARKER_COMMIT)

    assert receipt.execution_status is ExecutionStatus.COMPLETED
    assert receipt.integrity_status is IntegrityStatus.VALID
    assert receipt.observation is CrashObservation.EXACTLY_ONCE
    assert receipt.checkpoint_snapshot is not None
    assert receipt.checkpoint_snapshot.event_marker_count == 1


def test_atomic_fixture_is_exactly_once_at_effect_commit(tmp_path: Path) -> None:
    receipt = _execute_fixture(tmp_path, ATOMIC_REF, FaultBoundary.EFFECT_COMMIT)

    assert receipt.execution_status is ExecutionStatus.COMPLETED
    assert receipt.integrity_status is IntegrityStatus.VALID
    assert receipt.observation is CrashObservation.EXACTLY_ONCE
    assert receipt.checkpoint_snapshot is not None
    assert receipt.checkpoint_snapshot.event_marker_count == 1


def test_collect_kills_descendants_that_hold_worker_output_open(tmp_path: Path) -> None:
    process = subprocess.Popen(
        [
            sys.executable,
            "-c",
            (
                "import subprocess,sys;"
                "subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)']);"
                "print('leader exited', flush=True)"
            ),
        ],
        cwd=tmp_path,
        start_new_session=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    process.wait(timeout=5)
    controller, worker = socket.socketpair()
    worker.close()
    spawn = _Spawn(
        index=2,
        phase="replay",
        process=process,
        channel=controller,
        worker_nonce="worker-nonce",
        session_id="session-id",
        started_at=datetime.now(UTC),
        event_digest="0" * 64,
    )
    try:
        with pytest.raises(_AttemptFailure, match="descendants survived"):
            _collect(spawn)
        assert spawn.stdout_digest == sha256_bytes(b"leader exited\n")
        assert spawn.ended_at is not None
    finally:
        controller.close()


def test_cleanup_kills_a_devnull_descendant_after_its_leader_exits(tmp_path: Path) -> None:
    process = subprocess.Popen(
        [
            sys.executable,
            "-c",
            (
                "import subprocess,sys;"
                "child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)'],"
                "stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);"
                "print(child.pid,flush=True)"
            ),
        ],
        cwd=tmp_path,
        start_new_session=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert process.stdout is not None
    child_pid = int(process.stdout.readline())
    process.wait(timeout=5)
    controller, worker = socket.socketpair()
    worker.close()
    spawn = _Spawn(
        index=2,
        phase="replay",
        process=process,
        channel=controller,
        worker_nonce="worker-nonce",
        session_id="session-id",
        started_at=datetime.now(UTC),
        event_digest="0" * 64,
    )
    try:
        assert _cleanup([spawn]) is None
        deadline = monotonic() + 2
        while True:
            try:
                os.kill(child_pid, 0)
            except ProcessLookupError:
                break
            if monotonic() >= deadline:
                pytest.fail("worker descendant survived cleanup")
            sleep(0.01)
    finally:
        controller.close()
        with suppress(ProcessLookupError):
            os.kill(child_pid, signal.SIGKILL)


def test_worker_output_is_hashed_but_not_persisted_in_its_receipt(tmp_path: Path) -> None:
    process = subprocess.Popen(
        [
            sys.executable,
            "-c",
            "import sys;print('candidate stdout');print('candidate stderr',file=sys.stderr)",
        ],
        cwd=tmp_path,
        start_new_session=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    process.wait(timeout=5)
    controller, worker = socket.socketpair()
    worker.close()
    spawn = _Spawn(
        index=2,
        phase="replay",
        process=process,
        channel=controller,
        worker_nonce="worker-nonce",
        session_id="session-id",
        started_at=datetime.now(UTC),
        event_digest="0" * 64,
    )
    try:
        _collect(spawn)
        receipt = _spawn_receipt(spawn, spawn.event_digest)

        assert receipt.stdout_excerpt == receipt.stderr_excerpt == ""
        assert receipt.stdout_digest == sha256_bytes(b"candidate stdout\n")
        assert receipt.stderr_digest == sha256_bytes(b"candidate stderr\n")
        assert b"candidate" not in canonical_json(receipt.model_dump(mode="json"))
    finally:
        controller.close()


@contextmanager
def _bare_spawn(code: str, *, phase: str = "replay") -> Iterator[tuple[_Spawn, socket.socket]]:
    """A ``_Spawn`` around a plain process and one end of its channel.

    The refusals below fire before any worker protocol runs, and no handler can be written that
    makes a kill fail, that lingers past its own ``done``, or that exits on its own in the
    microseconds before SIGKILL lands. The process, its process group, and its pipes are real;
    only the worker's side of the conversation is written by the test.
    """
    process = subprocess.Popen(
        [sys.executable, "-c", code],
        start_new_session=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    controller, worker = socket.socketpair()
    spawn = _Spawn(
        index=2,
        phase=phase,
        process=process,
        channel=controller,
        worker_nonce="worker-nonce",
        session_id="session-id",
        started_at=datetime.now(UTC),
        event_digest="0" * 64,
    )
    try:
        yield spawn, worker
    finally:
        # os.kill, never os.killpg: these tests replace killpg, and teardown must not use it.
        process.kill()
        process.wait(timeout=5)
        controller.close()
        worker.close()


def _killpg_refused(pgid: int, number: int) -> None:
    raise OSError(1, "Operation not permitted")


def _killpg_lost(pgid: int, number: int) -> None:
    """The signal goes nowhere: the group is gone, or the kernel dropped it."""


def test_a_process_group_kill_that_fails_is_a_kill_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """The kill is the experiment; a kill that did not happen is not a verdict."""
    monkeypatch.setattr(os, "killpg", _killpg_refused)

    with (
        _bare_spawn("import time; time.sleep(30)") as (spawn, _worker),
        pytest.raises(_AttemptFailure) as failure,
    ):
        _kill_and_wait(spawn, 5.0)

    assert failure.value.status is ExecutionStatus.KILL_ERROR
    assert failure.value.detail == "process-group SIGKILL failed"


def test_a_killed_worker_that_is_not_reaped_names_its_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The wait has a budget, and its expiry says which budget, like every other wall-clock wait."""
    monkeypatch.setattr(os, "killpg", _killpg_lost)

    with (
        _bare_spawn("import time; time.sleep(30)") as (spawn, _worker),
        pytest.raises(_AttemptFailure) as failure,
    ):
        _kill_and_wait(spawn, 0.05)

    assert failure.value.status is ExecutionStatus.WAIT_ERROR
    assert failure.value.detail == "the killed worker was not reaped within 0.05 s"


def test_a_worker_that_exited_before_the_kill_landed_is_a_wait_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exit -9 is the sentence the README rests on: a worker that ended any other way, even
    cleanly on its own before the signal arrived, was not killed at the boundary, and the
    evidence it leaves is not a crash."""
    monkeypatch.setattr(os, "killpg", _killpg_lost)

    with (
        _bare_spawn("raise SystemExit(0)") as (spawn, _worker),
        pytest.raises(_AttemptFailure) as failure,
    ):
        _kill_and_wait(spawn, 5.0)

    assert failure.value.status is ExecutionStatus.WAIT_ERROR
    assert failure.value.detail == "worker did not exit from SIGKILL"


def test_a_write_after_the_worker_died_forfeits_the_post_kill_checkpoint(tmp_path: Path) -> None:
    """The checkpoint is read twice: once at the kill, once after the worker is gone. Between
    them nothing may write, because a detached child, an exit hook, or a connection the store
    does not own would be moving the money after the crash the receipt claims to describe."""
    event = {"account_id": "acct_7", "amount_cents": 2500, "event_id": "evt_1042"}
    database = tmp_path / "post-kill.sqlite3"
    _seed_database(CREDIT, database, event)
    at_the_kill = _ledger(CREDIT, database, event)

    with sqlite3.connect(database) as connection:
        connection.execute(
            "INSERT INTO credit_ledger(event_id, account_id, amount_cents) "
            "VALUES ('evt_1042', 'acct_7', 2500)"
        )
        connection.commit()

    with pytest.raises(_AttemptFailure) as failure:
        _require_unchanged(
            CREDIT, database, event, at_the_kill, "durable checkpoint changed after worker death"
        )

    assert failure.value.status is ExecutionStatus.INTEGRITY_ERROR
    assert failure.value.integrity is IntegrityStatus.INVALID
    assert failure.value.detail == (
        "durable checkpoint changed after worker death: rows that belong to other accounts "
        "or events changed (or this event's own rows did) in credit_ledger"
    )


def test_a_probe_that_cannot_read_the_database_is_a_probe_error(tmp_path: Path) -> None:
    """Every verdict is read through this one function. A read that failed is not a state, and
    the run has to stop on it instead of carrying on with whatever it half-saw. Both arms of the
    refusal are staged: a corrupt file answers with a sqlite3 error, a file that is no longer
    there with an OSError, and the engine turns each into the same refusal."""
    event = {"account_id": "acct_7", "amount_cents": 2500, "event_id": "evt_1042"}
    database = tmp_path / "unreadable.sqlite3"
    _seed_database(CREDIT, database, event)
    assert _read_content(CREDIT, database, event)["tables"]

    database.write_bytes(b"this is not a database" + bytes(200))
    with pytest.raises(_AttemptFailure) as corrupt:
        _read_content(CREDIT, database, event)
    assert corrupt.value.status is ExecutionStatus.PROBE_ERROR
    assert corrupt.value.detail == (
        "read-only state probe failed (the database file has no SQLite header)"
    )

    database.unlink()
    with pytest.raises(_AttemptFailure) as gone:
        _read_content(CREDIT, database, event)
    assert gone.value.status is ExecutionStatus.PROBE_ERROR
    # The errno text is the operating system's; the sentence around it is the engine's.
    assert gone.value.detail.startswith("read-only state probe failed ([Errno 2] ")


@pytest.mark.parametrize(
    "pragma",
    [
        "application_id",
        "auto_vacuum",
        "default_cache_size",
        "encoding",
        "freelist_count",
        "journal_mode",
        "page_size",
        "schema_version",
        "user_version",
    ],
)
def test_every_named_header_pragma_is_read_into_the_content(tmp_path: Path, pragma: str) -> None:
    """One test per durable header field the probe names, because the suite caught a dropped
    pragma only for `freelist_count` and `schema_version`: every other name could fall out of the
    read and every end-to-end test still passed. The names are written out here rather than taken
    from `_HEADER_PRAGMAS`, because a list that supplies its own test cases cannot notice a
    missing one. `_file_identity` reads the raw first 100 bytes beside this, which covers some of
    the same fields twice; the overlap is deliberate and neither read replaces the other."""
    assert pragma in _HEADER_PRAGMAS
    event = {"account_id": "acct_7", "amount_cents": 2500, "event_id": "evt_1042"}
    database = tmp_path / "header.sqlite3"
    _seed_database(CREDIT, database, event)

    header = cast(dict[str, object], _read_content(CREDIT, database, event)["header"])

    assert pragma in header
    with closing(_read_only(database)) as connection:
        assert header[pragma] == connection.execute(f"PRAGMA {pragma}").fetchone()[0]


_XATTR_NAME = "user.nemisis.seen"


def _set_xattr(path: Path, name: str) -> None:
    """Set one extended attribute, through whichever door this platform has.

    The same two doors `_xattrs` reads through, and the same two the packaged `xattr` handler in
    the zoo uses: CPython builds `os.setxattr` only on Linux, and on macOS the libc call is
    reached through ctypes.
    """
    setxattr = getattr(os, "setxattr", None)
    if setxattr is not None:
        setxattr(path, name, b"1")
        return
    libc = ctypes.CDLL(None, use_errno=True)
    call = libc.setxattr
    call.argtypes = [
        ctypes.c_char_p,
        ctypes.c_char_p,
        ctypes.c_void_p,
        ctypes.c_size_t,
        ctypes.c_uint32,
        ctypes.c_int,
    ]
    if call(os.fsencode(path), name.encode(), b"1", 1, 0, 0) != 0:
        raise OSError(ctypes.get_errno(), f"setxattr failed for {path}")


def test_xattrs_does_not_name_an_attribute_that_was_never_set(tmp_path: Path) -> None:
    """The guard has to answer, not just never object: a reader that reports nothing at all is
    the shape the third hostile review found (on macOS, CPython has no `os.listxattr`, so the
    whole guard was inert and every branch of it was dead)."""
    path = tmp_path / "plain"
    path.write_bytes(b"")

    assert _XATTR_NAME not in _xattrs(path)


def test_xattrs_names_an_extended_attribute_that_was_set(tmp_path: Path) -> None:
    """An extended attribute is durable state no store commit made, invisible to every PRAGMA
    and every row. The read must add exactly the name that was set, in sorted order, so two
    worlds that differ only by a flag are two different entries."""
    path = tmp_path / "flagged"
    path.write_bytes(b"")
    before = _xattrs(path)

    _set_xattr(path, _XATTR_NAME)

    assert _xattrs(path) == sorted([*before, _XATTR_NAME])


def test_xattrs_raises_instead_of_answering_for_a_path_it_cannot_read(tmp_path: Path) -> None:
    """A read that failed must not come back as "no attributes": the engine before the third
    hostile round swallowed the error and returned an empty list, which is indistinguishable
    from a clean file and made the whole channel invisible."""
    with pytest.raises(OSError) as failure:
        _xattrs(tmp_path / "not-there")

    assert failure.value.errno == errno.ENOENT
