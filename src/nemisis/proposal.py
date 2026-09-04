"""Candidate-blind Nemotron contract proposal for ``nemisis init --nemotron``.

The model sees the issue text and the exact base handler, nothing else. It may only select
audited catalog IDs and one bounded scalar. Deterministic code then decides whether the proposal
matches the audited scenario; a mismatch refuses to draft a contract. Nothing here influences the
hunt, the capsule, or the verdict, and the receipt never carries the credential or raw response.
"""

from __future__ import annotations

import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Protocol

from nemisis.crash_fixture import SCENARIO_ID, load_contract, load_event
from nemisis.crash_models import ContractProposal
from nemisis.crashcheck import (
    MAX_CONFIG_BYTES,
    CrashCheckError,
    _audited_contract,
    _materialize_source,
    _write_exact,
)
from nemisis.hashing import canonical_json, sha256_text
from nemisis.nemotron import NemotronClient, NemotronContractGeneration
from nemisis.sqlite_credit import AnchorResolutionError, bind_anchor

PROPOSAL_NAME = "proposal.json"
AMOUNT_BOUNDS = (1, 1_000_000)


class ProposalError(ValueError):
    """The model proposal was not accepted; no contract was drafted."""

    def __init__(self, detail: str, proposal: ContractProposal | None = None) -> None:
        super().__init__(detail)
        self.proposal = proposal


class Proposer(Protocol):
    def generate_contract(
        self,
        issue: str,
        base_material: str,
        catalog_ids: Sequence[str],
        bounds: Mapping[str, tuple[int, int]],
    ) -> NemotronContractGeneration: ...


def propose_contract(
    issue: str | Path,
    target: str,
    base: str | Path,
    scenario_id: str = SCENARIO_ID,
    *,
    client: Proposer | None = None,
) -> ContractProposal:
    """Ask the model to bind the issue to the audited catalog; accept only an exact match."""
    if scenario_id != SCENARIO_ID:
        raise ProposalError(f"unsupported scenario: {scenario_id}")
    audited = load_contract()
    if target != audited["target"]:
        raise ProposalError(
            f"Nemotron proposals support only the audited target {audited['target']} in this alpha"
        )
    issue_path = Path(issue)
    try:
        if not issue_path.is_file() or issue_path.stat().st_size > MAX_CONFIG_BYTES:
            raise ProposalError("issue must be a UTF-8 file no larger than 100,000 bytes")
        issue_text = issue_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise ProposalError("issue must be a readable UTF-8 file") from error

    with tempfile.TemporaryDirectory(prefix="nemisis-propose-") as temporary:
        source = _materialize_source(base, Path(temporary) / "base")
        try:
            binding = bind_anchor(
                _audited_contract(),
                source.path,
                source_ref=source.ref,
                resolved_source_identity=source.resolved_identity,
            )
        except AnchorResolutionError as error:
            raise ProposalError(f"base handler did not bind: {error}") from error
        try:
            material = (source.path / binding.handler_path).read_text(encoding="utf-8")
        except (OSError, UnicodeError) as error:
            raise ProposalError("base handler is not readable UTF-8") from error
        base_ref, base_tree_digest = source.ref, source.tree_digest

    offered = (
        audited["adapter_id"],
        audited["event_fixture_id"],
        audited["fault_intent_id"],
        audited["probe_id"],
        *audited["predicate_ids"],
    )
    proposer = client if client is not None else NemotronClient()
    generation = proposer.generate_contract(
        issue_text, material, offered, {"amount_cents": AMOUNT_BOUNDS}
    )
    event = load_event()
    proposal = ContractProposal.with_digest(
        scenario_id=scenario_id,
        target=target,
        issue_digest=sha256_text(issue_text),
        base_ref=base_ref,
        base_tree_digest=base_tree_digest,
        handler_path=binding.handler_path,
        offered_catalog_ids=offered,
        required_catalog_id=audited["fault_intent_id"],
        proposed_catalog_ids=generation.catalog_ids,
        audited_amount_cents=event["amount_cents"],
        proposed_amount_cents=generation.scalars["amount_cents"],
        accepted=(
            audited["fault_intent_id"] in generation.catalog_ids
            and generation.scalars["amount_cents"] == event["amount_cents"]
        ),
        model_call=generation.receipt,
    )
    if not proposal.accepted:
        raise ProposalError(describe(proposal), proposal)
    return proposal


def write_proposal(proposal: ContractProposal, path: Path) -> Path:
    """Write the sanitized receipt beside the drafted contract; a rerun replaces it."""
    try:
        _write_exact(path, canonical_json(proposal) + b"\n", replace=True)
    except CrashCheckError as error:
        raise ProposalError(str(error)) from error
    return path


def describe(proposal: ContractProposal) -> str:
    receipt = proposal.model_call
    intent = (
        "selected" if proposal.required_catalog_id in proposal.proposed_catalog_ids else "omitted"
    )
    amount = (
        "matches the audited event"
        if proposal.proposed_amount_cents == proposal.audited_amount_cents
        else f"differs from the audited {proposal.audited_amount_cents}"
    )
    return (
        f"{receipt.model_id} ({receipt.truth_label.value}) {intent} fault intent "
        f"{proposal.required_catalog_id}; amount_cents={proposal.proposed_amount_cents} {amount}; "
        f"{len(proposal.proposed_catalog_ids)}/{len(proposal.offered_catalog_ids)} catalog IDs"
    )


__all__ = [
    "AMOUNT_BOUNDS",
    "PROPOSAL_NAME",
    "ProposalError",
    "Proposer",
    "describe",
    "propose_contract",
    "write_proposal",
]
