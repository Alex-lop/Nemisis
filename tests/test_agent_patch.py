"""Nemotron as the coding agent: propose-patch writes an ordinary candidate, check judges it."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import cast

import pytest

import nemisis.agent_patch as agent_patch_module
import nemisis.cli as cli
from nemisis.agent_patch import RECEIPT_PATH, PatchError, describe, propose_patch
from nemisis.crash_fixture import (
    BUGGY_REF,
    MISLEADING_GREEN_REF,
    SCENARIO_ID,
    load_issue,
    materialize_fixture,
)
from nemisis.crash_models import CrashVerdict, PatchProposal
from nemisis.crashcheck import CrashCheckError, check
from nemisis.models import TruthLabel
from nemisis.nemotron import DEFAULT_MODEL_ID, NemotronClient, _Client

ATOMIC_MODULE = '''"""Account-credit handler, fixed."""

from typing import Protocol, TypedDict


class CreditEvent(TypedDict):
    event_id: str
    account_id: str
    amount_cents: int


class CreditStore(Protocol):
    def processed(self, event_id: str) -> bool: ...

    def credit(self, account_id: str, event_id: str, amount_cents: int) -> None: ...

    def mark_processed(self, event_id: str) -> None: ...

    def credit_and_mark(self, account_id: str, event_id: str, amount_cents: int) -> None: ...


def apply_credit(store: CreditStore, event: CreditEvent) -> None:
    store.credit_and_mark(event["account_id"], event["event_id"], event["amount_cents"])
'''

MARK_FIRST_MODULE = """def apply_credit(store, event):
    event_id = event["event_id"]
    if store.processed(event_id):
        return
    store.mark_processed(event_id)
    store.credit(event["account_id"], event_id, event["amount_cents"])
"""


class _Models:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def list(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        return {
            "data": [
                {
                    "id": DEFAULT_MODEL_ID,
                    "status": "active",
                    "architecture": {"modality": "text->text"},
                    "supported_features": ["structured_outputs"],
                }
            ]
        }


class _Completions:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        return {"choices": [{"message": {"content": json.dumps(self.payload), "refusal": None}}]}


class _Chat:
    def __init__(self, completions: _Completions) -> None:
        self.completions = completions


class _FakeClient:
    def __init__(
        self, module_source: str, rationale: str = "Commit credit and marker together."
    ) -> None:
        self.models = _Models()
        self.chat = _Chat(_Completions({"module_source": module_source, "rationale": rationale}))


def _adapter(fake: _FakeClient) -> NemotronClient:
    return NemotronClient(client=cast(_Client, fake))


@pytest.fixture
def issue(tmp_path: Path) -> Path:
    path = tmp_path / "issue.md"
    path.write_text(load_issue(), encoding="utf-8")
    return path


def test_model_writes_a_candidate_tree_and_the_prompt_is_checker_blind(
    issue: Path, tmp_path: Path
) -> None:
    fake = _FakeClient(ATOMIC_MODULE)
    out = tmp_path / "nemotron-candidate"

    proposal = propose_patch(issue, BUGGY_REF, out, client=_adapter(fake))

    assert (out / "app" / "credits.py").read_text(encoding="utf-8") == ATOMIC_MODULE
    assert (out / "tests" / "test_credits.py").is_file()
    receipt = PatchProposal.model_validate_json((out / RECEIPT_PATH).read_bytes())
    assert receipt == proposal
    assert receipt.model_call.truth_label is TruthLabel.MOCKED
    assert receipt.handler_path == "app/credits.py"
    assert receipt.candidate_tree_digest != receipt.base_tree_digest
    messages = cast(list[dict[str, str]], fake.chat.completions.calls[0]["messages"])
    payload = json.loads(messages[1]["content"])
    assert set(payload) == {"bug_report", "module_source", "storage_api"}
    assert "Duplicate account credit" in payload["bug_report"]
    assert "def apply_credit" in payload["module_source"]
    assert "credit_and_mark" in payload["storage_api"]
    # The base module is sent verbatim (its docstring names the product); everything Nemisis adds
    # around it must say nothing about how the checker kills or judges.
    nemisis_words = (
        messages[0]["content"] + payload["bug_report"] + payload["storage_api"]
    ).lower()
    for forbidden in ("sigkill", "capsule", "kill", "crashcheck", "boundary", "verdict", "hunt"):
        assert forbidden not in nemisis_words, forbidden
    serialized = receipt.model_dump_json()
    assert "def apply_credit" not in serialized
    assert "Duplicate account credit" not in serialized
    assert "MOCKED" in describe(proposal)


def test_model_written_fix_is_proven_and_credited_as_the_author(
    issue: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = tmp_path / "candidate"
    propose_patch(issue, BUGGY_REF, out, client=_adapter(_FakeClient(ATOMIC_MODULE)))
    artifacts = tmp_path / "artifacts"
    monkeypatch.setenv("NEMISIS_ARTIFACT_ROOT", str(artifacts))

    result = check(BUGGY_REF, out, SCENARIO_ID, mode="local")

    assert result.verdict is CrashVerdict.FIX_PROVEN_FOR_THIS_CAPSULE
    assert result.candidate_author is not None
    assert result.candidate_author.model_call.truth_label is TruthLabel.MOCKED
    assert result.candidate_author.candidate_tree_digest == result.bindings[1].tree_digest
    manifest = json.loads((artifacts / result.artifacts["manifest"]).read_text(encoding="utf-8"))
    assert manifest["result"]["candidate_author"]["model_call"]["truth_label"] == "MOCKED"
    report = (artifacts / result.artifacts["report"]).read_text(encoding="utf-8")
    assert "Candidate author · MOCKED Nemotron receipt" in report
    assert "not from the model" in report


def test_model_written_mark_first_patch_fails_the_sweep(
    issue: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The story the tool exists for: the AI agent's patch looks plausible and loses money."""
    out = tmp_path / "candidate"
    propose_patch(issue, BUGGY_REF, out, client=_adapter(_FakeClient(MARK_FIRST_MODULE)))
    monkeypatch.setenv("NEMISIS_ARTIFACT_ROOT", str(tmp_path / "artifacts"))

    result = check(BUGGY_REF, out, SCENARIO_ID, mode="local")

    assert result.verdict is CrashVerdict.PATCH_FAILED_INVARIANT_BROKEN
    assert "mark_processed" in result.summary
    assert result.candidate_author is not None


@pytest.mark.parametrize(
    ("module", "message"),
    [
        ("import sqlite3\n\ndef apply_credit(store, event):\n    pass\n", "import is not allowed"),
        ("def apply_credit(store, event):\n    store._database\n", "private attribute"),
        ("def apply_credit(store, event):\n    open('x')\n", "dangerous builtin"),
        ("def apply_credit(store, event, extra=None):\n    pass\n", "exact apply_credit"),
        ("async def apply_credit(store, event):\n    pass\n", "exactly one synchronous"),
        ("def other(store, event):\n    pass\n", "exactly one synchronous"),
        ("def apply_credit(store, event:\n", "not valid Python"),
        (
            "import os as typing\n\ndef apply_credit(store, event):\n    pass\n",
            "import is not allowed",
        ),
    ],
)
def test_unsafe_or_unbindable_modules_write_nothing(
    issue: Path, tmp_path: Path, module: str, message: str
) -> None:
    out = tmp_path / "candidate"

    with pytest.raises(PatchError, match=message):
        propose_patch(issue, BUGGY_REF, out, client=_adapter(_FakeClient(module)))

    assert not out.exists()


def test_existing_output_directory_is_refused_before_any_model_call(
    issue: Path, tmp_path: Path
) -> None:
    out = tmp_path / "taken"
    out.mkdir()
    fake = _FakeClient(ATOMIC_MODULE)

    with pytest.raises(PatchError, match="already exists"):
        propose_patch(issue, BUGGY_REF, out, client=_adapter(fake))

    assert fake.models.calls == [] and fake.chat.completions.calls == []


def test_foreign_or_malformed_author_receipts_are_handled_like_proposals(
    issue: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = tmp_path / "candidate"
    propose_patch(issue, BUGGY_REF, out, client=_adapter(_FakeClient(ATOMIC_MODULE)))
    monkeypatch.setenv("NEMISIS_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    receipt = out / RECEIPT_PATH

    # The same receipt copied into a different tree does not bind that tree: ignored, not attached.
    other = materialize_fixture(MISLEADING_GREEN_REF, tmp_path / "other").path
    (other / RECEIPT_PATH.parent).mkdir()
    (other / RECEIPT_PATH).write_bytes(receipt.read_bytes())
    foreign = check(BUGGY_REF, other, SCENARIO_ID, mode="local")
    assert foreign.verdict is CrashVerdict.PATCH_FAILED_STILL_REPRODUCES
    assert foreign.candidate_author is None

    receipt.write_bytes(b'{"schema_version":"nemisis.patch-proposal.v1"}')
    with pytest.raises(CrashCheckError, match="strict validation"):
        check(BUGGY_REF, out, SCENARIO_ID, mode="local")


def test_cli_propose_patch_fails_closed_without_a_credential(
    issue: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("NEBIUS_API_KEY", raising=False)
    out = tmp_path / "candidate"
    monkeypatch.setattr(
        sys,
        "argv",
        ["nemisis", "propose-patch", "--issue", str(issue), "--base", BUGGY_REF, "--out", str(out)],
    )

    with pytest.raises(SystemExit) as error:
        cli.main()

    assert error.value.code == 2
    captured = capsys.readouterr()
    assert "NEMOTRON PATCH REJECTED" in captured.err
    assert "NEBIUS_API_KEY" in captured.err
    assert captured.out == ""
    assert not out.exists()


def test_cli_propose_patch_prints_provenance_and_the_next_command(
    issue: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        agent_patch_module, "NemotronClient", lambda: _adapter(_FakeClient(ATOMIC_MODULE))
    )
    out = tmp_path / "candidate"
    monkeypatch.setattr(
        sys,
        "argv",
        ["nemisis", "propose-patch", "--issue", str(issue), "--base", BUGGY_REF, "--out", str(out)],
    )

    cli.main()

    lines = capsys.readouterr().out.splitlines()
    assert lines[0] == f"candidate: {out}"
    assert lines[1].startswith(f"nemotron: {DEFAULT_MODEL_ID} · global · MOCKED · schema valid")
    assert lines[2].startswith("patch: ")
    assert lines[3] == "rationale: Commit credit and marker together."
    assert lines[4] == f"next: nemisis check --base {BUGGY_REF} --candidate {out} --mode local"
    assert (out / RECEIPT_PATH).is_file()
