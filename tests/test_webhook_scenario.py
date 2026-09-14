"""``sqlite-webhook-idempotency-v1``: the Stripe-shaped redelivery, decided by CrashCheck.

Its own seed (one founder seat, not zero and not ten), its own subject (seats, not money and not
stock), its own marker (an idempotency key), and its own zoo: the two shapes that keep their
durable state where no kill point reaches it ship as trees here, not only as generated handlers.
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
from nemisis.crash_models import CrashObservation, CrashVerdict, WorldRole
from nemisis.crashcheck import CrashCheckError, accept_contract, check, initialize, replay
from nemisis.redteam import WEBHOOK as GRAMMAR
from nemisis.redteam import Op, oracle, render
from nemisis.scenarios import SCENARIOS, scenario_for
from nemisis.scenarios.sqlite_webhook_idempotency_v1 import INITIAL_SEATS
from nemisis.scenarios.sqlite_webhook_idempotency_v1 import SCENARIO as WEBHOOK

SCENARIO_ID = "sqlite-webhook-idempotency-v1"
BUGGY = WEBHOOK.ref("buggy")
GREEN = WEBHOOK.ref("misleading-green")
ATOMIC = WEBHOOK.ref("atomic")
MARK_FIRST = WEBHOOK.ref("mark-first")
RAW_SQL = WEBHOOK.ref("raw-sql")
SHADOW_TABLE = WEBHOOK.ref("shadow-table")
TARGET = "app.webhooks:handle_webhook"


def test_registry_holds_the_webhook_scenario_with_its_own_seed_subject_and_marker() -> None:
    assert set(SCENARIOS) == {"sqlite-credit-v1", "sqlite-inventory-v1", SCENARIO_ID}
    assert scenario_for(SCENARIO_ID) is WEBHOOK
    event = load_event(WEBHOOK)
    assert event == {"event_id": "evt_whk_88", "seats": 3, "workspace_id": "ws_acme"}
    assert WEBHOOK.initial_total(event) == INITIAL_SEATS == 1
    assert WEBHOOK.effect_delta(event) == 3
    assert WEBHOOK.repro_dir == "double-grant"
    assert WEBHOOK.target == TARGET
    assert WEBHOOK.scalar_name == "seats"
    assert "grant_and_mark(workspace_id, event_id, seats)" in WEBHOOK.store_remedy
    assert set(WEBHOOK.store_operations) == {"grant", "mark_processed", "grant_and_mark"}
    assert WEBHOOK.format_subject(4) == "4 seats"
    assert WEBHOOK.format_subject(1) == "1 seat"
    assert WEBHOOK.variants == ("buggy", "misleading-green", "atomic", *WEBHOOK.zoo_variants)
    assert WEBHOOK.zoo_variants == ("mark-first", "raw-sql", "shadow-table")
    assert "handle_webhook" in load_issue(WEBHOOK)


def test_the_hero_story_holds_for_a_redelivered_webhook(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Base reproduces, the agent's green rewrite still double-grants, the atomic fix is proven."""
    artifacts = tmp_path / "artifacts"
    monkeypatch.setenv("NEMISIS_ARTIFACT_ROOT", str(artifacts))

    result = check(BUGGY, GREEN, SCENARIO_ID, corrected=ATOMIC, mode="local")

    assert result.verdict is CrashVerdict.PATCH_FAILED_STILL_REPRODUCES, result.summary
    assert "double grant (7 seats, expected 4 seats)" in result.summary
    by_role = {
        role: {a.observation for a in result.attempts if a.role is role} for role in WorldRole
    }
    assert by_role[WorldRole.BASE] == {CrashObservation.DUPLICATE_EFFECT}
    assert by_role[WorldRole.CANDIDATE] == {CrashObservation.DUPLICATE_EFFECT}
    assert by_role[WorldRole.CORRECTED] == {CrashObservation.EXACTLY_ONCE}
    candidate = next(a for a in result.attempts if a.role is WorldRole.CANDIDATE)
    assert candidate.pre_crash_snapshot is not None
    assert candidate.pre_crash_snapshot.subject_total == 1
    assert candidate.checkpoint_snapshot is not None
    assert candidate.checkpoint_snapshot.subject_total == 4
    assert candidate.final_snapshot is not None
    assert (
        candidate.final_snapshot.subject_total,
        candidate.final_snapshot.event_effect_count,
        candidate.final_snapshot.event_effect_total,
    ) == (7, 2, 6)
    assert candidate.effect_delta == 3
    assert [sweep.role for sweep in result.sweeps] == [WorldRole.CORRECTED]
    assert result.sweeps[0].census.first_delivery_operations == ("grant_and_mark",)
    assert result.artifacts["capsule"].startswith("repros/double-grant/")
    capsule = json.loads((artifacts / result.artifacts["capsule"]).read_text(encoding="utf-8"))
    assert capsule["event"] == {"event_id": "evt_whk_88", "seats": 3, "workspace_id": "ws_acme"}
    assert capsule["effect_delta"] == 3
    assert capsule["scenario_id"] == SCENARIO_ID
    report = (artifacts / result.artifacts["report"]).read_text(encoding="utf-8")
    assert "Expected seat count after one delivery" in report
    assert "<strong>4 seats</strong>" in report
    assert "<strong>7 seats</strong>" in report
    assert "grant rows 2 / marker 1" in report
    assert "$" not in report.split("<details")[0]
    assert cli._exit_code(result.verdict) == 1

    replayed = replay(artifacts / result.artifacts["capsule"], BUGGY, role="base")
    assert replayed.verdict is CrashVerdict.BUG_REPRODUCED
    proven = replay(artifacts / result.artifacts["capsule"], ATOMIC, role="corrected")
    assert proven.verdict is CrashVerdict.FIX_PROVEN_FOR_THIS_CAPSULE
    assert "exactly 4 seats, one grant, and one idempotency key" in proven.summary


def test_mark_first_loses_the_grant_and_the_summary_says_so(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("NEMISIS_ARTIFACT_ROOT", str(tmp_path / "artifacts"))

    result = check(BUGGY, MARK_FIRST, SCENARIO_ID, mode="local")

    assert result.verdict is CrashVerdict.PATCH_FAILED_INVARIANT_BROKEN, result.summary
    assert "commit 1 of 2 (mark_processed)" in result.summary
    assert "1 seat instead of 4 seats (0 grant rows, 1 idempotency key)" in result.summary
    assert "the purchase is lost" in result.summary
    sweep = result.sweeps[0]
    assert sweep.census.first_delivery_operations == ("mark_processed", "grant")
    assert [a.observation for a in sweep.attempts] == [
        CrashObservation.INVARIANT_FAILED,
        CrashObservation.EXACTLY_ONCE,
    ]
    assert cli._exit_code(result.verdict) == 1


def test_the_packaged_zoo_keeps_its_durable_state_out_of_reach_and_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Both are correct by inspection and neither earns a verdict: the grant they make has no
    kill point, so the remedy names the store call that would have one."""
    monkeypatch.setenv("NEMISIS_ARTIFACT_ROOT", str(tmp_path / "artifacts"))

    raw = check(BUGGY, RAW_SQL, SCENARIO_ID, mode="local")
    assert raw.verdict is CrashVerdict.EVIDENCE_INCOMPLETE, raw.summary
    assert "without a single WebhookStore commit" in raw.summary
    assert "seat count 4 seats, 1 grant row(s), 1 marker" in raw.summary
    assert "store.grant_and_mark(workspace_id, event_id, seats)" in raw.summary
    assert "credit" not in raw.summary and "stock" not in raw.summary
    assert cli._exit_code(raw.verdict) == 2

    shadow = check(BUGGY, SHADOW_TABLE, SCENARIO_ID, mode="local")
    assert shadow.verdict is CrashVerdict.EVIDENCE_INCOMPLETE, shadow.summary
    assert "the schema changed" in shadow.summary
    assert "store.grant_and_mark(workspace_id, event_id, seats)" in shadow.summary


def test_init_accept_and_check_bind_a_webhook_contract(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.chdir(workspace)
    monkeypatch.setenv("NEMISIS_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    issue = workspace / "issue.md"
    issue.write_text(load_issue(WEBHOOK) + "\nLocal contract.\n", encoding="utf-8")

    config = initialize(issue, TARGET, BUGGY, SCENARIO_ID)
    payload = json.loads(config.read_bytes())
    assert payload["status"] == "DRAFT" and payload["scenario_id"] == SCENARIO_ID
    contract = accept_contract(payload["contract"]["digest"], config)
    assert contract.scenario_id == SCENARIO_ID and contract.target == TARGET

    result = check(BUGGY, ATOMIC, config, mode="local")
    assert result.verdict is CrashVerdict.FIX_PROVEN_FOR_THIS_CAPSULE

    with pytest.raises(CrashCheckError, match=f"pass --scenario {SCENARIO_ID}"):
        check(BUGGY, ATOMIC, "sqlite-credit-v1", mode="local")
    with pytest.raises(CrashCheckError, match=f"pass --scenario {SCENARIO_ID}"):
        initialize(issue, TARGET, BUGGY, "sqlite-inventory-v1")


def test_cli_infers_the_scenario_from_a_fixture_base_and_names_seats(
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
    assert "timeline: 4 seats durable -> SIGKILL -> fresh worker -> 7 seats" in out
    assert "$" not in out


def test_export_names_the_webhook_base_in_its_next_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "mine"
    monkeypatch.setattr(sys, "argv", ["nemisis", "export", GREEN, str(out)])

    cli.main()

    lines = capsys.readouterr().out.splitlines()
    assert lines[2] == f"edit: {out.resolve() / 'app' / 'webhooks.py'}"
    assert lines[3].startswith(f"next: nemisis check --base {BUGGY} ")
    assert (
        materialize_fixture(BUGGY, tmp_path / "again").tree_digest == WEBHOOK.tree_digests["buggy"]
    )


def test_the_generator_speaks_the_webhook_vocabulary() -> None:
    """The grammar only changes its spelling; the oracle that judges it is unchanged."""
    module = render((Op.GUARD, Op.ATOMIC, Op.TABLE), GRAMMAR, helper=True)
    assert "def handle_webhook(store, event):\n    _deliver(store, event)\n" in module
    assert 'store.grant_and_mark(event["workspace_id"], event["event_id"], event["seats"])' in (
        module
    )
    assert "CREATE TABLE IF NOT EXISTS dedup" in module
    assert "UPDATE workspaces SET seats = seats + ?" in render((Op.RAW_SQL,), GRAMMAR)
    assert oracle((Op.ATOMIC,))[0].value == CrashVerdict.FIX_PROVEN_FOR_THIS_CAPSULE.value
    assert oracle((Op.GUARD, Op.EFFECT, Op.MARK))[0].value == (
        CrashVerdict.PATCH_FAILED_STILL_REPRODUCES.value
    )


def test_webhook_unit_test_is_green_for_every_hero_tree(tmp_path: Path) -> None:
    for variant in (*WEBHOOK.hero_variants, "mark-first"):
        tree = materialize_fixture(WEBHOOK.ref(variant), tmp_path / variant).path
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
