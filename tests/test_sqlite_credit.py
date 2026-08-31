from __future__ import annotations

import os
import signal
import socket
import subprocess
import sys
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from time import monotonic, sleep

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
from nemisis.sqlite_credit import (
    AnchorResolutionError,
    _AttemptFailure,
    _cleanup,
    _collect,
    _receive,
    _Spawn,
    _spawn_receipt,
    bind_anchor,
    execute_attempt,
)


def test_anchor_resolution_distinguishes_zero_one_and_multiple(tmp_path: Path) -> None:
    contract = _audited_contract()
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
    contract = _audited_contract()
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
    contract = _audited_contract()
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


def test_receive_preserves_a_coalesced_second_frame() -> None:
    controller, worker = socket.socketpair()
    buffer = bytearray()
    try:
        worker.sendall(
            canonical_json({"type": "hello"}) + b"\n" + canonical_json({"type": "commit"}) + b"\n"
        )

        assert _receive(controller, buffer, 1) == {"type": "hello"}
        assert _receive(controller, buffer, 1) == {"type": "commit"}
        assert not buffer
    finally:
        controller.close()
        worker.close()


def _execute_fixture(
    tmp_path: Path, fixture_ref: str, fault_boundary: FaultBoundary
) -> AttemptReceipt:
    contract = _audited_contract()
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
        text=True,
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
        text=True,
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
        text=True,
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
