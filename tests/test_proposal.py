from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import cast

import pytest

import nemisis.cli as cli
import nemisis.proposal as proposal_module
from nemisis.crash_fixture import BUGGY_REF, MISLEADING_GREEN_REF, load_contract, load_issue
from nemisis.crash_models import ContractProposal, CrashVerdict
from nemisis.crashcheck import CrashCheckError, check, initialize
from nemisis.hashing import canonical_json
from nemisis.models import TruthLabel
from nemisis.nemotron import DEFAULT_MODEL_ID, NemotronClient, _Client
from nemisis.proposal import PROPOSAL_NAME, ProposalError, propose_contract, write_proposal

AUDITED = load_contract()
TARGET = AUDITED["target"]
OFFERED = (
    AUDITED["adapter_id"],
    AUDITED["event_fixture_id"],
    AUDITED["fault_intent_id"],
    AUDITED["probe_id"],
    *AUDITED["predicate_ids"],
)


def _payload(catalog_ids: tuple[str, ...], amount_cents: int) -> dict[str, object]:
    return {
        "catalog_ids": list(catalog_ids),
        "scalars": [{"name": "amount_cents", "value": amount_cents}],
    }


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
    def __init__(self, payload: dict[str, object]) -> None:
        self.models = _Models()
        self.chat = _Chat(_Completions(payload))


def _adapter(fake: _FakeClient) -> NemotronClient:
    return NemotronClient(client=cast(_Client, fake))


@pytest.fixture
def issue(tmp_path: Path) -> Path:
    path = tmp_path / "issue.md"
    path.write_text(load_issue(), encoding="utf-8")
    return path


def test_accepted_proposal_is_candidate_blind_and_sanitized(issue: Path) -> None:
    fake = _FakeClient(_payload(OFFERED, 2_500))

    result = propose_contract(issue, TARGET, BUGGY_REF, client=_adapter(fake))

    assert result.accepted
    assert result.model_call.truth_label is TruthLabel.MOCKED
    assert result.model_call.model_id == DEFAULT_MODEL_ID
    assert result.handler_path == "app/credits.py"
    assert result.base_tree_digest == AUDITED["originating_base_tree_digest"]
    assert result.required_catalog_id == AUDITED["fault_intent_id"]
    assert result.proposed_amount_cents == result.audited_amount_cents == 2_500
    messages = cast(list[dict[str, str]], fake.chat.completions.calls[0]["messages"])
    prompt = "\n".join(message["content"] for message in messages)
    assert "apply_credit" in prompt and "evt_1042" in prompt
    assert "candidate" not in prompt.lower() and "misleading" not in prompt
    ContractProposal.model_validate_json(canonical_json(result))
    serialized = result.model_dump_json()
    assert "Duplicate account credit" not in serialized
    assert "store.credit(" not in serialized


@pytest.mark.parametrize(
    ("catalog_ids", "amount_cents", "message"),
    [
        (OFFERED, 25, "differs from the audited 2500"),
        (tuple(item for item in OFFERED if item != AUDITED["fault_intent_id"]), 2_500, "omitted"),
    ],
)
def test_mismatched_proposal_is_rejected_with_its_receipt(
    issue: Path, catalog_ids: tuple[str, ...], amount_cents: int, message: str
) -> None:
    fake = _FakeClient(_payload(catalog_ids, amount_cents))

    with pytest.raises(ProposalError, match=message) as caught:
        propose_contract(issue, TARGET, BUGGY_REF, client=_adapter(fake))

    rejected = caught.value.proposal
    assert rejected is not None and not rejected.accepted
    assert rejected.model_call.truth_label is TruthLabel.MOCKED


def test_unsupported_target_is_refused_before_any_model_call(issue: Path) -> None:
    fake = _FakeClient(_payload(OFFERED, 2_500))

    with pytest.raises(ProposalError, match="audited target"):
        propose_contract(issue, "app.other:handler", BUGGY_REF, client=_adapter(fake))

    assert fake.models.calls == [] and fake.chat.completions.calls == []


def test_bound_proposal_flows_into_check_manifest_and_report(
    issue: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    artifacts = tmp_path / "artifacts"
    monkeypatch.setenv("NEMISIS_ARTIFACT_ROOT", str(artifacts))
    proposal = propose_contract(
        issue, TARGET, BUGGY_REF, client=_adapter(_FakeClient(_payload(OFFERED, 2_500)))
    )
    config = initialize(issue, TARGET, BUGGY_REF, "sqlite-credit-v1")
    write_proposal(proposal, config.with_name(PROPOSAL_NAME))

    result = check(BUGGY_REF, MISLEADING_GREEN_REF, config, mode="local")

    assert result.verdict is CrashVerdict.PATCH_FAILED_STILL_REPRODUCES
    manifest = json.loads((artifacts / result.artifacts["manifest"]).read_text(encoding="utf-8"))
    assert manifest["contract_proposal"]["digest"] == proposal.digest
    assert manifest["contract_proposal"]["model_call"]["truth_label"] == "MOCKED"
    report = (artifacts / result.artifacts["report"]).read_text(encoding="utf-8")
    assert "MOCKED Nemotron receipt" in report
    assert DEFAULT_MODEL_ID in report
    assert "never emits a verdict" in report


def test_foreign_proposal_is_not_attached_and_malformed_one_fails_closed(
    issue: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("NEMISIS_ARTIFACT_ROOT", str(tmp_path / "artifacts"))
    proposal = propose_contract(
        issue, TARGET, BUGGY_REF, client=_adapter(_FakeClient(_payload(OFFERED, 2_500)))
    )
    config = initialize(issue, TARGET, BUGGY_REF, "sqlite-credit-v1")
    foreign = ContractProposal.with_digest(
        **proposal.model_dump(mode="python", exclude={"digest", "model_call", "issue_digest"}),
        issue_digest="f" * 64,
        model_call=proposal.model_call,
    )
    sidecar = config.with_name(PROPOSAL_NAME)
    write_proposal(foreign, sidecar)

    result = check(BUGGY_REF, MISLEADING_GREEN_REF, config, mode="local")
    manifest = json.loads(
        (tmp_path / "artifacts" / result.artifacts["manifest"]).read_text(encoding="utf-8")
    )
    assert manifest["contract_proposal"] is None

    sidecar.write_bytes(b'{"schema_version":"nemisis.contract-proposal.v1"}')
    with pytest.raises(CrashCheckError, match="strict validation"):
        check(BUGGY_REF, MISLEADING_GREEN_REF, config, mode="local")


def test_cli_init_nemotron_fails_closed_without_a_credential(
    issue: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("NEBIUS_API_KEY", raising=False)
    monkeypatch.setattr(
        sys,
        "argv",
        ["nemisis", "init", "--issue", str(issue), "--target", TARGET, "--base", BUGGY_REF]
        + ["--nemotron"],
    )

    with pytest.raises(SystemExit) as error:
        cli.main()

    assert error.value.code == 2
    captured = capsys.readouterr()
    assert "NEMOTRON PROPOSAL REJECTED" in captured.err
    assert "NEBIUS_API_KEY" in captured.err
    assert captured.out == ""
    assert not (tmp_path / ".nemisis").exists()


def test_cli_init_nemotron_writes_receipt_and_prints_provenance(
    issue: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        proposal_module,
        "NemotronClient",
        lambda: _adapter(_FakeClient(_payload(OFFERED, 2_500))),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["nemisis", "init", "--issue", str(issue), "--target", TARGET, "--base", BUGGY_REF]
        + ["--nemotron"],
    )

    cli.main()

    out = capsys.readouterr().out
    assert "status: ACCEPTED" in out
    assert f"nemotron: {DEFAULT_MODEL_ID} · global · MOCKED · schema valid" in out
    assert "amount_cents=2500 matches the audited event" in out
    sidecar = tmp_path / ".nemisis" / PROPOSAL_NAME
    proposal = ContractProposal.model_validate_json(sidecar.read_bytes())
    assert f"receipt {proposal.digest}" in out
    config = json.loads((tmp_path / ".nemisis" / "config.json").read_text(encoding="utf-8"))
    assert config["contract"]["issue_digest"] == proposal.issue_digest
    assert config["contract"]["originating_base_tree_digest"] == proposal.base_tree_digest


def test_cli_init_nemotron_rejection_drafts_nothing(
    issue: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        proposal_module,
        "NemotronClient",
        lambda: _adapter(_FakeClient(_payload(OFFERED, 25))),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["nemisis", "init", "--issue", str(issue), "--target", TARGET, "--base", BUGGY_REF]
        + ["--nemotron", "--json"],
    )

    with pytest.raises(SystemExit) as error:
        cli.main()

    assert error.value.code == 2
    captured = capsys.readouterr()
    assert "differs from the audited 2500" in captured.out
    assert '"verdict":"EVIDENCE_INCOMPLETE"' in captured.out
    assert not (tmp_path / ".nemisis").exists()
