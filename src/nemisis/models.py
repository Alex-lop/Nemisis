"""Evidence contracts. Models propose; these records never delegate acceptance to a model."""

from __future__ import annotations

import hashlib
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
SafeId = Annotated[str, Field(min_length=1, max_length=120, pattern=r"^[A-Za-z0-9_.:-]+$")]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class RuntimeMode(StrEnum):
    LOCAL = "local"
    LIVE = "live"


class TruthLabel(StrEnum):
    LIVE = "LIVE"
    RECORDED_LIVE = "RECORDED_LIVE"
    LOCAL = "LOCAL"
    FIXTURE = "FIXTURE"
    MOCKED = "MOCKED"
    PLANNED = "PLANNED"
    BLOCKED = "BLOCKED"


class WorldKind(StrEnum):
    BASE = "base"
    CANDIDATE = "candidate"
    REPAIR = "repair"


class Outcome(StrEnum):
    PASS = "PASS"
    ASSERTION_FAIL = "ASSERTION_FAIL"
    ERROR = "ERROR"
    TIMEOUT = "TIMEOUT"
    NOT_RUN = "NOT_RUN"


class ExpectedRelation(StrEnum):
    CHANGE_WITNESS = "CHANGE_WITNESS"
    INVARIANT = "INVARIANT"


class Classification(StrEnum):
    SUPPORTED = "SUPPORTED"
    UNRESOLVED = "UNRESOLVED"
    REGRESSION = "REGRESSION"
    NON_DISCRIMINATING = "NON_DISCRIMINATING"
    INCOMPLETE = "INCOMPLETE"


class PatchValidationStatus(StrEnum):
    VALID = "VALID"
    REJECTED = "REJECTED"


class ArtifactStatus(StrEnum):
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"


class RunState(StrEnum):
    INTAKE = "INTAKE"
    CLAIM_GENERATION = "CLAIM_GENERATION"
    WORLD_PREPARATION = "WORLD_PREPARATION"
    EXECUTION = "EXECUTION"
    CLASSIFICATION = "CLASSIFICATION"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"


class VerificationRequest(StrictModel):
    run_id: SafeId
    source_identity: str = Field(min_length=1, max_length=500)
    base_ref: str = Field(min_length=1, max_length=200)
    base_digest: Sha256
    candidate_patch_location: str = Field(min_length=1, max_length=500)
    candidate_patch_digest: Sha256
    ticket: str = Field(min_length=1, max_length=50_000)
    ticket_digest: Sha256
    requested_runtime_mode: RuntimeMode
    max_generated_tests: int = Field(ge=1, le=8)
    repair_allowed: bool = False

    @model_validator(mode="after")
    def ticket_hash_matches(self) -> VerificationRequest:
        if hashlib.sha256(self.ticket.encode()).hexdigest() != self.ticket_digest:
            raise ValueError("ticket digest does not match ticket text")
        return self


class CandidatePatchSpec(StrictModel):
    canonical_patch: bytes = Field(max_length=100_000)
    digest: Sha256
    declared_files: tuple[str, ...] = Field(max_length=20)
    total_bytes: int = Field(ge=1, le=100_000)
    resolved_base_identity: Sha256
    allowed_text_modifications: tuple[str, ...] = Field(max_length=20)
    resulting_tree_digest: Sha256 | None = None
    validation_status: PatchValidationStatus
    rejection_reason: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def rejection_is_explained(self) -> CandidatePatchSpec:
        if len(self.canonical_patch) != self.total_bytes:
            raise ValueError("patch byte count does not match canonical patch")
        if hashlib.sha256(self.canonical_patch).hexdigest() != self.digest:
            raise ValueError("patch digest does not match canonical patch")
        if set(self.declared_files) != set(self.allowed_text_modifications):
            raise ValueError("declared and allowed patch files differ")
        if self.validation_status is PatchValidationStatus.REJECTED and not self.rejection_reason:
            raise ValueError("a rejected patch requires a rejection reason")
        if self.validation_status is PatchValidationStatus.VALID and self.rejection_reason:
            raise ValueError("a valid patch cannot have a rejection reason")
        return self


class ClaimSpec(StrictModel):
    claim_id: SafeId
    statement: str = Field(min_length=1, max_length=1_000)
    rationale: str = Field(min_length=1, max_length=2_000)
    risk_category: str = Field(min_length=1, max_length=100)
    expected_relation: ExpectedRelation
    referenced_files: tuple[str, ...] = Field(max_length=20)
    referenced_symbols: tuple[str, ...] = Field(max_length=20)
    linked_test_ids: tuple[SafeId, ...] = Field(min_length=1, max_length=8)


class GeneratedTestSpec(StrictModel):
    test_id: SafeId
    claim_id: SafeId
    path: str = Field(min_length=1, max_length=240)
    test_name: SafeId
    language: Literal["python"]
    framework: Literal["pytest"]
    content: str = Field(min_length=1, max_length=30_000)
    content_hash: Sha256
    expected_relation: ExpectedRelation

    @model_validator(mode="after")
    def content_hash_matches(self) -> GeneratedTestSpec:
        if hashlib.sha256(self.content.encode()).hexdigest() != self.content_hash:
            raise ValueError("generated test content hash mismatch")
        return self


class BundleFile(StrictModel):
    path: str = Field(min_length=1, max_length=240)
    content: str = Field(min_length=1, max_length=30_000)
    content_hash: Sha256

    @model_validator(mode="after")
    def content_hash_matches(self) -> BundleFile:
        if hashlib.sha256(self.content.encode()).hexdigest() != self.content_hash:
            raise ValueError("bundle file content hash mismatch")
        return self


class VerificationBundle(StrictModel):
    claims: tuple[ClaimSpec, ...] = Field(min_length=1, max_length=16)
    baseline_tests: tuple[GeneratedTestSpec, ...] = Field(min_length=1, max_length=16)
    generated_tests: tuple[GeneratedTestSpec, ...] = Field(min_length=1, max_length=8)
    harness_files: tuple[BundleFile, ...] = Field(min_length=1, max_length=8)
    runner_id: SafeId
    runner_argv: tuple[str, ...] = Field(min_length=1, max_length=20)
    runner_version: str = Field(min_length=1, max_length=100)
    result_format: Literal["junit-xml"]
    parser_version: str = Field(min_length=1, max_length=100)
    parser_digest: Sha256
    dependency_lock_digest: Sha256
    model_id: str = Field(min_length=1, max_length=200)
    prompt_template_digest: Sha256
    model_input_digest: Sha256 | None = None
    model_response_digest: Sha256 | None = None
    digest: Sha256


class WorldReceipt(StrictModel):
    world_id: SafeId
    kind: WorldKind
    parent_world_id: SafeId | None = None
    parent_operation_id: str | None = Field(default=None, max_length=200)
    preparation_operation_id: str | None = Field(default=None, max_length=200)
    image_uuid: str | None = Field(default=None, max_length=200)
    bundle_object_id: str | None = Field(default=None, max_length=200)
    bundle_archive_digest: Sha256 | None = None
    base_digest: Sha256
    candidate_patch_digest: Sha256
    ticket_digest: Sha256
    model_id: str = Field(min_length=1, max_length=200)
    prompt_template_digest: Sha256
    model_input_digest: Sha256 | None = None
    generated_test_digest: Sha256
    verification_bundle_digest: Sha256
    patch_applied: bool
    resulting_tree_digest: Sha256
    runtime_label: TruthLabel
    attempt: int = Field(ge=1)


class ResourceMetrics(StrictModel):
    provider_values: dict[str, int | float] = Field(default_factory=dict)


class ExecutionReceipt(StrictModel):
    receipt_id: SafeId
    test_id: SafeId
    world_id: SafeId
    operation_id: str | None = Field(default=None, max_length=200)
    source_image_uuid: str | None = Field(default=None, max_length=200)
    result_image_uuid: str | None = Field(default=None, max_length=200)
    started_at: datetime
    ended_at: datetime
    duration_ms: int = Field(ge=0)
    exit_code: int | None
    outcome: Outcome
    collection_status: Outcome
    stdout_excerpt: str = Field(max_length=4_000)
    stderr_excerpt: str = Field(max_length=4_000)
    stdout_hash: Sha256
    stderr_hash: Sha256
    result_report_hash: Sha256
    metrics: ResourceMetrics | None = None
    runner_version: str = Field(min_length=1, max_length=100)
    command_id: SafeId
    verification_bundle_digest: Sha256
    attempt: int = Field(ge=1)
    is_stale: bool = False

    @model_validator(mode="after")
    def timestamps_are_ordered(self) -> ExecutionReceipt:
        if self.ended_at < self.started_at:
            raise ValueError("execution ended before it started")
        return self


class MatrixCell(StrictModel):
    claim_id: SafeId
    test_id: SafeId
    expected_relation: ExpectedRelation
    base_outcome: Outcome
    candidate_outcome: Outcome
    repair_outcome: Outcome | None = None
    classification: Classification
    base_receipt_id: SafeId
    candidate_receipt_id: SafeId
    repair_receipt_id: SafeId | None = None
    evidence_complete: bool


class ClaimResult(StrictModel):
    claim_id: SafeId
    expected_relation: ExpectedRelation
    test_ids: tuple[SafeId, ...] = Field(min_length=1)
    classifications: tuple[Classification, ...] = Field(min_length=1)
    supported: bool
    evidence_complete: bool


class ArtifactReceipt(StrictModel):
    status: ArtifactStatus
    world_id: SafeId
    image_uuid: str | None = Field(default=None, max_length=200)
    final_patch_digest: Sha256
    source_identity: str = Field(min_length=1, max_length=500)
    base_digest: Sha256
    candidate_patch_digest: Sha256
    generated_test_digest: Sha256
    verification_bundle_digest: Sha256
    verification_receipt_ids: tuple[SafeId, ...] = Field(min_length=1)
    producing_attempt: int = Field(ge=1)
    source_commit: str | None = Field(default=None, max_length=64)
    reason: str = Field(min_length=1, max_length=1_000)


class ModelCallReceipt(StrictModel):
    truth_label: TruthLabel
    timestamp: datetime
    endpoint_region: str = Field(min_length=1, max_length=100)
    model_id: str = Field(min_length=1, max_length=200)
    input_digest: Sha256
    prompt_template_digest: Sha256
    latency_ms: int | None = Field(default=None, ge=0)
    outcome: str = Field(min_length=1, max_length=200)
    schema_valid: bool
    response_digest: Sha256 | None = None


class RunManifest(StrictModel):
    schema_version: Literal["1"] = "1"
    request: VerificationRequest
    runtime_mode: RuntimeMode
    truth_label: TruthLabel
    endpoint_region: str | None = Field(default=None, max_length=100)
    model_id: str | None = Field(default=None, max_length=200)
    prompt_template_version: str
    prompt_template_digest: Sha256
    model_call: ModelCallReceipt | None
    current_attempt: int = Field(ge=1)
    bundle: VerificationBundle
    candidate_tree_digest: Sha256
    worlds: tuple[WorldReceipt, ...]
    executions: tuple[ExecutionReceipt, ...]
    matrix: tuple[MatrixCell, ...]
    claims: tuple[ClaimResult, ...]
    artifact: ArtifactReceipt
    state: RunState
    terminal_reason: str = Field(min_length=1, max_length=1_000)
    source_commit: str | None = Field(default=None, max_length=64)
