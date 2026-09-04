from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest

from nemisis.crash_fixture import BUGGY_REF, load_contract, load_issue
from nemisis.crash_models import ContractProposal
from nemisis.hashing import canonical_json
from nemisis.models import TruthLabel
from nemisis.nemotron import DEFAULT_MODEL_ID, NemotronClient, _Client
from nemisis.proposal import ProposalError, propose_contract

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
