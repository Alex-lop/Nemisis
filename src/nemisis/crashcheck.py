"""CrashCheck's small public interface and candidate-blind orchestration."""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import partial
from importlib import resources
from io import BytesIO
from pathlib import Path
from typing import cast

from nemisis.crash_fixture import (
    BUGGY_REF,
    FIXTURE_REFS,
    SCENARIO_ID,
    load_contract,
    load_event,
    materialize_fixture,
)
from nemisis.crash_models import (
    REQUIRED_CONFIRMATIONS,
    AnchorBinding,
    AnchorResolutionReceipt,
    AttemptReceipt,
    CommitSweepReceipt,
    ContractProposal,
    CrashCheckResult,
    CrashObservation,
    CrashVerdict,
    CreditSnapshot,
    ExecutionStatus,
    FaultBoundary,
    HypothesisReceipt,
    IntegrityStatus,
    MinimizationReceipt,
    NoFaultReplayReceipt,
    PatchProposal,
    ReproCapsule,
    RetryContract,
    TimelineEntry,
    TimelineState,
    WorldRole,
    sweep_observation,
)
from nemisis.doctor import doctor
from nemisis.hashing import canonical_json, sha256_bytes, sha256_json, sha256_text, sha256_tree
from nemisis.local import source_commit
from nemisis.models import TruthLabel
from nemisis.report import money, write_crash_report
from nemisis.safety import safe_destination, safe_relative_path
from nemisis.sqlite_credit import (
    RUNNER_ID,
    RUNNER_VERSION,
    AnchorResolutionError,
    bind_anchor,
    execute_attempt,
    execute_no_fault_replay,
    initial_database_digest,
    runner_environment_digest,
)

CONFIRMATIONS = REQUIRED_CONFIRMATIONS
CONFIG_PATH = Path(".nemisis/config.json")
MAX_CONFIG_BYTES = 100_000
MAX_SOURCE_ARCHIVE_BYTES = 20_000_000
MAX_SOURCE_FILES = 5_000
_IGNORED = frozenset({".git", ".nemisis", "__pycache__", ".pytest_cache", ".mypy_cache"})
_ENGINE_RESOURCES = (
    "crash_fixture.py",
    "crash_models.py",
    "crashcheck.py",
    "doctor.py",
    "hashing.py",
    "local.py",
    "models.py",
    "report.py",
    "safety.py",
    "sqlite_credit.py",
    "fixtures/sqlite_credit_v1/contract.json",
    "fixtures/sqlite_credit_v1/event.json",
)
_HYPOTHESES = (
    (1, "effect-commit-v1", FaultBoundary.EFFECT_COMMIT, 1),
    (2, "marker-commit-v1", FaultBoundary.MARKER_COMMIT, 2),
)
_MINIMIZATION_CONFIRMATIONS = 2
UNTRUSTED_FORK_DETAIL = "Local execution of an untrusted fork source is blocked; use ConTree."


class CrashCheckError(ValueError):
    """Invalid or unsupported CrashCheck input."""


def engine_code_digest() -> str:
    """Bind evidence to the exact installed trusted runner and catalog bytes."""
    root = resources.files("nemisis")
    hashes: dict[str, str] = {}
    try:
        for relative in _ENGINE_RESOURCES:
            item = root
            for part in relative.split("/"):
                item = item.joinpath(part)
            hashes[relative] = sha256_bytes(item.read_bytes())
    except (FileNotFoundError, OSError) as error:
        raise CrashCheckError("trusted CrashCheck engine resources are unavailable") from error
    return sha256_json(hashes)


AUTHOR_RECEIPT_PATH = Path(".nemisis/agent-patch.json")


@dataclass(frozen=True)
class _Source:
    ref: str
    path: Path
    tree_digest: str
    resolved_identity: str
    config_bytes: bytes | None
    author_bytes: bytes | None = None


def initialize(issue: str | Path, target: str, base: str | Path, scenario_id: str) -> Path:
    """Write strict, non-executable project configuration under ``.nemisis``."""
    if scenario_id != SCENARIO_ID:
        raise CrashCheckError(f"unsupported scenario: {scenario_id}")
    issue_path = Path(issue)
    if not issue_path.is_file() or issue_path.stat().st_size > 50_000:
        raise CrashCheckError("issue must be a UTF-8 file no larger than 50,000 bytes")
    try:
        issue_text = issue_path.read_text(encoding="utf-8")
    except UnicodeError as error:
        raise CrashCheckError("issue must be valid UTF-8") from error
    with tempfile.TemporaryDirectory(prefix="nemisis-init-") as temporary:
        source = _materialize_source(base, Path(temporary) / "base")
        audited = _audited_contract()
        accepted = (
            target == audited.target
            and source.ref == audited.originating_base_ref
            and source.tree_digest == audited.originating_base_tree_digest
            and sha256_text(issue_text) == audited.issue_digest
        )
        contract = _contract(
            base_ref=source.ref,
            base_digest=source.tree_digest,
            issue_digest=sha256_text(issue_text),
            target=target,
            accepted=accepted,
            truth_label=TruthLabel.FIXTURE if accepted else TruthLabel.PLANNED,
        )
    payload = {
        "base": str(base),
        "contract": contract.model_dump(mode="json"),
        "issue": str(issue_path),
        "scenario_id": scenario_id,
        "schema_version": "1",
        "status": "ACCEPTED" if accepted else "DRAFT",
        "target": target,
    }
    path = Path.cwd() / CONFIG_PATH
    if path.exists():
        _, existing = _load_config(path)
        same_identity = (
            existing.scenario_id == contract.scenario_id
            and existing.target == contract.target
            and existing.issue_digest == contract.issue_digest
            and existing.originating_base_tree_digest == contract.originating_base_tree_digest
        )
        if same_identity and existing.accepted:
            return path
        if not same_identity:
            raise CrashCheckError(
                f"{path} already holds a contract for a different issue, base, or target; "
                "delete it to re-initialize"
            )
    _write_exact(path, canonical_json(payload) + b"\n")
    return path


def accept_contract(digest: str, path: Path = CONFIG_PATH) -> RetryContract:
    """Accept only the exact draft digest previously printed to the user."""
    payload, draft = _load_config(path)
    if payload["status"] == "ACCEPTED":
        raise CrashCheckError(
            f"contract is already ACCEPTED with digest {draft.digest}; nothing to accept"
        )
    if draft.digest != digest:
        raise CrashCheckError("accepted digest does not match the current draft contract")
    values = draft.model_dump(mode="python", exclude={"digest", "accepted", "truth_label"})
    contract = RetryContract.with_digest(
        **values,
        accepted=True,
        truth_label=TruthLabel.LOCAL,
    )
    payload["contract"] = contract.model_dump(mode="json")
    payload["status"] = "ACCEPTED"
    _write_exact(path, canonical_json(payload) + b"\n", replace=True)
    return contract


def check(
    base: str | Path,
    candidate: str | Path,
    scenario: str | Path | RetryContract,
    corrected: str | Path | None = None,
    mode: str = "local",
) -> CrashCheckResult:
    """Hunt on the base, freeze one capsule, then evaluate the candidate unchanged."""
    started_at = datetime.now(UTC)
    run_id = _run_id(mode)
    with tempfile.TemporaryDirectory(prefix="nemisis-check-") as temporary:
        root = Path(temporary)
        base_source = _materialize_source(base, root / "source-base")
        contract = _contract_for_check(scenario, base_source)
        proposal = _proposal_for_check(scenario, contract)
        publish = partial(_publish, proposal=proposal)
        if mode not in {"local", "live"}:
            raise CrashCheckError("mode must be 'local' or 'live'")
        requested_transport = TruthLabel.LIVE if mode == "live" else TruthLabel.LOCAL
        preflight_capsule = _seal_capsule(contract)
        base_anchor = _bind_anchor(
            contract,
            base_source,
            WorldRole.BASE,
            requested_transport,
            preflight_capsule.digest,
        )
        if isinstance(base_anchor, AnchorResolutionReceipt):
            return publish(
                run_id,
                started_at,
                preflight_capsule,
                contract,
                (),
                (),
                CrashVerdict.EVIDENCE_INCOMPLETE,
                _anchor_failure_summary(base_anchor),
                anchor_resolutions=(base_anchor,),
                transport=requested_transport,
            )
        base_binding = base_anchor
        if mode == "live":
            capsule = preflight_capsule
            detail = _live_blocker()
            attempt = _failed_attempt(
                capsule, base_binding, WorldRole.BASE, TruthLabel.LIVE, detail
            )
            return publish(
                run_id,
                started_at,
                capsule,
                contract,
                (base_binding,),
                (attempt,),
                CrashVerdict.EVIDENCE_INCOMPLETE,
                detail,
            )
        if mode != "local":
            raise CrashCheckError("mode must be 'local' or 'live'")

        hypothesis_receipts, capsule = _hunt_hypotheses(
            contract,
            base_binding,
            base_source.path,
            root / uuid.uuid4().hex,
        )
        if not _hunt_is_conclusive(hypothesis_receipts):
            detail = "The two base-only crash-boundary hypotheses did not yield one witness."
            attempt = _failed_attempt(
                capsule, base_binding, WorldRole.BASE, TruthLabel.LOCAL, detail
            )
            return publish(
                run_id,
                started_at,
                capsule,
                contract,
                (base_binding,),
                (attempt,),
                CrashVerdict.EVIDENCE_INCOMPLETE,
                detail,
                hypothesis_receipts=hypothesis_receipts,
            )

        minimization_receipt, capsule = _minimize_witness(
            contract,
            capsule,
            base_binding,
            base_source.path,
            root / uuid.uuid4().hex,
        )
        minimization_receipts = (minimization_receipt,)
        if not minimization_receipt.sole_fault_action_necessary_for_fixture:
            detail = (
                "The fixture-scoped one-action deletion check did not establish necessity in two "
                "fresh base worlds."
            )
            attempt = _failed_attempt(
                capsule, base_binding, WorldRole.BASE, TruthLabel.LOCAL, detail
            )
            return publish(
                run_id,
                started_at,
                capsule,
                contract,
                (base_binding,),
                (attempt,),
                CrashVerdict.EVIDENCE_INCOMPLETE,
                detail,
                hypothesis_receipts=hypothesis_receipts,
                minimization_receipts=minimization_receipts,
            )

        base_attempts = _execute_confirmations(
            capsule, base_binding, base_source.path, root / uuid.uuid4().hex, WorldRole.BASE
        )
        if _confirmed_observation(base_attempts, capsule) is not CrashObservation.DUPLICATE_EFFECT:
            return publish(
                run_id,
                started_at,
                capsule,
                contract,
                (base_binding,),
                base_attempts,
                CrashVerdict.EVIDENCE_INCOMPLETE,
                "The originating base did not reproduce in five fresh worlds.",
                hypothesis_receipts=hypothesis_receipts,
                minimization_receipts=minimization_receipts,
            )
        if _untrusted_fork():
            attempt = _failed_attempt(
                capsule,
                base_binding,
                WorldRole.BASE,
                TruthLabel.LOCAL,
                UNTRUSTED_FORK_DETAIL,
            )
            return publish(
                run_id,
                started_at,
                capsule,
                contract,
                (base_binding,),
                (*base_attempts, attempt),
                CrashVerdict.EVIDENCE_INCOMPLETE,
                attempt.failure_detail or "Untrusted fork blocked.",
                hypothesis_receipts=hypothesis_receipts,
                minimization_receipts=minimization_receipts,
            )

        # Candidate materialization deliberately begins only after the base witness is frozen.
        candidate_source = _materialize_source(candidate, root / "source-candidate")
        publish = partial(publish, author=_load_author(candidate_source, contract))
        candidate_anchor = _bind_anchor(
            contract,
            candidate_source,
            WorldRole.CANDIDATE,
            requested_transport,
            capsule.digest,
        )
        if isinstance(candidate_anchor, AnchorResolutionReceipt):
            return publish(
                run_id,
                started_at,
                capsule,
                contract,
                (base_binding,),
                base_attempts,
                CrashVerdict.EVIDENCE_INCOMPLETE,
                _anchor_failure_summary(candidate_anchor),
                hypothesis_receipts=hypothesis_receipts,
                minimization_receipts=minimization_receipts,
                anchor_resolutions=(candidate_anchor,),
            )
        candidate_binding = candidate_anchor
        _require_distinct_binding(candidate_binding, (base_binding,), WorldRole.CANDIDATE)
        candidate_attempts = _execute_confirmations(
            capsule,
            candidate_binding,
            candidate_source.path,
            root / uuid.uuid4().hex,
            WorldRole.CANDIDATE,
        )
        bindings = [base_binding, candidate_binding]
        attempts = [*base_attempts, *candidate_attempts]
        sweeps: list[CommitSweepReceipt] = []
        candidate_observation = _confirmed_observation(candidate_attempts, capsule)
        if candidate_observation is CrashObservation.NOT_OBSERVED:
            # The crash test could not run. If that is because the handler never reached the
            # credit, a no-kill census still tells the user what the money did.
            if _never_reached_checkpoint(candidate_attempts):
                sweeps.append(
                    _execute_sweep(
                        capsule,
                        candidate_binding,
                        candidate_source.path,
                        root / uuid.uuid4().hex,
                        WorldRole.CANDIDATE,
                    )
                )
            return publish(
                run_id,
                started_at,
                capsule,
                contract,
                tuple(bindings),
                tuple(attempts),
                CrashVerdict.EVIDENCE_INCOMPLETE,
                _unreached_summary(candidate_attempts, sweeps[-1] if sweeps else None, capsule),
                hypothesis_receipts=hypothesis_receipts,
                minimization_receipts=minimization_receipts,
                sweeps=tuple(sweeps),
            )
        candidate_sweep: CommitSweepReceipt | None = None
        if candidate_observation is CrashObservation.EXACTLY_ONCE:
            candidate_sweep = _execute_sweep(
                capsule,
                candidate_binding,
                candidate_source.path,
                root / uuid.uuid4().hex,
                WorldRole.CANDIDATE,
            )
            sweeps.append(candidate_sweep)
            candidate_observation = candidate_sweep.observation
        corrected_observation: CrashObservation | None = None
        if corrected is not None:
            corrected_source = _materialize_source(corrected, root / "source-corrected")
            corrected_anchor = _bind_anchor(
                contract,
                corrected_source,
                WorldRole.CORRECTED,
                requested_transport,
                capsule.digest,
            )
            if isinstance(corrected_anchor, AnchorResolutionReceipt):
                return publish(
                    run_id,
                    started_at,
                    capsule,
                    contract,
                    tuple(bindings),
                    tuple(attempts),
                    CrashVerdict.EVIDENCE_INCOMPLETE,
                    _anchor_failure_summary(corrected_anchor),
                    hypothesis_receipts=hypothesis_receipts,
                    minimization_receipts=minimization_receipts,
                    anchor_resolutions=(corrected_anchor,),
                )
            corrected_binding = corrected_anchor
            _require_distinct_binding(
                corrected_binding, (base_binding, candidate_binding), WorldRole.CORRECTED
            )
            corrected_attempts = _execute_confirmations(
                capsule,
                corrected_binding,
                corrected_source.path,
                root / uuid.uuid4().hex,
                WorldRole.CORRECTED,
            )
            bindings.append(corrected_binding)
            attempts.extend(corrected_attempts)
            corrected_observation = _confirmed_observation(corrected_attempts, capsule)
            if corrected_observation is CrashObservation.EXACTLY_ONCE:
                corrected_sweep = _execute_sweep(
                    capsule,
                    corrected_binding,
                    corrected_source.path,
                    root / uuid.uuid4().hex,
                    WorldRole.CORRECTED,
                )
                sweeps.append(corrected_sweep)
                corrected_observation = corrected_sweep.observation

        if corrected is not None and corrected_observation is not CrashObservation.EXACTLY_ONCE:
            verdict = CrashVerdict.EVIDENCE_INCOMPLETE
            summary = "The known-good corrected control did not prove the capsule invariant."
        else:
            verdict, summary = _claimed_fix_verdict(
                candidate_observation, candidate_attempts, candidate_sweep, capsule
            )
        return publish(
            run_id,
            started_at,
            capsule,
            contract,
            tuple(bindings),
            tuple(attempts),
            verdict,
            summary,
            hypothesis_receipts=hypothesis_receipts,
            minimization_receipts=minimization_receipts,
            sweeps=tuple(sweeps),
        )


def replay(
    capsule: str | Path | ReproCapsule,
    source: str | Path,
    role: str = "candidate",
    mode: str = "local",
) -> CrashCheckResult:
    """Replay only the immutable event, fault intent, schedule, and predicates in a capsule."""
    started_at = datetime.now(UTC)
    capsule_path = None if isinstance(capsule, ReproCapsule) else Path(capsule)
    sealed = _load_capsule(capsule)
    contract = _contract_for_capsule(
        sealed,
        capsule_path.with_name("contract.json") if capsule_path is not None else None,
    )
    try:
        world_role = WorldRole(role)
    except ValueError:
        raise CrashCheckError("role must be base, candidate, or corrected") from None
    run_id = _run_id(mode)
    with tempfile.TemporaryDirectory(prefix="nemisis-replay-") as temporary:
        root = Path(temporary)
        materialized = _materialize_source(source, root / "source")
        if mode not in {"local", "live"}:
            raise CrashCheckError("mode must be 'local' or 'live'")
        requested_transport = TruthLabel.LIVE if mode == "live" else TruthLabel.LOCAL
        anchor = _bind_anchor(
            contract,
            materialized,
            world_role,
            requested_transport,
            sealed.digest,
        )
        if isinstance(anchor, AnchorResolutionReceipt):
            return _publish(
                run_id,
                started_at,
                sealed,
                contract,
                (),
                (),
                CrashVerdict.EVIDENCE_INCOMPLETE,
                _anchor_failure_summary(anchor),
                anchor_resolutions=(anchor,),
                transport=requested_transport,
            )
        binding = anchor
        attempts: tuple[AttemptReceipt, ...]
        sweeps: tuple[CommitSweepReceipt, ...] = ()
        sweep: CommitSweepReceipt | None = None
        if mode == "live":
            detail = _live_blocker()
            attempts = (_failed_attempt(sealed, binding, world_role, TruthLabel.LIVE, detail),)
            verdict = CrashVerdict.EVIDENCE_INCOMPLETE
        elif _untrusted_fork():
            detail = UNTRUSTED_FORK_DETAIL
            attempts = (_failed_attempt(sealed, binding, world_role, TruthLabel.LOCAL, detail),)
            verdict = CrashVerdict.EVIDENCE_INCOMPLETE
        elif mode == "local":
            attempts = _execute_confirmations(
                sealed, binding, materialized.path, root / uuid.uuid4().hex, world_role
            )
            observation = _confirmed_observation(attempts, sealed)
            if world_role is WorldRole.BASE:
                if observation is CrashObservation.DUPLICATE_EFFECT:
                    verdict = CrashVerdict.BUG_REPRODUCED
                    detail = _summary(verdict)
                elif observation is CrashObservation.EXACTLY_ONCE:
                    verdict = CrashVerdict.EVIDENCE_INCOMPLETE
                    detail = (
                        "The base role completed exactly once, so it did not reproduce this "
                        "capsule; replay a fix under --role candidate or --role corrected."
                    )
                else:
                    verdict = CrashVerdict.EVIDENCE_INCOMPLETE
                    detail = _unsupported_observation_summary(observation, attempts)
            else:
                if observation is CrashObservation.EXACTLY_ONCE:
                    sweep = _execute_sweep(
                        sealed, binding, materialized.path, root / uuid.uuid4().hex, world_role
                    )
                    sweeps = (sweep,)
                    observation = sweep.observation
                verdict, detail = _claimed_fix_verdict(observation, attempts, sweep, sealed)
        else:
            raise CrashCheckError("mode must be 'local' or 'live'")
        return _publish(
            run_id,
            started_at,
            sealed,
            contract,
            (binding,),
            attempts,
            verdict,
            detail,
            sweeps=sweeps,
        )


def _audited_contract() -> RetryContract:
    raw = load_contract()
    return _contract(
        base_ref=raw["originating_base_ref"],
        base_digest=raw["originating_base_tree_digest"],
        issue_digest=raw["issue_digest"],
        target=raw["target"],
        accepted=True,
        truth_label=TruthLabel.FIXTURE,
    )


def _contract(
    *,
    base_ref: str,
    base_digest: str,
    issue_digest: str,
    target: str,
    accepted: bool,
    truth_label: TruthLabel,
) -> RetryContract:
    raw = load_contract()
    return RetryContract.with_digest(
        scenario_id=raw["scenario_id"],
        originating_base_ref=base_ref,
        originating_base_tree_digest=base_digest,
        issue_digest=issue_digest,
        target=target,
        adapter_id=raw["adapter_id"],
        event_fixture_id=raw["event_fixture_id"],
        event_digest=raw["event_digest"],
        fault_intent_id=raw["fault_intent_id"],
        probe_id=raw["probe_id"],
        predicate_ids=tuple(raw["predicate_ids"]),
        accepted=accepted,
        truth_label=truth_label,
    )


def _contract_for_check(scenario: str | Path | RetryContract, base: _Source) -> RetryContract:
    if isinstance(scenario, RetryContract):
        contract = scenario
    elif str(scenario) == SCENARIO_ID:
        audited = _audited_contract()
        if base.ref == BUGGY_REF and base.tree_digest == audited.originating_base_tree_digest:
            contract = audited
        elif base.config_bytes is not None:
            _, contract = _load_config_bytes(base.config_bytes)
        else:
            raise CrashCheckError(
                "exact supplied base has no accepted .nemisis/config.json for sqlite-credit-v1"
            )
    elif Path(str(scenario)).is_file():
        _, contract = _load_config(Path(str(scenario)))
    else:
        raise CrashCheckError(f"unsupported scenario: {scenario}")
    if not contract.accepted:
        raise CrashCheckError(f"contract is DRAFT; accept digest {contract.digest}")
    if contract.originating_base_tree_digest != base.tree_digest:
        raise CrashCheckError("contract originating base digest differs from the supplied base")
    return contract


def _proposal_for_check(
    scenario: str | Path | RetryContract, contract: RetryContract
) -> ContractProposal | None:
    """Attach the sidecar Nemotron proposal only for a config path whose sibling binds it."""
    if isinstance(scenario, RetryContract) or str(scenario) == SCENARIO_ID:
        return None
    return _load_proposal(Path(str(scenario)).with_name("proposal.json"), contract)


def _load_author(source: _Source, contract: RetryContract) -> PatchProposal | None:
    """Attach the Nemotron authorship receipt only when it binds this exact candidate tree."""
    if source.author_bytes is None:
        return None
    if len(source.author_bytes) > MAX_CONFIG_BYTES:
        raise CrashCheckError("candidate authorship receipt is oversized")
    try:
        author = PatchProposal.model_validate_json(source.author_bytes)
    except ValueError as error:
        raise CrashCheckError("candidate authorship receipt failed strict validation") from error
    bound = (
        author.scenario_id == contract.scenario_id
        and author.candidate_tree_digest == source.tree_digest
        and author.base_tree_digest == contract.originating_base_tree_digest
    )
    return author if bound else None


def _load_proposal(path: Path, contract: RetryContract) -> ContractProposal | None:
    try:
        status = path.lstat()
    except FileNotFoundError:
        return None
    except OSError as error:
        raise CrashCheckError("contract proposal could not be read") from error
    if not stat.S_ISREG(status.st_mode) or status.st_size > MAX_CONFIG_BYTES:
        raise CrashCheckError("contract proposal is not a bounded regular file")
    try:
        proposal = ContractProposal.model_validate_json(path.read_bytes())
    except OSError as error:
        raise CrashCheckError("contract proposal could not be read") from error
    except ValueError as error:
        raise CrashCheckError("contract proposal failed strict validation") from error
    bound = (
        proposal.accepted
        and proposal.scenario_id == contract.scenario_id
        and proposal.target == contract.target
        and proposal.issue_digest == contract.issue_digest
        and proposal.base_tree_digest == contract.originating_base_tree_digest
    )
    return proposal if bound else None


def _contract_for_capsule(
    capsule: ReproCapsule, exported_contract: Path | None = None
) -> RetryContract:
    audited = _audited_contract()
    if exported_contract is not None and exported_contract.exists():
        contract = _load_exported_contract(exported_contract)
        if not contract.accepted or contract.digest != capsule.contract_digest:
            raise CrashCheckError("exported capsule contract is unaccepted or has another digest")
    elif audited.digest == capsule.contract_digest:
        contract = audited
    elif CONFIG_PATH.is_file():
        _, configured = _load_config(CONFIG_PATH)
        if configured.digest == capsule.contract_digest and configured.accepted:
            contract = configured
        else:
            raise CrashCheckError("capsule contract is not the audited or accepted local contract")
    else:
        raise CrashCheckError("capsule contract is not the audited or accepted local contract")
    _validate_capsule_contract(capsule, contract)
    return contract


def _load_exported_contract(path: Path) -> RetryContract:
    try:
        status = path.lstat()
        if not stat.S_ISREG(status.st_mode) or status.st_size > MAX_CONFIG_BYTES:
            raise CrashCheckError("exported capsule contract is not a bounded regular file")
        contract = RetryContract.model_validate_json(path.read_bytes())
    except OSError as error:
        raise CrashCheckError("exported capsule contract could not be read") from error
    except ValueError as error:
        raise CrashCheckError("exported capsule contract failed strict validation") from error
    _require_contract_label(contract)
    return contract


def _validate_capsule_contract(capsule: ReproCapsule, contract: RetryContract) -> None:
    event = load_event()
    expected = {
        "contract_digest": capsule.contract_digest == contract.digest,
        "originating_base_tree_digest": (
            capsule.originating_base_tree_digest == contract.originating_base_tree_digest
        ),
        "engine_code_digest": capsule.engine_code_digest == engine_code_digest(),
        "scenario_id": capsule.scenario_id == contract.scenario_id,
        "event_id": capsule.event_id == event["event_id"],
        "account_id": capsule.account_id == event["account_id"],
        "amount_cents": capsule.amount_cents == event["amount_cents"],
        "event_digest": capsule.event_digest == contract.event_digest,
        "fault_intent_id": capsule.fault_intent_id == contract.fault_intent_id,
        "probe_id": capsule.probe_id == contract.probe_id,
        "predicate_ids": capsule.predicate_ids == contract.predicate_ids,
        "runner_id": capsule.runner_id == RUNNER_ID,
        "runner_version": capsule.runner_version == RUNNER_VERSION,
        "environment_digest": capsule.environment_digest == runner_environment_digest(),
        "initial_database_digest": (
            capsule.initial_database_digest == initial_database_digest(event)
        ),
        "truth_label": capsule.truth_label is contract.truth_label,
    }
    failed = [name for name, okay in expected.items() if not okay]
    if failed:
        hint = ""
        if "engine_code_digest" in failed or "environment_digest" in failed:
            hint = (
                "; this capsule was recorded under a different engine build or runtime, so "
                "run check again to freeze a capsule for this engine"
            )
        raise CrashCheckError(
            "capsule fields differ from its accepted contract or trusted engine: "
            f"{', '.join(failed)}{hint}"
        )


def _bind_anchor(
    contract: RetryContract,
    source: _Source,
    role: WorldRole,
    transport: TruthLabel,
    capsule_digest: str,
) -> AnchorBinding | AnchorResolutionReceipt:
    try:
        return bind_anchor(
            contract,
            source.path,
            source_ref=source.ref,
            resolved_source_identity=source.resolved_identity,
        )
    except AnchorResolutionError as error:
        return AnchorResolutionReceipt.with_digest(
            role=role,
            transport=transport,
            status=error.status,
            capsule_digest=capsule_digest,
            contract_digest=contract.digest,
            scenario_id=contract.scenario_id,
            source_ref=source.ref,
            resolved_source_identity=source.resolved_identity,
            tree_digest=source.tree_digest,
            target=contract.target,
            matched_paths=error.matched_paths,
            detail=str(error),
        )
    except ValueError as error:
        raise CrashCheckError(f"UNSUPPORTED_TARGET: {error}") from error


def _require_distinct_binding(
    binding: AnchorBinding, earlier: tuple[AnchorBinding, ...], role: WorldRole
) -> None:
    if any(binding.digest == other.digest for other in earlier):
        raise CrashCheckError(
            f"{role.value} resolves to the same source ref and tree as an earlier role; "
            "supply a different ref"
        )


def _unsupported_observation_summary(
    observation: CrashObservation, attempts: tuple[AttemptReceipt, ...] = ()
) -> str:
    if observation is CrashObservation.INVARIANT_FAILED:
        return (
            "Every world completed, but the final durable state matched neither exactly-once nor "
            "the capsule's duplicate shape: the invariant failed, so nothing is proven."
        )
    failures = [attempt.failure_detail for attempt in attempts if attempt.failure_detail]
    if failures:
        detail, count = max(
            ((item, failures.count(item)) for item in set(failures)), key=lambda x: x[1]
        )
        role = attempts[0].role.value
        return (
            f"{count} of {len(attempts)} {role} worlds did not complete: {detail}. "
            "No verdict is issued from incomplete or contradictory evidence."
        )
    seen = sorted({attempt.observation for attempt in attempts}, key=lambda item: item.value)
    if len(seen) > 1:
        tally = ", ".join(
            f"{sum(attempt.observation is item for attempt in attempts)} {item.value}"
            for item in seen
        )
        return (
            f"The {len(attempts)} {attempts[0].role.value} worlds disagreed ({tally}): the "
            "handler is nondeterministic under the same kill, so no verdict is issued. CrashCheck "
            "reports unanimity or nothing."
        )
    return "Execution completed without one stable supported observation."


def _invariant_summary(attempts: tuple[AttemptReceipt, ...], capsule: ReproCapsule) -> str:
    """Name the durable state that was neither exactly-once nor the capsule's duplicate."""
    final = next((attempt.final_snapshot for attempt in attempts if attempt.final_snapshot), None)
    if final is None:
        return _unsupported_observation_summary(CrashObservation.INVARIANT_FAILED)
    return (
        f"Every world completed with {_describe_final(final, capsule)}. "
        "The patch broke the invariant it was meant to protect."
    )


def _anchor_failure_summary(receipt: AnchorResolutionReceipt) -> str:
    return (
        f"The accepted {receipt.role.value} target mapping for {receipt.target} was "
        f"{receipt.status.value} in {receipt.source_ref} "
        f"(resolved {receipt.resolved_source_identity[:16]}): {receipt.detail}. "
        "No unbound source was executed."
    )


def _seal_capsule(
    contract: RetryContract,
    fault_boundary: FaultBoundary = FaultBoundary.EFFECT_COMMIT,
    minimization_trace: tuple[str, ...] = (),
) -> ReproCapsule:
    event = load_event()
    if contract.event_digest != load_contract()["event_digest"]:
        raise CrashCheckError("contract event digest differs from the trusted catalog")
    return ReproCapsule.with_digest(
        contract_digest=contract.digest,
        originating_base_tree_digest=contract.originating_base_tree_digest,
        engine_code_digest=engine_code_digest(),
        scenario_id=contract.scenario_id,
        scenario_version="1",
        event_id=event["event_id"],
        account_id=event["account_id"],
        amount_cents=event["amount_cents"],
        event_digest=contract.event_digest,
        fault_intent_id=contract.fault_intent_id,
        fault_boundary=fault_boundary,
        probe_id=contract.probe_id,
        predicate_ids=contract.predicate_ids,
        runner_id=RUNNER_ID,
        runner_version=RUNNER_VERSION,
        environment_digest=runner_environment_digest(),
        initial_database_digest=initial_database_digest(event),
        minimization_trace=minimization_trace,
        truth_label=contract.truth_label,
    )


def _hunt_hypotheses(
    contract: RetryContract,
    binding: AnchorBinding,
    source: Path,
    work_root: Path,
) -> tuple[tuple[HypothesisReceipt, ...], ReproCapsule]:
    """Execute the fixed candidate-blind hypothesis wave and freeze its trace."""

    def one(
        spec: tuple[int, str, FaultBoundary, int],
    ) -> tuple[tuple[int, str, FaultBoundary, int], ReproCapsule, AttemptReceipt]:
        rank, _hypothesis_id, boundary, _operation_count = spec
        provisional = _seal_capsule(contract, boundary)
        nonce = uuid.uuid4().hex
        try:
            attempt = execute_attempt(
                capsule=provisional,
                binding=binding,
                source_tree=source,
                work_dir=work_root / uuid.uuid4().hex,
                role=WorldRole.BASE,
                execution_nonce=nonce,
            )
        except Exception as error:  # Preserve a bounded fail-closed hunt receipt.
            attempt = _failed_attempt(
                provisional,
                binding,
                WorldRole.BASE,
                TruthLabel.LOCAL,
                f"hypothesis orchestration failed ({type(error).__name__})",
                execution_nonce=nonce,
            )
        return spec, provisional, attempt

    with ThreadPoolExecutor(max_workers=len(_HYPOTHESES)) as executor:
        futures = [executor.submit(one, spec) for spec in _HYPOTHESES]
        observations = [future.result() for future in futures]

    reproducing_ranks = [
        spec[0]
        for spec, _capsule, attempt in observations
        if attempt.execution_status is ExecutionStatus.COMPLETED
        and attempt.integrity_status is IntegrityStatus.VALID
        and attempt.observation is CrashObservation.DUPLICATE_EFFECT
    ]
    selected_rank = min(reproducing_ranks, default=None)
    receipts = tuple(
        HypothesisReceipt.with_digest(
            canonical_rank=spec[0],
            hypothesis_id=spec[1],
            contract_digest=contract.digest,
            originating_base_tree_digest=binding.tree_digest,
            fault_boundary=spec[2],
            trusted_operation_count=spec[3],
            reproduced=(
                attempt.execution_status is ExecutionStatus.COMPLETED
                and attempt.integrity_status is IntegrityStatus.VALID
                and attempt.observation is CrashObservation.DUPLICATE_EFFECT
            ),
            selected=spec[0] == selected_rank,
            provisional_capsule_digest=provisional.digest,
            attempt=attempt,
        )
        for spec, provisional, attempt in observations
    )
    selected_boundary = next(
        (receipt.fault_boundary for receipt in receipts if receipt.selected),
        FaultBoundary.EFFECT_COMMIT,
    )
    capsule = _seal_capsule(contract, selected_boundary)
    return receipts, capsule


def _hunt_is_conclusive(receipts: tuple[HypothesisReceipt, ...]) -> bool:
    return (
        len(receipts) == len(_HYPOTHESES)
        and sum(receipt.selected for receipt in receipts) == 1
        and all(
            receipt.attempt.execution_status is ExecutionStatus.COMPLETED
            and receipt.attempt.integrity_status is IntegrityStatus.VALID
            for receipt in receipts
        )
    )


def _hypothesis_trace(receipts: tuple[HypothesisReceipt, ...]) -> tuple[str, ...]:
    """Hash only stable hunt semantics; full volatile receipts stay in the run manifest."""
    return tuple(
        sha256_json(
            {
                "canonical_rank": receipt.canonical_rank,
                "contract_digest": receipt.contract_digest,
                "fault_boundary": receipt.fault_boundary,
                "hypothesis_id": receipt.hypothesis_id,
                "originating_base_tree_digest": receipt.originating_base_tree_digest,
                "provisional_capsule_digest": receipt.provisional_capsule_digest,
                "reproduced": receipt.reproduced,
                "selected": receipt.selected,
                "trusted_operation_count": receipt.trusted_operation_count,
            }
        )
        for receipt in receipts
    )


def _minimize_witness(
    contract: RetryContract,
    parent: ReproCapsule,
    binding: AnchorBinding,
    source: Path,
    work_root: Path,
) -> tuple[MinimizationReceipt, ReproCapsule]:
    """Delete the sole fault action twice; continue only when both fixture worlds are exact-once."""

    def one(index: int) -> NoFaultReplayReceipt:
        nonce = uuid.uuid4().hex
        try:
            return execute_no_fault_replay(
                capsule=parent,
                binding=binding,
                source_tree=source,
                work_dir=work_root / uuid.uuid4().hex,
                execution_nonce=nonce,
            )
        except Exception as error:  # Preserve fail-closed minimization evidence.
            now = datetime.now(UTC)
            return NoFaultReplayReceipt.with_digest(
                receipt_id=f"no-fault-{uuid.uuid4().hex}",
                execution_status=ExecutionStatus.SETUP_ERROR,
                integrity_status=IntegrityStatus.INCOMPLETE,
                observation=CrashObservation.NOT_OBSERVED,
                parent_capsule_digest=parent.digest,
                contract_digest=parent.contract_digest,
                binding_digest=binding.digest,
                tree_digest=binding.tree_digest,
                post_execution_tree_digest=binding.tree_digest,
                environment_digest=parent.environment_digest,
                event_digest=parent.event_digest,
                amount_cents=parent.amount_cents,
                initial_database_digest=parent.initial_database_digest,
                database_id=f"db-{uuid.uuid4().hex}",
                execution_nonce=nonce,
                started_at=now,
                ended_at=now,
                spawns=(),
                failure_detail=f"minimization orchestration failed ({type(error).__name__})",
            )

    with ThreadPoolExecutor(max_workers=_MINIMIZATION_CONFIRMATIONS) as executor:
        futures = [
            executor.submit(one, index) for index in range(1, _MINIMIZATION_CONFIRMATIONS + 1)
        ]
        confirmations = tuple(future.result() for future in futures)
    completed = all(
        attempt.execution_status is ExecutionStatus.COMPLETED
        and attempt.integrity_status is IntegrityStatus.VALID
        for attempt in confirmations
    )
    reproduced = completed and all(
        attempt.observation is CrashObservation.DUPLICATE_EFFECT for attempt in confirmations
    )
    necessary = completed and all(
        attempt.observation is CrashObservation.EXACTLY_ONCE for attempt in confirmations
    )
    stable = {
        "candidate_schedule": (),
        "confirmation_count": len(confirmations),
        "contract_digest": contract.digest,
        "sole_fault_action_necessary_for_fixture": necessary,
        "originating_base_tree_digest": binding.tree_digest,
        "parent_capsule_digest": parent.digest,
        "parent_schedule": (FaultBoundary.EFFECT_COMMIT,),
        "removed_fault": FaultBoundary.EFFECT_COMMIT,
        "empty_schedule_reproduced_duplicate": reproduced,
        "deletion_accepted": reproduced,
    }
    receipt = MinimizationReceipt.with_digest(
        parent_capsule_digest=parent.digest,
        contract_digest=contract.digest,
        originating_base_tree_digest=binding.tree_digest,
        parent_schedule=(FaultBoundary.EFFECT_COMMIT,),
        candidate_schedule=(),
        removed_fault=FaultBoundary.EFFECT_COMMIT,
        confirmations=confirmations,
        empty_schedule_reproduced_duplicate=reproduced,
        deletion_accepted=reproduced,
        sole_fault_action_necessary_for_fixture=necessary,
        trace_digest=sha256_json(stable),
    )
    return receipt, _seal_capsule(
        contract,
        parent.fault_boundary,
        (receipt.trace_digest,),
    )


def _load_capsule(value: str | Path | ReproCapsule) -> ReproCapsule:
    if isinstance(value, ReproCapsule):
        return value
    path = Path(value)
    try:
        status = path.lstat()
    except OSError as error:
        raise CrashCheckError("capsule must be a bounded regular JSON file") from error
    if not stat.S_ISREG(status.st_mode) or status.st_size > 100_000:
        raise CrashCheckError("capsule must be a bounded JSON file")
    try:
        capsule = ReproCapsule.model_validate_json(path.read_bytes())
    except ValueError as error:
        raise CrashCheckError("capsule failed strict schema or digest validation") from error
    if capsule.scenario_id != SCENARIO_ID:
        raise CrashCheckError("capsule scenario is unsupported")
    return capsule


def _execute_confirmations(
    capsule: ReproCapsule,
    binding: AnchorBinding,
    source: Path,
    work_root: Path,
    role: WorldRole,
) -> tuple[AttemptReceipt, ...]:
    work_root.mkdir(parents=True, exist_ok=False)

    def one(index: int) -> AttemptReceipt:
        nonce = uuid.uuid4().hex
        try:
            return execute_attempt(
                capsule=capsule,
                binding=binding,
                source_tree=source,
                work_dir=work_root / uuid.uuid4().hex,
                role=role,
                execution_nonce=nonce,
            )
        except Exception as error:  # Preserve a bounded fail-closed receipt at the deep seam.
            return _failed_attempt(
                capsule,
                binding,
                role,
                TruthLabel.LOCAL,
                f"attempt orchestration failed ({type(error).__name__})",
                execution_nonce=nonce,
            )

    with ThreadPoolExecutor(max_workers=CONFIRMATIONS) as executor:
        futures = [executor.submit(one, index) for index in range(1, CONFIRMATIONS + 1)]
        return tuple(future.result() for future in futures)


def _execute_sweep(
    capsule: ReproCapsule,
    binding: AnchorBinding,
    source: Path,
    work_root: Path,
    role: WorldRole,
) -> CommitSweepReceipt:
    """Count the handler's store commits without a kill, then kill once after each of them."""
    work_root.mkdir(parents=True, exist_ok=False)
    nonce = uuid.uuid4().hex
    try:
        census = execute_no_fault_replay(
            capsule=capsule,
            binding=binding,
            source_tree=source,
            work_dir=work_root / uuid.uuid4().hex,
            execution_nonce=nonce,
            role=role,
        )
    except Exception as error:  # Preserve a fail-closed census receipt.
        census = _failed_census(capsule, binding, role, nonce, type(error).__name__)
    attempts: tuple[AttemptReceipt, ...] = ()
    if (
        census.execution_status is ExecutionStatus.COMPLETED
        and census.integrity_status is IntegrityStatus.VALID
    ):

        def one(index: int) -> AttemptReceipt:
            attempt_nonce = uuid.uuid4().hex
            try:
                return execute_attempt(
                    capsule=capsule,
                    binding=binding,
                    source_tree=source,
                    work_dir=work_root / uuid.uuid4().hex,
                    role=role,
                    execution_nonce=attempt_nonce,
                    kill_after_commit=index,
                )
            except Exception as error:  # Preserve a fail-closed sweep receipt.
                return _failed_attempt(
                    capsule,
                    binding,
                    role,
                    TruthLabel.LOCAL,
                    f"sweep orchestration failed ({type(error).__name__})",
                    execution_nonce=attempt_nonce,
                    kill_after_commit=index,
                )

        kill_points = range(1, len(census.first_delivery_operations) + 1)
        with ThreadPoolExecutor(max_workers=max(1, len(kill_points))) as executor:
            futures = [executor.submit(one, index) for index in kill_points]
            attempts = tuple(future.result() for future in futures)
    return CommitSweepReceipt.with_digest(
        role=role,
        capsule_digest=capsule.digest,
        binding_digest=binding.digest,
        census=census,
        attempts=attempts,
        observation=sweep_observation(census, attempts),
    )


def _failed_census(
    capsule: ReproCapsule, binding: AnchorBinding, role: WorldRole, nonce: str, error: str
) -> NoFaultReplayReceipt:
    now = datetime.now(UTC)
    return NoFaultReplayReceipt.with_digest(
        receipt_id=f"no-fault-{uuid.uuid4().hex}",
        role=role,
        execution_status=ExecutionStatus.SETUP_ERROR,
        integrity_status=IntegrityStatus.INCOMPLETE,
        observation=CrashObservation.NOT_OBSERVED,
        parent_capsule_digest=capsule.digest,
        contract_digest=capsule.contract_digest,
        binding_digest=binding.digest,
        tree_digest=binding.tree_digest,
        post_execution_tree_digest=binding.tree_digest,
        environment_digest=capsule.environment_digest,
        event_digest=capsule.event_digest,
        amount_cents=capsule.amount_cents,
        initial_database_digest=capsule.initial_database_digest,
        database_id=f"db-{uuid.uuid4().hex}",
        execution_nonce=nonce,
        started_at=now,
        ended_at=now,
        spawns=(),
        failure_detail=f"census orchestration failed ({error})",
    )


def _claimed_fix_verdict(
    observation: CrashObservation,
    attempts: tuple[AttemptReceipt, ...],
    sweep: CommitSweepReceipt | None,
    capsule: ReproCapsule,
) -> tuple[CrashVerdict, str]:
    """Decide for a candidate or corrected role from its boundary worlds and its sweep."""
    boundary = _confirmed_observation(attempts, capsule)
    if observation is CrashObservation.DUPLICATE_EFFECT:
        verdict = CrashVerdict.PATCH_FAILED_STILL_REPRODUCES
        if boundary is CrashObservation.DUPLICATE_EFFECT or sweep is None:
            return verdict, _summary(verdict)
        return verdict, _sweep_summary(sweep, capsule)
    if observation is CrashObservation.INVARIANT_FAILED:
        verdict = CrashVerdict.PATCH_FAILED_INVARIANT_BROKEN
        if boundary is CrashObservation.INVARIANT_FAILED or sweep is None:
            return verdict, _invariant_summary(attempts, capsule)
        return verdict, _sweep_summary(sweep, capsule)
    if observation is CrashObservation.EXACTLY_ONCE and sweep is not None:
        verdict = CrashVerdict.FIX_PROVEN_FOR_THIS_CAPSULE
        return verdict, _summary(verdict) + " " + _sweep_summary(sweep, capsule)
    if sweep is not None and boundary is CrashObservation.EXACTLY_ONCE:
        return CrashVerdict.EVIDENCE_INCOMPLETE, _sweep_summary(sweep, capsule)
    return CrashVerdict.EVIDENCE_INCOMPLETE, _unsupported_observation_summary(observation, attempts)


def _never_reached_checkpoint(attempts: tuple[AttemptReceipt, ...]) -> bool:
    return bool(attempts) and all(
        attempt.execution_status is ExecutionStatus.CHECKPOINT_NOT_REACHED for attempt in attempts
    )


def _unreached_summary(
    attempts: tuple[AttemptReceipt, ...], sweep: CommitSweepReceipt | None, capsule: ReproCapsule
) -> str:
    base = _unsupported_observation_summary(CrashObservation.NOT_OBSERVED, attempts)
    if sweep is None:
        return base
    census = sweep.census
    if census.final_snapshot is not None:
        observed = (
            f"Delivering {capsule.event_id} twice with no crash at all ended at "
            f"{_describe_final(census.final_snapshot, capsule)}"
        )
    elif census.first_delivery_snapshot is not None:
        redelivery = census.failure_detail or "the redelivery did not complete"
        observed = (
            f"Delivering {capsule.event_id} once with no crash at all ended at "
            f"{_describe_final(census.first_delivery_snapshot, capsule)}, and {redelivery}"
        )
    else:
        return base
    return (
        f"{base} {observed}; the crash test could not run because the handler never reached the "
        "credit, so this is reported, not judged."
    )


def _sweep_summary(sweep: CommitSweepReceipt, capsule: ReproCapsule) -> str:
    operations = sweep.census.first_delivery_operations
    schedule = f"{len(operations)} store commit{'s' if len(operations) != 1 else ''}"
    if sweep.observation is CrashObservation.EXACTLY_ONCE:
        return (
            f"The commit sweep killed the {sweep.role.value} once after each of its {schedule} "
            f"({', '.join(operations)}) and every replay ended exactly once."
        )
    census_final = sweep.census.final_snapshot
    if sweep.census.first_delivery_commit_count > len(operations):
        schedule += (
            f" (first {len(operations)} of {sweep.census.first_delivery_commit_count} recorded)"
        )
    if (
        sweep.census.execution_status is ExecutionStatus.COMPLETED
        and sweep.census.observation is sweep.observation
        and census_final is not None
    ):
        return (
            f"Delivering {capsule.event_id} twice with no crash at all ended at "
            f"{_describe_final(census_final, capsule)}. The handler is wrong before any kill; the "
            f"{REQUIRED_CONFIRMATIONS} capsule-boundary worlds passed only because the kill "
            "landed before the extra write."
        )
    failing = next(
        (attempt for attempt in sweep.attempts if attempt.observation is sweep.observation), None
    )
    if failing is not None and failing.kill_after_commit is not None:
        index = failing.kill_after_commit
        own = failing.first_worker_operations
        operation = own[index - 1] if index <= len(own) else "unknown"
        drift = ""
        if tuple(own[:index]) != tuple(operations[:index]):
            drift = (
                f" (this world's commits {', '.join(own) or 'none'} differ from the census's "
                f"{', '.join(operations)}: the handler's schedule is not deterministic)"
            )
        final = failing.final_snapshot
        observed = _describe_final(final, capsule) if final is not None else "no final state"
        return (
            f"Killed after store commit {index} of {len(operations)} ({operation}){drift} and "
            f"replayed: {observed}. The {REQUIRED_CONFIRMATIONS} capsule-boundary worlds passed, "
            "so this is a crash window the base did not have."
        )
    detail = sweep.census.failure_detail or next(
        (attempt.failure_detail for attempt in sweep.attempts if attempt.failure_detail),
        "a sweep world did not complete",
    )
    return f"The commit sweep could not complete: {detail}. No verdict is issued."


def _describe_final(final: CreditSnapshot, capsule: ReproCapsule) -> str:
    money_now = money(final.account_balance_cents)
    rows = f"{final.event_ledger_count} ledger row{'s' if final.event_ledger_count != 1 else ''}"
    marker = f"{final.event_marker_count} marker"
    if final.event_ledger_count == 0 and final.event_marker_count == 1:
        cause = f"{capsule.event_id} was marked processed but never credited, so the credit is lost"
    elif final.event_ledger_count == 2:
        cause = f"{capsule.event_id} was credited twice"
    elif final.event_ledger_count > 2:
        cause = f"{capsule.event_id} was credited {final.event_ledger_count} times"
    else:
        cause = "the final state matches neither exactly-once nor the capsule's duplicate shape"
    return f"{money_now} instead of {money(capsule.amount_cents)} ({rows}, {marker}): {cause}"


def _confirmed_observation(
    attempts: tuple[AttemptReceipt, ...], capsule: ReproCapsule
) -> CrashObservation:
    if len(attempts) != CONFIRMATIONS:
        return CrashObservation.NOT_OBSERVED
    if (
        len({item.database_id for item in attempts}) != CONFIRMATIONS
        or len({item.execution_nonce for item in attempts}) != CONFIRMATIONS
    ):
        return CrashObservation.NOT_OBSERVED
    observations = {item.observation for item in attempts}
    if len(observations) != 1:
        return CrashObservation.NOT_OBSERVED
    for attempt in attempts:
        if (
            attempt.execution_status is not ExecutionStatus.COMPLETED
            or attempt.integrity_status is not IntegrityStatus.VALID
            or attempt.capsule_digest != capsule.digest
            or attempt.event_digest != capsule.event_digest
            or attempt.environment_digest != capsule.environment_digest
            or attempt.pre_crash_snapshot is None
            or attempt.pre_crash_snapshot.account_balance_cents != 0
            or attempt.checkpoint_snapshot is None
            or attempt.checkpoint_snapshot.account_balance_cents != capsule.amount_cents
            or attempt.checkpoint_snapshot.event_ledger_count != 1
            or attempt.post_kill_snapshot is None
            or attempt.post_kill_snapshot.digest != attempt.checkpoint_snapshot.digest
            or len(attempt.spawns) != 2
            or attempt.spawns[0].exit_code != -9
            or attempt.spawns[0].event_digest != attempt.spawns[1].event_digest
        ):
            return CrashObservation.NOT_OBSERVED
    return next(iter(observations))


def _failed_attempt(
    capsule: ReproCapsule,
    binding: AnchorBinding,
    role: WorldRole,
    transport: TruthLabel,
    detail: str,
    *,
    execution_nonce: str | None = None,
    kill_after_commit: int | None = None,
) -> AttemptReceipt:
    started = datetime.now(UTC)
    ended = datetime.now(UTC)
    status = (
        ExecutionStatus.UNSUPPORTED if transport is TruthLabel.LIVE else ExecutionStatus.SETUP_ERROR
    )
    return AttemptReceipt.with_digest(
        receipt_id=f"attempt-{uuid.uuid4().hex}",
        role=role,
        transport=transport,
        execution_status=status,
        integrity_status=IntegrityStatus.INCOMPLETE,
        observation=CrashObservation.NOT_OBSERVED,
        capsule_digest=capsule.digest,
        contract_digest=capsule.contract_digest,
        binding_digest=binding.digest,
        tree_digest=binding.tree_digest,
        post_execution_tree_digest=binding.tree_digest,
        environment_digest=capsule.environment_digest,
        event_digest=capsule.event_digest,
        amount_cents=capsule.amount_cents,
        initial_database_digest=capsule.initial_database_digest,
        database_id=f"db-{uuid.uuid4().hex}",
        execution_nonce=execution_nonce or uuid.uuid4().hex,
        started_at=started,
        ended_at=ended,
        timeline=(
            TimelineEntry(state=TimelineState.PREFLIGHT, timestamp=started),
            TimelineEntry(state=TimelineState.FAILED, timestamp=ended, detail=detail[:500]),
        ),
        spawns=(),
        checkpoint_reached=False,
        kill_after_commit=kill_after_commit,
        replay_acknowledged=False,
        failure_detail=detail[:1_000],
    )


def _publish(
    run_id: str,
    started_at: datetime,
    capsule: ReproCapsule,
    contract: RetryContract,
    bindings: tuple[AnchorBinding, ...],
    attempts: tuple[AttemptReceipt, ...],
    verdict: CrashVerdict,
    summary: str,
    *,
    anchor_resolutions: tuple[AnchorResolutionReceipt, ...] = (),
    hypothesis_receipts: tuple[HypothesisReceipt, ...] = (),
    minimization_receipts: tuple[MinimizationReceipt, ...] = (),
    transport: TruthLabel | None = None,
    proposal: ContractProposal | None = None,
    sweeps: tuple[CommitSweepReceipt, ...] = (),
    author: PatchProposal | None = None,
) -> CrashCheckResult:
    if capsule.engine_code_digest != engine_code_digest():
        raise CrashCheckError("capsule engine digest differs from the installed engine")
    if minimization_receipts and capsule.minimization_trace != (
        minimization_receipts[0].trace_digest,
    ):
        raise CrashCheckError(
            "capsule one-action deletion trace differs from its fixture necessity receipt"
        )
    root = _absolute(Path(os.environ.get("NEMISIS_ARTIFACT_ROOT", ".nemisis")))
    run_relative = Path("runs") / run_id
    repro_relative = Path("repros") / "double-credit" / capsule.digest
    run_dir = root / run_relative
    repro_dir = root / repro_relative
    artifacts = {
        "capsule": (repro_relative / "capsule.json").as_posix(),
        "contract": (repro_relative / "contract.json").as_posix(),
        "event": (repro_relative / "event.json").as_posix(),
        "manifest": (run_relative / "manifest.json").as_posix(),
        "metadata": (repro_relative / "metadata.json").as_posix(),
    }
    if attempts:
        artifacts["report"] = (run_relative / "report.html").as_posix()
    if anchor_resolutions:
        artifacts["anchor_resolution"] = (run_relative / "anchor-resolution.json").as_posix()
    if hypothesis_receipts:
        artifacts["hunt"] = (repro_relative / "hunt.json").as_posix()
    if minimization_receipts:
        artifacts["minimization"] = (run_relative / "minimization.json").as_posix()
    if anchor_resolutions:
        execution = ExecutionStatus.SETUP_ERROR
        integrity = IntegrityStatus.INCOMPLETE
    else:
        execution = (
            ExecutionStatus.COMPLETED
            if all(item.execution_status is ExecutionStatus.COMPLETED for item in attempts)
            else next(
                item.execution_status
                for item in attempts
                if item.execution_status is not ExecutionStatus.COMPLETED
            )
        )
        integrity = (
            IntegrityStatus.VALID
            if all(item.integrity_status is IntegrityStatus.VALID for item in attempts)
            else (
                IntegrityStatus.INVALID
                if any(item.integrity_status is IntegrityStatus.INVALID for item in attempts)
                else IntegrityStatus.INCOMPLETE
            )
        )
    if transport is None:
        if not attempts:
            raise CrashCheckError("attempt-free publication requires an explicit transport")
        result_transport = attempts[0].transport
    else:
        result_transport = transport
    exercised = (
        bool(attempts)
        and execution is ExecutionStatus.COMPLETED
        and integrity is IntegrityStatus.VALID
    )
    if exercised:
        artifacts["regression_test"] = (repro_relative / "test_repro.py").as_posix()
    result = CrashCheckResult.with_digest(
        run_id=run_id,
        transport=result_transport,
        execution_status=execution,
        integrity_status=integrity,
        verdict=verdict,
        capsule_digest=capsule.digest,
        engine_code_digest=capsule.engine_code_digest,
        anchor_resolutions=anchor_resolutions,
        hypothesis_receipts=hypothesis_receipts,
        minimization_receipts=minimization_receipts,
        bindings=bindings,
        attempts=attempts,
        sweeps=sweeps,
        candidate_author=author,
        started_at=started_at,
        ended_at=datetime.now(UTC),
        summary=summary,
        engine_source_commit=_engine_source_commit(),
        artifacts=artifacts,
    )
    _ensure_directory(run_dir, exist_ok=False)
    _ensure_directory(repro_dir, exist_ok=True)
    _write_exact(repro_dir / "capsule.json", canonical_json(capsule) + b"\n")
    _write_exact(repro_dir / "contract.json", canonical_json(contract) + b"\n")
    _write_exact(repro_dir / "event.json", canonical_json(load_event()) + b"\n")
    metadata = {
        "capsule_digest": capsule.digest,
        "contract_digest": contract.digest,
        "engine_code_digest": capsule.engine_code_digest,
        "fault_boundary": capsule.fault_boundary,
        "minimization_trace": capsule.minimization_trace,
        "schema_version": "nemisis.crashcheck.repro.v1",
        "truth_label": capsule.truth_label,
    }
    _write_exact(repro_dir / "metadata.json", canonical_json(metadata) + b"\n")
    if exercised:
        _write_exact(repro_dir / "test_repro.py", _regression_asset(capsule))
    if anchor_resolutions:
        _write_exact(
            run_dir / "anchor-resolution.json",
            canonical_json(anchor_resolutions[0]) + b"\n",
        )
    if hypothesis_receipts:
        hypothesis_trace = _hypothesis_trace(hypothesis_receipts)
        hunt = {
            "hypotheses": [
                {
                    "canonical_rank": receipt.canonical_rank,
                    "fault_boundary": receipt.fault_boundary,
                    "hypothesis_id": receipt.hypothesis_id,
                    "provisional_capsule_digest": receipt.provisional_capsule_digest,
                    "reproduced": receipt.reproduced,
                    "selected": receipt.selected,
                    "trace_digest": trace_digest,
                    "trusted_operation_count": receipt.trusted_operation_count,
                }
                for receipt, trace_digest in zip(hypothesis_receipts, hypothesis_trace, strict=True)
            ],
            "schema_version": "nemisis.crashcheck.hunt.v1",
        }
        _write_exact(repro_dir / "hunt.json", canonical_json(hunt) + b"\n")
    if minimization_receipts:
        _write_exact(
            run_dir / "minimization.json",
            canonical_json(minimization_receipts[0]) + b"\n",
        )
    manifest = {
        "bindings": [item.model_dump(mode="json") for item in bindings],
        "capsule": capsule.model_dump(mode="json"),
        "contract": contract.model_dump(mode="json"),
        "contract_proposal": (proposal.model_dump(mode="json") if proposal is not None else None),
        "result": result.model_dump(mode="json"),
        "schema_version": "nemisis.crashcheck.run.v1",
    }
    _write_exact(
        run_dir / "manifest.json",
        json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False).encode() + b"\n",
    )
    if attempts:
        with tempfile.TemporaryDirectory(prefix="nemisis-report-") as temporary:
            rendered = Path(temporary) / "report.html"
            write_crash_report(result, capsule, rendered, proposal=proposal)
            _write_exact(run_dir / "report.html", rendered.read_bytes())
    return result


def _materialize_source(value: str | Path, destination: Path) -> _Source:
    ref = str(value)
    if ref in FIXTURE_REFS:
        fixture = materialize_fixture(ref, destination)
        return _Source(ref, fixture.path, fixture.tree_digest, ref, None)
    if ref.startswith("fixture:"):
        raise CrashCheckError(f"unknown fixture ref {ref!r}; known: {', '.join(FIXTURE_REFS)}")
    path = Path(value)
    try:
        path_status = path.lstat()
    except FileNotFoundError:
        path_status = None
    if path_status is not None and stat.S_ISLNK(path_status.st_mode):
        raise CrashCheckError("source root must not be a symlink")
    if path_status is not None and stat.S_ISDIR(path_status.st_mode):
        source = path.resolve()
        config = _read_source_config(source)
        author = _read_source_file(source, AUTHOR_RECEIPT_PATH)
        _copy_tree(source, destination)
        digest = sha256_tree(destination)
        return _Source(str(path), destination.resolve(), digest, digest, config, author)
    try:
        repository = _git_repository()
        commit = (
            _git(
                repository,
                "rev-parse",
                "--verify",
                "--end-of-options",
                f"{ref}^{{commit}}",
            )
            .decode()
            .strip()
        )
    except CrashCheckError as error:
        raise CrashCheckError(
            f"{error} (ref {ref!r} is not a packaged fixture ref, an existing directory, or a "
            "resolvable Git commit)"
        ) from error
    _warn_if_working_tree_is_dirty(repository, ref, commit)
    archive = _git(repository, "archive", "--format=tar", commit)
    if not archive or len(archive) > MAX_SOURCE_ARCHIVE_BYTES:
        raise CrashCheckError("resolved Git source archive is empty or oversized")
    config, author = _extract_archive(archive, destination)
    return _Source(ref, destination.resolve(), sha256_tree(destination), commit, config, author)


def _read_source_config(source: Path) -> bytes | None:
    return _read_source_file(source, CONFIG_PATH)


def _read_source_file(source: Path, relative: Path) -> bytes | None:
    """Read one bounded regular file under a source's ``.nemisis`` directory, if present."""
    metadata = source / relative.parent
    try:
        metadata_status = metadata.lstat()
    except FileNotFoundError:
        return None
    if not stat.S_ISDIR(metadata_status.st_mode):
        raise CrashCheckError("base .nemisis metadata path is not a regular directory")
    target = source / relative
    try:
        target_status = target.lstat()
    except FileNotFoundError:
        return None
    if not stat.S_ISREG(target_status.st_mode) or target_status.st_size > MAX_CONFIG_BYTES:
        raise CrashCheckError(f"base {relative.as_posix()} is not a bounded regular file")
    try:
        return target.read_bytes()
    except OSError as error:
        raise CrashCheckError(f"base {relative.as_posix()} could not be read") from error


def _copy_tree(source: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=False)
    file_count = 0
    total_bytes = 0
    for path in sorted(source.rglob("*")):
        relative = path.relative_to(source)
        if any(part in _IGNORED for part in relative.parts):
            continue
        status = path.lstat()
        if stat.S_ISLNK(status.st_mode):
            raise CrashCheckError(f"source tree contains a symlink: {relative.as_posix()}")
        if stat.S_ISDIR(status.st_mode):
            continue
        if not stat.S_ISREG(status.st_mode):
            raise CrashCheckError(f"source tree contains a non-regular file: {relative.as_posix()}")
        file_count += 1
        total_bytes += status.st_size
        if file_count > MAX_SOURCE_FILES or total_bytes > MAX_SOURCE_ARCHIVE_BYTES:
            raise CrashCheckError("source tree exceeds the supported file or byte limit")
        output = safe_destination(destination, safe_relative_path(relative.as_posix()))
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, output)


def _extract_archive(content: bytes, destination: Path) -> tuple[bytes | None, bytes | None]:
    destination.mkdir(parents=True, exist_ok=False)
    sidecars: dict[str, bytes] = {}
    sidecar_names = {CONFIG_PATH.as_posix(): "config", AUTHOR_RECEIPT_PATH.as_posix(): "author"}
    file_count = 0
    try:
        with tarfile.open(fileobj=BytesIO(content), mode="r:") as archive:
            for member in archive.getmembers():
                relative = safe_relative_path(member.name)
                if relative.as_posix() in sidecar_names:
                    name = sidecar_names[relative.as_posix()]
                    if name in sidecars or not member.isfile():
                        raise CrashCheckError(
                            f"Git {name} sidecar is duplicated or not a regular file"
                        )
                    file_count += 1
                    if file_count > MAX_SOURCE_FILES:
                        raise CrashCheckError("Git source archive exceeds the supported file limit")
                    extracted = archive.extractfile(member)
                    if extracted is None:
                        raise CrashCheckError(f"Git {name} sidecar is unreadable")
                    sidecars[name] = extracted.read(MAX_CONFIG_BYTES + 1)
                    if len(sidecars[name]) > MAX_CONFIG_BYTES:
                        raise CrashCheckError(f"Git {name} sidecar is oversized")
                    continue
                if any(part in _IGNORED for part in relative.parts):
                    continue
                if member.isdir():
                    continue
                if not member.isfile():
                    raise CrashCheckError("Git source archive contains a non-regular file")
                file_count += 1
                if file_count > MAX_SOURCE_FILES:
                    raise CrashCheckError("Git source archive exceeds the supported file limit")
                extracted = archive.extractfile(member)
                if extracted is None:
                    raise CrashCheckError("Git source archive member is unreadable")
                output = safe_destination(destination, relative)
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_bytes(extracted.read())
    except tarfile.TarError as error:
        raise CrashCheckError("Git source archive is malformed") from error
    return sidecars.get("config"), sidecars.get("author")


def _warn_if_working_tree_is_dirty(repository: Path, ref: str, commit: str) -> None:
    """Evidence binds the commit, not the checkout; say so when they differ."""
    try:
        dirty = subprocess.run(
            ["git", "-C", str(repository), "status", "--porcelain", "--untracked-files=no"],
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return
    if dirty:
        print(
            f"warning: working tree has uncommitted changes; {ref} was evaluated at commit "
            f"{commit}, not the checkout",
            file=sys.stderr,
        )


def _git_repository() -> Path:
    try:
        return Path(
            subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                capture_output=True,
                text=True,
                timeout=10,
                check=True,
            ).stdout.strip()
        ).resolve()
    except (OSError, subprocess.SubprocessError) as error:
        raise CrashCheckError("ordinary refs require invocation inside a Git repository") from error


def _git(repository: Path, *args: str) -> bytes:
    try:
        return subprocess.run(
            ["git", "-C", str(repository), *args],
            capture_output=True,
            timeout=30,
            check=True,
        ).stdout
    except (OSError, subprocess.SubprocessError) as error:
        raise CrashCheckError("Git source ref could not be resolved exactly") from error


def _load_config(path: Path) -> tuple[dict[str, object], RetryContract]:
    try:
        status = path.lstat()
        if not stat.S_ISREG(status.st_mode) or status.st_size > MAX_CONFIG_BYTES:
            raise CrashCheckError("Nemisis config is not a bounded regular file")
        content = path.read_bytes()
    except OSError as error:
        raise CrashCheckError("Nemisis config is not valid JSON") from error
    return _load_config_bytes(content)


def _load_config_bytes(content: bytes) -> tuple[dict[str, object], RetryContract]:
    if len(content) > MAX_CONFIG_BYTES:
        raise CrashCheckError("Nemisis config is oversized")
    try:
        value = cast(object, json.loads(content))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise CrashCheckError("Nemisis config is not valid JSON") from error
    expected = {"base", "contract", "issue", "scenario_id", "schema_version", "status", "target"}
    if not isinstance(value, dict) or set(value) != expected:
        raise CrashCheckError("Nemisis config has unknown or missing fields")
    payload = cast(dict[str, object], value)
    if payload["schema_version"] != "1" or payload["status"] not in {"DRAFT", "ACCEPTED"}:
        raise CrashCheckError("Nemisis config version or status is invalid")
    try:
        contract = RetryContract.model_validate_json(canonical_json(payload["contract"]))
    except ValueError as error:
        raise CrashCheckError("Nemisis config contract is invalid") from error
    expected_status = "ACCEPTED" if contract.accepted else "DRAFT"
    if (
        payload["scenario_id"] != contract.scenario_id
        or payload["target"] != contract.target
        or payload["status"] != expected_status
    ):
        raise CrashCheckError("Nemisis config metadata contradicts its contract")
    _require_contract_label(contract)
    return payload, contract


def _require_contract_label(contract: RetryContract) -> None:
    """Only the packaged contract is FIXTURE; accepted user contracts are LOCAL; drafts PLANNED."""
    if not contract.accepted:
        expected = TruthLabel.PLANNED
    elif contract.digest == _audited_contract().digest:
        expected = TruthLabel.FIXTURE
    else:
        expected = TruthLabel.LOCAL
    if contract.truth_label is not expected:
        raise CrashCheckError(
            f"contract truth label {contract.truth_label.value} contradicts its acceptance state; "
            f"expected {expected.value}"
        )


def _write_exact(path: Path, content: bytes, *, replace: bool = False) -> None:
    absolute = _absolute(path)
    parent = _open_directory(absolute.parent)
    try:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC
        try:
            descriptor = os.open(absolute.name, flags, 0o600, dir_fd=parent)
        except FileExistsError:
            existing = _read_regular(parent, absolute.name, maximum=len(content) + 1)
            if existing == content:
                return
            if not replace:
                raise CrashCheckError(
                    f"refusing to overwrite different evidence: {absolute}"
                ) from None
            _replace_exact(parent, absolute.name, content)
            return
        except OSError as error:
            raise CrashCheckError(f"unsafe evidence target: {absolute}") from error
        try:
            _write_descriptor(descriptor, content)
        except BaseException:
            with suppress(OSError):
                os.unlink(absolute.name, dir_fd=parent)
            raise
    finally:
        os.close(parent)


def _absolute(path: Path) -> Path:
    return Path(os.path.abspath(path))


def _open_directory(path: Path) -> int:
    absolute = _absolute(path)
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    descriptor = os.open("/", flags)
    try:
        for part in absolute.parts[1:]:
            try:
                child = os.open(part, flags, dir_fd=descriptor)
            except FileNotFoundError:
                with suppress(FileExistsError):
                    os.mkdir(part, 0o700, dir_fd=descriptor)
                child = os.open(part, flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
    except OSError as error:
        os.close(descriptor)
        raise CrashCheckError(f"unsafe evidence parent: {absolute}") from error
    return descriptor


def _ensure_directory(path: Path, *, exist_ok: bool) -> None:
    absolute = _absolute(path)
    parent = _open_directory(absolute.parent)
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    try:
        try:
            os.mkdir(absolute.name, 0o700, dir_fd=parent)
        except FileExistsError:
            if not exist_ok:
                raise CrashCheckError(f"evidence directory already exists: {absolute}") from None
        try:
            child = os.open(absolute.name, flags, dir_fd=parent)
        except OSError as error:
            raise CrashCheckError(f"unsafe evidence directory: {absolute}") from error
        else:
            os.close(child)
    finally:
        os.close(parent)


def _read_regular(parent: int, name: str, *, maximum: int) -> bytes:
    try:
        descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=parent)
    except OSError as error:
        raise CrashCheckError(f"unsafe evidence target: {name}") from error
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise CrashCheckError(f"unsafe evidence target: {name}")
        with os.fdopen(descriptor, "rb") as source:
            return source.read(maximum)
    except BaseException:
        with suppress(OSError):
            os.close(descriptor)
        raise


def _write_descriptor(descriptor: int, content: bytes) -> None:
    with os.fdopen(descriptor, "wb") as output:
        os.fchmod(output.fileno(), 0o600)
        output.write(content)
        output.flush()
        os.fsync(output.fileno())


def _replace_exact(parent: int, name: str, content: bytes) -> None:
    temporary = f".{name}.{uuid.uuid4().hex}.tmp"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC
    try:
        descriptor = os.open(temporary, flags, 0o600, dir_fd=parent)
        _write_descriptor(descriptor, content)
        os.replace(temporary, name, src_dir_fd=parent, dst_dir_fd=parent)
    except OSError as error:
        raise CrashCheckError(f"atomic evidence replacement failed: {name}") from error
    finally:
        with suppress(FileNotFoundError):
            os.unlink(temporary, dir_fd=parent)


def _regression_asset(capsule: ReproCapsule) -> bytes:
    return f'''"""Nemisis integration/fault regression.

Capsule: {capsule.digest}
This test requires the trusted Nemisis process-kill runner; it is not a unit test.
"""

import os
from pathlib import Path

from nemisis import CrashVerdict, replay


def test_repro() -> None:
    source = os.environ.get("NEMISIS_REPRO_SOURCE", ".")
    role = os.environ.get("NEMISIS_REPRO_ROLE", "candidate")
    result = replay(Path(__file__).with_name("capsule.json"), source, role=role)
    assert result.verdict is CrashVerdict.FIX_PROVEN_FOR_THIS_CAPSULE
'''.encode()


def _untrusted_fork() -> bool:
    if os.environ.get("GITHUB_EVENT_NAME") != "pull_request":
        return False
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    if not event_path:
        return True
    try:
        event = json.loads(Path(event_path).read_text())
        pull = event["pull_request"]
        return bool(pull["head"]["repo"]["full_name"] != pull["base"]["repo"]["full_name"])
    except (OSError, KeyError, TypeError, json.JSONDecodeError):
        return True


def _live_blocker() -> str:
    result = doctor("live")
    blocked = [item["name"] for item in result["checks"] if item["status"] != "PASS"]
    if blocked:
        return f"LIVE BLOCKED: {', '.join(blocked)}. Local execution was not substituted."
    return (
        "LIVE BLOCKED: genuine CrashCheck provider receipt unavailable. Local was not substituted."
    )


def _engine_source_commit() -> str | None:
    action_ref = os.environ.get("NEMISIS_ENGINE_SOURCE_COMMIT")
    if (
        action_ref is not None
        and len(action_ref) == 40
        and all(character in "0123456789abcdef" for character in action_ref)
    ):
        return action_ref
    return source_commit()


def _run_id(mode: str) -> str:
    return f"{mode}-{datetime.now(UTC):%Y%m%dT%H%M%S}-{uuid.uuid4().hex[:8]}"


def _summary(verdict: CrashVerdict) -> str:
    return {
        CrashVerdict.BUG_REPRODUCED: (
            "The base replayed evt_1042 to a durable +$50 duplicate effect."
        ),
        CrashVerdict.PATCH_FAILED_STILL_REPRODUCES: (
            "The candidate replayed evt_1042 to a durable +$50 duplicate effect."
        ),
        CrashVerdict.PATCH_FAILED_INVARIANT_BROKEN: (
            "The candidate completed every world in a state that is neither exactly-once nor "
            "the capsule's duplicate."
        ),
        CrashVerdict.FIX_PROVEN_FOR_THIS_CAPSULE: (
            "Five fresh worlds ended at exactly +$25, one ledger effect, and one marker."
        ),
        CrashVerdict.EVIDENCE_INCOMPLETE: "Required crash evidence was incomplete.",
        CrashVerdict.UNSUPPORTED_TARGET: "The supplied target is unsupported.",
    }[verdict]


__all__ = ["accept_contract", "check", "initialize", "replay"]
