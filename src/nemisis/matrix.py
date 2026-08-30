"""Deterministic claim classification."""

from __future__ import annotations

from collections.abc import Sequence

from nemisis.models import (
    ClaimResult,
    Classification,
    ExpectedRelation,
    MatrixCell,
    Outcome,
)

INCOMPLETE_OUTCOMES = frozenset({Outcome.ERROR, Outcome.TIMEOUT, Outcome.NOT_RUN})


def classify(expected: ExpectedRelation, base: Outcome, candidate: Outcome) -> Classification:
    if base in INCOMPLETE_OUTCOMES or candidate in INCOMPLETE_OUTCOMES:
        return Classification.INCOMPLETE
    if expected is ExpectedRelation.CHANGE_WITNESS:
        if (base, candidate) == (Outcome.ASSERTION_FAIL, Outcome.PASS):
            return Classification.SUPPORTED
        if (base, candidate) == (Outcome.PASS, Outcome.ASSERTION_FAIL):
            return Classification.REGRESSION
        if (base, candidate) == (Outcome.PASS, Outcome.PASS):
            return Classification.NON_DISCRIMINATING
        return Classification.UNRESOLVED
    if (base, candidate) == (Outcome.PASS, Outcome.PASS):
        return Classification.SUPPORTED
    if (base, candidate) == (Outcome.PASS, Outcome.ASSERTION_FAIL):
        return Classification.REGRESSION
    return Classification.UNRESOLVED


def make_cell(
    *,
    claim_id: str,
    test_id: str,
    expected: ExpectedRelation,
    base: Outcome,
    candidate: Outcome,
    base_receipt_id: str,
    candidate_receipt_id: str,
) -> MatrixCell:
    classification = classify(expected, base, candidate)
    return MatrixCell(
        claim_id=claim_id,
        test_id=test_id,
        expected_relation=expected,
        base_outcome=base,
        candidate_outcome=candidate,
        classification=classification,
        base_receipt_id=base_receipt_id,
        candidate_receipt_id=candidate_receipt_id,
        evidence_complete=classification is not Classification.INCOMPLETE,
    )


def summarize_claim(claim_id: str, cells: Sequence[MatrixCell]) -> ClaimResult:
    matching = [cell for cell in cells if cell.claim_id == claim_id]
    if not matching:
        raise ValueError(f"claim has no matrix cells: {claim_id}")
    expected = matching[0].expected_relation
    if any(cell.expected_relation is not expected for cell in matching):
        raise ValueError(f"claim mixes expected relations: {claim_id}")
    classifications = tuple(cell.classification for cell in matching)
    return ClaimResult(
        claim_id=claim_id,
        expected_relation=expected,
        test_ids=tuple(cell.test_id for cell in matching),
        classifications=classifications,
        supported=all(item is Classification.SUPPORTED for item in classifications),
        evidence_complete=all(cell.evidence_complete for cell in matching),
    )


def candidate_is_accepted(results: Sequence[ClaimResult]) -> bool:
    return bool(results) and all(
        result.supported and result.evidence_complete for result in results
    )
