from __future__ import annotations

from itertools import product

import pytest

from nemisis.hashing import canonical_json, sha256_json
from nemisis.matrix import candidate_is_accepted, classify, make_cell, summarize_claim
from nemisis.models import Classification, ExpectedRelation, Outcome


def test_canonical_digest_is_order_independent() -> None:
    left = {"b": [2, 1], "a": {"value": True}}
    right = {"a": {"value": True}, "b": [2, 1]}
    assert canonical_json(left) == canonical_json(right)
    assert sha256_json(left) == sha256_json(right)


@pytest.mark.parametrize("expected", list(ExpectedRelation))
@pytest.mark.parametrize("base,candidate", product(Outcome, repeat=2))
def test_classification_truth_table(
    expected: ExpectedRelation, base: Outcome, candidate: Outcome
) -> None:
    result = classify(expected, base, candidate)
    supported = (
        expected is ExpectedRelation.CHANGE_WITNESS
        and (base, candidate) == (Outcome.ASSERTION_FAIL, Outcome.PASS)
    ) or (
        expected is ExpectedRelation.INVARIANT and (base, candidate) == (Outcome.PASS, Outcome.PASS)
    )
    assert (result is Classification.SUPPORTED) is supported
    if base in {Outcome.ERROR, Outcome.TIMEOUT, Outcome.NOT_RUN} or candidate in {
        Outcome.ERROR,
        Outcome.TIMEOUT,
        Outcome.NOT_RUN,
    }:
        assert result is Classification.INCOMPLETE


def test_acceptance_requires_complete_supported_evidence() -> None:
    supported = make_cell(
        claim_id="claim",
        test_id="test",
        expected=ExpectedRelation.CHANGE_WITNESS,
        base=Outcome.ASSERTION_FAIL,
        candidate=Outcome.PASS,
        base_receipt_id="base:test",
        candidate_receipt_id="candidate:test",
    )
    result = summarize_claim("claim", [supported])
    assert candidate_is_accepted([result])

    incomplete = supported.model_copy(
        update={"classification": Classification.INCOMPLETE, "evidence_complete": False}
    )
    assert not candidate_is_accepted([summarize_claim("claim", [incomplete])])
    assert not candidate_is_accepted([])
