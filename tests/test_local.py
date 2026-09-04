from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import pytest

import nemisis.local as local_module
from nemisis.local import source_commit, verify_local
from nemisis.models import ArtifactStatus, Classification, Outcome, TruthLabel


def test_local_fixture_exposes_the_incomplete_candidate(tmp_path: Path) -> None:
    result = verify_local(output_root=tmp_path)
    manifest = result.manifest
    by_test = {cell.test_id: cell for cell in manifest.matrix}

    assert manifest.truth_label is TruthLabel.FIXTURE
    assert manifest.artifact.status is ArtifactStatus.REJECTED
    assert by_test["baseline.reserve"].classification is Classification.SUPPORTED
    assert by_test["baseline.out-of-stock"].classification is Classification.SUPPORTED
    assert by_test["adversarial.duplicate"].base_outcome is Outcome.ASSERTION_FAIL
    assert by_test["adversarial.duplicate"].candidate_outcome is Outcome.PASS
    assert by_test["adversarial.duplicate"].classification is Classification.SUPPORTED
    assert by_test["adversarial.crash-retry"].classification is Classification.UNRESOLVED
    assert {world.parent_world_id for world in manifest.worlds} == {
        f"prepared:{manifest.request.base_digest[:16]}"
    }
    assert {world.verification_bundle_digest for world in manifest.worlds} == {
        manifest.bundle.digest
    }
    assert {receipt.verification_bundle_digest for receipt in manifest.executions} == {
        manifest.bundle.digest
    }
    assert result.report_path.is_file()
    report = result.report_path.read_text()
    assert "LOCAL FIXTURE" in report
    assert manifest.bundle.digest in report
    assert "Execution receipts" in report
    persisted = json.loads(result.manifest_path.read_text())
    assert persisted["artifact"]["status"] == "REJECTED"


def test_installed_wheel_does_not_claim_the_callers_repository(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_module = tmp_path / "site-packages" / "nemisis" / "local.py"
    monkeypatch.setattr(local_module, "__file__", str(fake_module))
    assert source_commit() is None


@pytest.mark.skipif(os.name != "posix", reason="process-group isolation requires POSIX")
def test_local_runner_timeout_kills_and_reaps_its_private_process_group(tmp_path: Path) -> None:
    child_pid_path = tmp_path / "child.pid"
    script = """
import os
import subprocess
import sys
import time

child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
with open(sys.argv[1], "w", encoding="utf-8") as output:
    output.write(str(child.pid))
print(os.getpid(), os.getpgrp(), os.getsid(0), flush=True)
time.sleep(60)
"""

    exit_code, stdout, stderr, timed_out = local_module._run_process(
        [sys.executable, "-c", script, str(child_pid_path)],
        cwd=tmp_path,
        env={"PATH": os.environ.get("PATH", "")},
        timeout_seconds=1,
    )

    runner_pid, process_group, session = map(int, stdout.splitlines()[0].split())
    child_pid = int(child_pid_path.read_text())
    assert timed_out is True
    assert exit_code is None
    assert stderr == ""
    assert runner_pid == process_group == session
    deadline = time.monotonic() + 3
    while _pid_exists(child_pid) and time.monotonic() < deadline:
        time.sleep(0.01)
    assert not _pid_exists(child_pid)


def _pid_exists(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def test_verify_refuses_non_posix_platforms_plainly(monkeypatch: pytest.MonkeyPatch) -> None:
    import os

    import nemisis.local as local_module

    monkeypatch.setattr(os, "name", "nt")
    with pytest.raises(ValueError, match="POSIX Python 3.12\\+"):
        local_module.verify_local(output_root=Path("/nonexistent"))
