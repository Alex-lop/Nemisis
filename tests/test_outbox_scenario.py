"""``sqlite-outbox-v1``: exactly-once send through a transactional outbox, decided by CrashCheck.

Its own subject (bytes handed to one channel), its own effect row (an outbox row standing for the
email or the webhook), and its own predicate (one outbox row, one marker, 512 bytes). Nothing here
is a renamed credit or a renamed reservation.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

import nemisis.cli as cli
from nemisis.crash_fixture import load_event, load_issue, materialize_fixture
from nemisis.crash_models import CrashObservation, CrashVerdict, ExecutionStatus, WorldRole
from nemisis.crashcheck import CrashCheckError, accept_contract, check, initialize, replay
from nemisis.scenarios import SCENARIOS, scenario_for
from nemisis.scenarios.sqlite_outbox_v1 import INITIAL_SENT_BYTES
from nemisis.scenarios.sqlite_outbox_v1 import SCENARIO as OUTBOX

SCENARIO_ID = "sqlite-outbox-v1"
BUGGY = OUTBOX.ref("buggy")
GREEN = OUTBOX.ref("misleading-green")
ATOMIC = OUTBOX.ref("atomic")
MARK_FIRST = OUTBOX.ref("mark-first")
TARGET = "app.outbox:dispatch_outbox"


def _tree(tmp_path: Path, name: str, handler_source: str) -> Path:
    root = tmp_path / name
    (root / "app").mkdir(parents=True)
    (root / "app" / "__init__.py").write_text('"""app"""\n', encoding="utf-8")
    (root / "app" / "outbox.py").write_text(handler_source, encoding="utf-8")
    return root


def test_registry_holds_the_outbox_scenario_with_its_own_subject_and_predicate() -> None:
    assert scenario_for(SCENARIO_ID) is OUTBOX
    assert SCENARIOS[SCENARIO_ID] is OUTBOX
    event = load_event(OUTBOX)
    assert event == {"channel": "billing-webhook", "event_id": "msg-1", "payload_bytes": 512}
    assert OUTBOX.initial_total(event) == INITIAL_SENT_BYTES == 0
    assert OUTBOX.effect_delta(event) == 512
    assert OUTBOX.repro_dir == "double-send"
    assert OUTBOX.target == TARGET
    assert "send_and_mark(channel, event_id, payload_bytes)" in OUTBOX.store_remedy
    assert set(OUTBOX.store_operations) == {"send", "mark_sent", "send_and_mark"}
    assert OUTBOX.format_subject(512) == "512 bytes"
    assert OUTBOX.format_subject(1) == "1 byte"
    assert "dispatch_outbox" in load_issue(OUTBOX)


def test_the_hero_story_holds_for_a_send(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Base reproduces, the agent's green rewrite still double-sends, the atomic fix is proven."""
    artifacts = tmp_path / "artifacts"
    monkeypatch.setenv("NEMISIS_ARTIFACT_ROOT", str(artifacts))

    result = check(BUGGY, GREEN, SCENARIO_ID, corrected=ATOMIC, mode="local")

    assert result.verdict is CrashVerdict.PATCH_FAILED_STILL_REPRODUCES, result.summary
    assert "double send (1024 bytes on the channel, expected 512 bytes)" in result.summary
    by_role = {
        role: {a.observation for a in result.attempts if a.role is role} for role in WorldRole
    }
    assert by_role[WorldRole.BASE] == {CrashObservation.DUPLICATE_EFFECT}
    assert by_role[WorldRole.CANDIDATE] == {CrashObservation.DUPLICATE_EFFECT}
    assert by_role[WorldRole.CORRECTED] == {CrashObservation.EXACTLY_ONCE}
    candidate = next(a for a in result.attempts if a.role is WorldRole.CANDIDATE)
    assert candidate.pre_crash_snapshot is not None
    assert candidate.pre_crash_snapshot.subject_total == 0
    assert candidate.checkpoint_snapshot is not None
    assert candidate.checkpoint_snapshot.subject_total == 512
    assert candidate.final_snapshot is not None
    assert (
        candidate.final_snapshot.subject_total,
        candidate.final_snapshot.event_effect_count,
        candidate.final_snapshot.event_effect_total,
    ) == (1024, 2, 1024)
    assert candidate.effect_delta == 512
    assert [sweep.role for sweep in result.sweeps] == [WorldRole.CORRECTED]
    assert result.sweeps[0].census.first_delivery_operations == ("send_and_mark",)
    assert result.artifacts["capsule"].startswith("repros/double-send/")
    capsule = json.loads((artifacts / result.artifacts["capsule"]).read_text(encoding="utf-8"))
    assert capsule["event"] == {
        "channel": "billing-webhook",
        "event_id": "msg-1",
        "payload_bytes": 512,
    }
    assert capsule["effect_delta"] == 512
    assert capsule["scenario_id"] == SCENARIO_ID
    report = (artifacts / result.artifacts["report"]).read_text(encoding="utf-8")
    assert "Expected sent payload after one delivery" in report
    assert "<strong>512 bytes</strong>" in report
    assert "<strong>1024 bytes</strong>" in report
    assert "send rows 2 / marker 1" in report
    assert "$" not in report.split("<details")[0]
    assert cli._exit_code(result.verdict) == 1

    replayed = replay(artifacts / result.artifacts["capsule"], BUGGY, role="base")
    assert replayed.verdict is CrashVerdict.BUG_REPRODUCED
    proven = replay(artifacts / result.artifacts["capsule"], ATOMIC, role="corrected")
    assert proven.verdict is CrashVerdict.FIX_PROVEN_FOR_THIS_CAPSULE
    assert "exactly 512 bytes on the channel, one outbox row, and one marker" in proven.summary


def test_mark_first_loses_the_send_and_the_summary_says_so(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("NEMISIS_ARTIFACT_ROOT", str(tmp_path / "artifacts"))

    result = check(BUGGY, MARK_FIRST, SCENARIO_ID, mode="local")

    assert result.verdict is CrashVerdict.PATCH_FAILED_INVARIANT_BROKEN, result.summary
    assert "commit 1 of 2 (mark_sent)" in result.summary
    assert "0 bytes on the channel instead of 512 bytes (0 outbox rows, 1 marker)" in result.summary
    assert "the message is lost" in result.summary
    sweep = result.sweeps[0]
    assert sweep.census.first_delivery_operations == ("mark_sent", "send")
    assert [a.observation for a in sweep.attempts] == [
        CrashObservation.INVARIANT_FAILED,
        CrashObservation.EXACTLY_ONCE,
    ]
    assert cli._exit_code(result.verdict) == 1


OTHER_CHANNEL = """def dispatch_outbox(store, event):
    store.send_and_mark("other-channel", event["event_id"], event["payload_bytes"])
"""


def test_raw_sql_and_look_alike_arguments_get_the_outbox_words(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("NEMISIS_ARTIFACT_ROOT", str(tmp_path / "artifacts"))

    raw = check(BUGGY, OUTBOX.ref("raw-sql"), SCENARIO_ID, mode="local")
    assert raw.verdict is CrashVerdict.EVIDENCE_INCOMPLETE
    assert "without a single OutboxStore commit" in raw.summary
    assert "sent payload 512 bytes, 1 send row(s), 1 marker" in raw.summary
    assert "store.send_and_mark(channel, event_id, payload_bytes)" in raw.summary
    assert "credit" not in raw.summary
    assert "reservation" not in raw.summary

    other = check(BUGGY, _tree(tmp_path, "other-channel", OTHER_CHANNEL), SCENARIO_ID, mode="local")
    assert other.verdict is CrashVerdict.EVIDENCE_INCOMPLETE
    assert {a.execution_status for a in other.attempts if a.role is WorldRole.CANDIDATE} == {
        ExecutionStatus.CHECKPOINT_NOT_REACHED
    }
    assert "raised ValueError" in other.summary


@pytest.mark.parametrize(
    ("variant", "verdict", "fragment"),
    [
        ("leftover-send", CrashVerdict.PATCH_FAILED_STILL_REPRODUCES, "with no crash at all"),
        ("never-marks", CrashVerdict.PATCH_FAILED_STILL_REPRODUCES, "durable double send"),
        ("shadow-table", CrashVerdict.EVIDENCE_INCOMPLETE, "the schema changed"),
        ("tail-bytes", CrashVerdict.EVIDENCE_INCOMPLETE, "past the database file's last page"),
    ],
)
def test_each_packaged_zoo_tree_earns_its_own_verdict(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    variant: str,
    verdict: CrashVerdict,
    fragment: str,
) -> None:
    """The credit zoo, spelled for a send: each tree is the patch a reviewer would have signed."""
    monkeypatch.setenv("NEMISIS_ARTIFACT_ROOT", str(tmp_path / "artifacts"))

    result = check(BUGGY, OUTBOX.ref(variant), SCENARIO_ID, mode="local")

    assert result.verdict is verdict, result.summary
    assert fragment in result.summary, result.summary


def test_init_accept_and_check_bind_an_outbox_contract(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.chdir(workspace)
    monkeypatch.setenv("NEMISIS_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    issue = workspace / "issue.md"
    issue.write_text(load_issue(OUTBOX) + "\nLocal contract.\n", encoding="utf-8")

    config = initialize(issue, TARGET, BUGGY, SCENARIO_ID)
    payload = json.loads(config.read_bytes())
    assert payload["status"] == "DRAFT" and payload["scenario_id"] == SCENARIO_ID
    contract = accept_contract(payload["contract"]["digest"], config)
    assert contract.scenario_id == SCENARIO_ID and contract.target == TARGET

    result = check(BUGGY, ATOMIC, config, mode="local")
    assert result.verdict is CrashVerdict.FIX_PROVEN_FOR_THIS_CAPSULE

    with pytest.raises(CrashCheckError, match="pass --scenario sqlite-outbox-v1"):
        check(BUGGY, ATOMIC, "sqlite-credit-v1", mode="local")
    with pytest.raises(CrashCheckError, match="pass --scenario sqlite-outbox-v1"):
        initialize(issue, TARGET, BUGGY, "sqlite-inventory-v1")


def test_cli_infers_the_scenario_from_a_fixture_base_and_names_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        ["nemisis", "check", "--base", BUGGY, "--candidate", GREEN, "--output-dir", str(tmp_path)],
    )

    with pytest.raises(SystemExit) as error:
        cli.main()

    assert error.value.code == 1
    out = capsys.readouterr().out
    assert "verdict: PATCH_FAILED_STILL_REPRODUCES" in out
    assert "timeline: 512 bytes durable -> SIGKILL -> fresh worker -> 1024 bytes" in out
    assert "$" not in out


def test_export_names_the_outbox_base_in_its_next_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "mine"
    monkeypatch.setattr(sys, "argv", ["nemisis", "export", GREEN, str(out)])

    cli.main()

    lines = capsys.readouterr().out.splitlines()
    assert lines[2] == f"edit: {out.resolve() / 'app' / 'outbox.py'}"
    assert lines[3].startswith(f"next: nemisis check --base {BUGGY} ")
    assert (
        materialize_fixture(BUGGY, tmp_path / "again").tree_digest == OUTBOX.tree_digests["buggy"]
    )


def test_outbox_unit_test_is_green_for_every_tree_that_can_run_it(tmp_path: Path) -> None:
    """The hero trees, mark-first, and never-marks are all green on the repository's own test:
    that is why the bug ships. The raw-SQL, shadow-table and tail-bytes trees reach for the
    store's database, which the in-memory store does not have, and leftover-send sends twice."""
    for variant in (*OUTBOX.hero_variants, "mark-first", "never-marks"):
        tree = materialize_fixture(OUTBOX.ref(variant), tmp_path / variant).path
        run = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests"],
            cwd=tree,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        assert run.returncode == 0, run.stdout + run.stderr
        assert re.search(r"1 passed", run.stdout), run.stdout
