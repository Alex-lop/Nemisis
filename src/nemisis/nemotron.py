"""Bounded Token Factory client for Nemotron-generated verification tests."""

from __future__ import annotations

import ast
import json
import os
import re
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import PurePosixPath
from time import monotonic
from typing import Literal, Protocol, cast
from urllib.parse import urlparse

from openai import OpenAI
from pydantic import Field, ValidationError

from nemisis.hashing import sha256_bytes, sha256_json, sha256_text
from nemisis.models import (
    ClaimSpec,
    ExpectedRelation,
    GeneratedTestSpec,
    ModelCallReceipt,
    SafeId,
    StrictModel,
    TruthLabel,
)

DEFAULT_BASE_URL = "https://api.tokenfactory.nebius.com/v1/"
DEFAULT_MODEL_ID = "nvidia/nemotron-3-super-120b-a12b"
API_KEY_ENV = "NEBIUS_API_KEY"
BASE_URL_ENV = "NEMISIS_TOKEN_FACTORY_BASE_URL"
MODEL_ID_ENV = "NEMISIS_MODEL_ID"

TIMEOUT_SECONDS = 120.0
MAX_RETRIES = 2
MAX_OUTPUT_TOKENS = 8_192
MAX_GENERATED_TESTS = 8
MAX_TICKET_BYTES = 50_000
MAX_DIFF_BYTES = 100_000
MAX_TEST_BYTES = 30_000
MAX_TOTAL_TEST_BYTES = 60_000
MAX_RESPONSE_BYTES = 150_000
MAX_BASE_MATERIAL_BYTES = 100_000
MAX_CONTRACT_CATALOG_IDS = 16
MAX_CONTRACT_SCALARS = 16
MIN_CONTRACT_SCALAR = -1_000_000_000
MAX_CONTRACT_SCALAR = 1_000_000_000

PROMPT_TEMPLATE = """You are Nemisis's adversarial test author.
Given a ticket and candidate diff, return behavioral claims and complete pytest files.
Only return the supplied JSON schema. Do not return commands, runner configuration,
environment variables, markdown, patches, or prose outside the schema.
Each generated path must be generated/test_*.py, language python, framework pytest.
Prefix every claim ID and test ID with nemotron., every test function with test_nemotron_,
and every file basename with test_nemotron_. These names are reserved for model evidence.
Use CHANGE_WITNESS for behavior that should fail by assertion on base and pass on candidate;
use INVARIANT for behavior that must pass on both. Link every claim and test by stable IDs.
"""
PROMPT_TEMPLATE_DIGEST = sha256_text(PROMPT_TEMPLATE)

CONTRACT_PROMPT_TEMPLATE = """You are Nemisis's retry-contract selector.
Use only the supplied audited catalog IDs and scalar bounds. Return only the supplied
JSON schema. Do not return code, commands, SQL, tests, predicates, schedules, patches,
environment variables, markdown, or prose. Every scalar key must be supplied by the
request and every scalar value must remain within its inclusive bounds.
"""
CONTRACT_PROMPT_TEMPLATE_DIGEST = sha256_text(CONTRACT_PROMPT_TEMPLATE)

_SAFE_PART = re.compile(r"^[A-Za-z0-9_.-]+$")
_TOKEN_FACTORY_HOST = re.compile(r"^api\.tokenfactory(?:\.[a-z0-9-]+)?\.nebius\.com$")
_STRUCTURED_FEATURES = frozenset({"json_schema", "structured_output", "structured_outputs"})
_ALLOWED_IMPORTS = frozenset({"inventory", "pytest"})
_DANGEROUS_NAMES = frozenset(
    {
        "__import__",
        "breakpoint",
        "compile",
        "eval",
        "exec",
        "exit",
        "getattr",
        "globals",
        "locals",
        "open",
        "quit",
        "setattr",
        "vars",
    }
)


class NemotronError(RuntimeError):
    """A safe, user-facing Token Factory failure."""


class MissingCredentialsError(NemotronError):
    """The required Token Factory credential is absent."""


class ModelUnavailableError(NemotronError):
    """The configured model is not currently usable."""


class NemotronAuthenticationError(NemotronError):
    """Token Factory rejected the configured credential."""


class NemotronRateLimitError(NemotronError):
    """Token Factory rejected the bounded call due to a rate limit."""


class NemotronTimeoutError(NemotronError):
    """Token Factory did not finish within the configured timeout."""


class NemotronResponseError(NemotronError):
    """Token Factory returned unusable or unsafe model output."""


class _ProposedTest(StrictModel):
    test_id: SafeId
    claim_id: SafeId
    path: str = Field(min_length=1, max_length=240)
    test_name: SafeId
    language: Literal["python"]
    framework: Literal["pytest"]
    content: str = Field(min_length=1, max_length=MAX_TEST_BYTES)
    expected_relation: ExpectedRelation


class _ModelPayload(StrictModel):
    claims: tuple[ClaimSpec, ...] = Field(min_length=1, max_length=16)
    generated_tests: tuple[_ProposedTest, ...] = Field(min_length=1, max_length=MAX_GENERATED_TESTS)


class _ContractScalar(StrictModel):
    name: SafeId
    value: int = Field(ge=MIN_CONTRACT_SCALAR, le=MAX_CONTRACT_SCALAR)


class _ContractPayload(StrictModel):
    catalog_ids: tuple[SafeId, ...] = Field(min_length=1, max_length=MAX_CONTRACT_CATALOG_IDS)
    scalars: tuple[_ContractScalar, ...] = Field(max_length=MAX_CONTRACT_SCALARS)


class NemotronGeneration(StrictModel):
    """Validated model proposals and their sanitized live-call receipt."""

    claims: tuple[ClaimSpec, ...]
    generated_tests: tuple[GeneratedTestSpec, ...]
    receipt: ModelCallReceipt


class NemotronContractGeneration(StrictModel):
    """Candidate-blind selection from trusted contracts and bounded scalar values."""

    catalog_ids: tuple[SafeId, ...]
    scalars: dict[str, int]
    receipt: ModelCallReceipt


class _ModelsResource(Protocol):
    def list(self, **kwargs: object) -> object: ...


class _CompletionsResource(Protocol):
    def create(self, **kwargs: object) -> object: ...


class _ChatResource(Protocol):
    completions: _CompletionsResource


class _Client(Protocol):
    models: _ModelsResource
    chat: _ChatResource


class NemotronClient:
    """Generate typed adversarial tests through one Token Factory model."""

    def __init__(
        self,
        *,
        client: _Client | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        model_id: str | None = None,
    ) -> None:
        self.base_url: str = base_url or os.getenv(BASE_URL_ENV) or DEFAULT_BASE_URL
        self.model_id: str = model_id or os.getenv(MODEL_ID_ENV) or DEFAULT_MODEL_ID
        _validate_base_url(self.base_url)
        self._truth_label = TruthLabel.MOCKED
        if client is None:
            credential = api_key or os.getenv(API_KEY_ENV)
            if not credential:
                raise MissingCredentialsError(f"{API_KEY_ENV} is required for live Nemotron calls")
            client = cast(
                _Client,
                OpenAI(
                    api_key=credential,
                    base_url=self.base_url,
                    timeout=TIMEOUT_SECONDS,
                    max_retries=MAX_RETRIES,
                ),
            )
            self._truth_label = TruthLabel.LIVE
        self._client = client

    def generate_contract(
        self,
        issue: str,
        base_material: str,
        catalog_ids: Sequence[str],
        bounds: Mapping[str, tuple[int, int]],
    ) -> NemotronContractGeneration:
        """Select only trusted catalog IDs and in-range values without candidate input."""
        trusted_ids, trusted_bounds = _validate_contract_input(
            issue, base_material, catalog_ids, bounds
        )
        self._validate_model()

        started_at = datetime.now(UTC)
        started = monotonic()
        prompt = json.dumps(
            {
                "base_material": base_material,
                "bounds": {
                    name: {"maximum": maximum, "minimum": minimum}
                    for name, (minimum, maximum) in trusted_bounds.items()
                },
                "catalog_ids": trusted_ids,
                "issue": issue,
            },
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        request: dict[str, object] = {
            "model": self.model_id,
            "messages": [
                {"role": "system", "content": CONTRACT_PROMPT_TEMPLATE},
                {"role": "user", "content": prompt},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "nemisis_retry_contract",
                    "strict": True,
                    "schema": _ContractPayload.model_json_schema(),
                },
            },
            "max_tokens": MAX_OUTPUT_TOKENS,
            "temperature": 0,
            "timeout": TIMEOUT_SECONDS,
        }
        input_digest = sha256_json(
            {
                "base_url": self.base_url,
                "max_retries": MAX_RETRIES,
                "request": request,
            }
        )
        try:
            completion = self._client.chat.completions.create(**request)
        except Exception as exc:
            raise _provider_error(exc, "contract generation") from exc

        raw = _completion_content(completion)
        encoded = _encode_bounded(raw, "model response", MAX_RESPONSE_BYTES)
        try:
            payload = _ContractPayload.model_validate_json(encoded)
        except (ValidationError, ValueError) as exc:
            raise NemotronResponseError("Nemotron contract failed the required schema") from exc
        selected_ids, scalars = _validate_contract_payload(payload, trusted_ids, trusted_bounds)
        receipt = ModelCallReceipt(
            truth_label=self._truth_label,
            timestamp=started_at,
            endpoint_region=_endpoint_region(self.base_url),
            model_id=self.model_id,
            input_digest=input_digest,
            prompt_template_digest=CONTRACT_PROMPT_TEMPLATE_DIGEST,
            latency_ms=max(0, round((monotonic() - started) * 1_000)),
            outcome="success",
            schema_valid=True,
            response_digest=sha256_bytes(encoded),
        )
        return NemotronContractGeneration(
            catalog_ids=selected_ids,
            scalars=scalars,
            receipt=receipt,
        )

    def generate(
        self,
        *,
        ticket: str,
        candidate_diff: str,
        max_generated_tests: int = MAX_GENERATED_TESTS,
    ) -> NemotronGeneration:
        """Return only schema-valid claims/tests and a sanitized receipt."""
        _validate_input(ticket, candidate_diff, max_generated_tests)
        self._validate_model()

        started_at = datetime.now(UTC)
        started = monotonic()
        prompt = (
            f"Maximum generated tests: {max_generated_tests}\n\n"
            f"TICKET\n{ticket}\n\nCANDIDATE DIFF\n{candidate_diff}"
        )
        request: dict[str, object] = {
            "model": self.model_id,
            "messages": [
                {"role": "system", "content": PROMPT_TEMPLATE},
                {"role": "user", "content": prompt},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "nemisis_claim_bundle",
                    "strict": True,
                    "schema": _ModelPayload.model_json_schema(),
                },
            },
            "max_tokens": MAX_OUTPUT_TOKENS,
            "temperature": 0,
            "timeout": TIMEOUT_SECONDS,
        }
        input_digest = sha256_json(
            {
                "base_url": self.base_url,
                "max_generated_tests": max_generated_tests,
                "max_retries": MAX_RETRIES,
                "request": request,
            }
        )
        try:
            completion = self._client.chat.completions.create(**request)
        except Exception as exc:
            raise _provider_error(exc, "generation") from exc

        raw = _completion_content(completion)
        encoded = _encode_bounded(raw, "model response", MAX_RESPONSE_BYTES)
        try:
            payload = _ModelPayload.model_validate_json(encoded)
        except (ValidationError, ValueError) as exc:
            raise NemotronResponseError("Nemotron response failed the required schema") from exc
        tests = _validate_payload(payload, max_generated_tests)
        response_digest = sha256_bytes(encoded)
        receipt = ModelCallReceipt(
            truth_label=self._truth_label,
            timestamp=started_at,
            endpoint_region=_endpoint_region(self.base_url),
            model_id=self.model_id,
            input_digest=input_digest,
            prompt_template_digest=PROMPT_TEMPLATE_DIGEST,
            latency_ms=max(0, round((monotonic() - started) * 1_000)),
            outcome="success",
            schema_valid=True,
            response_digest=response_digest,
        )
        return NemotronGeneration(
            claims=payload.claims,
            generated_tests=tests,
            receipt=receipt,
        )

    def _validate_model(self) -> None:
        try:
            response = self._client.models.list(
                extra_query={"verbose": True}, timeout=TIMEOUT_SECONDS
            )
        except Exception as exc:
            raise _provider_error(exc, "model capability check") from exc

        data = _field(response, "data")
        if not isinstance(data, Sequence) or isinstance(data, (str, bytes, bytearray)):
            raise ModelUnavailableError("Token Factory returned a malformed model catalog")
        selected = next(
            (item for item in data if _field(item, "id", required=False) == self.model_id),
            None,
        )
        if selected is None:
            raise ModelUnavailableError(
                f"configured model {self.model_id!r} is not in the live Token Factory catalog"
            )

        status = _field(selected, "status", required=False)
        if status is not None and status != "active":
            raise ModelUnavailableError(
                f"configured model {self.model_id!r} is not active (status={status!r})"
            )
        architecture = _field(selected, "architecture", required=False)
        modality = _field(architecture, "modality", required=False)
        if modality != "text->text":
            raise ModelUnavailableError(
                f"configured model {self.model_id!r} lacks text chat capability"
            )
        features = _field(selected, "supported_features", required=False)
        normalized = (
            {
                str(feature).strip().lower().replace("-", "_").replace(" ", "_")
                for feature in features
            }
            if isinstance(features, Sequence) and not isinstance(features, (str, bytes, bytearray))
            else set()
        )
        if not normalized.intersection(_STRUCTURED_FEATURES):
            raise ModelUnavailableError(
                f"configured model {self.model_id!r} lacks JSON-schema output capability"
            )


def _validate_contract_input(
    issue: str,
    base_material: str,
    catalog_ids: Sequence[str],
    bounds: Mapping[str, tuple[int, int]],
) -> tuple[tuple[str, ...], dict[str, tuple[int, int]]]:
    if not issue.strip():
        raise ValueError("issue must not be empty")
    if not base_material.strip():
        raise ValueError("base material must not be empty")
    _encode_bounded(issue, "issue", MAX_TICKET_BYTES)
    _encode_bounded(base_material, "base material", MAX_BASE_MATERIAL_BYTES)
    if (
        isinstance(catalog_ids, (str, bytes))
        or not 1 <= len(catalog_ids) <= MAX_CONTRACT_CATALOG_IDS
    ):
        raise ValueError(f"catalog_ids must contain 1 to {MAX_CONTRACT_CATALOG_IDS} IDs")
    if any(
        not isinstance(catalog_id, str)
        or len(catalog_id) > 120
        or not _SAFE_PART.fullmatch(catalog_id)
        for catalog_id in catalog_ids
    ):
        raise ValueError("catalog IDs must use trusted safe identifiers")
    trusted_ids = tuple(sorted(catalog_ids))
    if len(trusted_ids) != len(set(trusted_ids)):
        raise ValueError("catalog IDs must be unique")
    if not isinstance(bounds, Mapping) or len(bounds) > MAX_CONTRACT_SCALARS:
        raise ValueError(f"bounds must contain at most {MAX_CONTRACT_SCALARS} scalars")

    trusted_bounds: dict[str, tuple[int, int]] = {}
    for name, bound in sorted(bounds.items()):
        if not isinstance(name, str) or len(name) > 120 or not _SAFE_PART.fullmatch(name):
            raise ValueError("scalar names must use trusted safe identifiers")
        if (
            not isinstance(bound, tuple)
            or len(bound) != 2
            or any(not isinstance(value, int) or isinstance(value, bool) for value in bound)
        ):
            raise ValueError("each scalar bound must be an integer (minimum, maximum) tuple")
        minimum, maximum = bound
        if minimum < MIN_CONTRACT_SCALAR or maximum > MAX_CONTRACT_SCALAR or minimum > maximum:
            raise ValueError("scalar bounds are invalid or exceed the supported range")
        trusted_bounds[name] = (minimum, maximum)
    return trusted_ids, trusted_bounds


def _validate_contract_payload(
    payload: _ContractPayload,
    trusted_ids: tuple[str, ...],
    trusted_bounds: Mapping[str, tuple[int, int]],
) -> tuple[tuple[str, ...], dict[str, int]]:
    selected_ids = tuple(sorted(payload.catalog_ids))
    if len(selected_ids) != len(set(selected_ids)) or not set(selected_ids).issubset(trusted_ids):
        raise NemotronResponseError("Nemotron selected an unknown or duplicate catalog ID")
    scalars = {scalar.name: scalar.value for scalar in payload.scalars}
    if len(scalars) != len(payload.scalars):
        raise NemotronResponseError("Nemotron returned duplicate scalar keys")
    if scalars.keys() != trusted_bounds.keys():
        raise NemotronResponseError("Nemotron scalar keys do not exactly match supplied bounds")
    for name, value in scalars.items():
        minimum, maximum = trusted_bounds[name]
        if not minimum <= value <= maximum:
            raise NemotronResponseError(f"Nemotron scalar {name!r} is outside supplied bounds")
    return selected_ids, dict(sorted(scalars.items()))


def _validate_input(ticket: str, candidate_diff: str, max_generated_tests: int) -> None:
    if not ticket.strip():
        raise ValueError("ticket must not be empty")
    if not candidate_diff.strip():
        raise ValueError("candidate diff must not be empty")
    _encode_bounded(ticket, "ticket", MAX_TICKET_BYTES)
    _encode_bounded(candidate_diff, "candidate diff", MAX_DIFF_BYTES)
    if not 1 <= max_generated_tests <= MAX_GENERATED_TESTS:
        raise ValueError(f"max_generated_tests must be between 1 and {MAX_GENERATED_TESTS}")


def _validate_payload(
    payload: _ModelPayload, max_generated_tests: int
) -> tuple[GeneratedTestSpec, ...]:
    if len(payload.generated_tests) > max_generated_tests:
        returned = len(payload.generated_tests)
        raise NemotronResponseError(
            f"Nemotron returned {returned} tests; limit is {max_generated_tests}"
        )
    claim_by_id = {claim.claim_id: claim for claim in payload.claims}
    if len(claim_by_id) != len(payload.claims):
        raise NemotronResponseError("Nemotron returned duplicate claim IDs")
    if any(not claim_id.startswith("nemotron.") for claim_id in claim_by_id):
        raise NemotronResponseError("Nemotron claim IDs must use the reserved prefix")

    seen_test_ids: set[str] = set()
    seen_paths: set[str] = set()
    total_bytes = 0
    generated: list[GeneratedTestSpec] = []
    for proposed in payload.generated_tests:
        if proposed.test_id in seen_test_ids:
            raise NemotronResponseError("Nemotron returned duplicate test IDs")
        if proposed.path in seen_paths:
            raise NemotronResponseError("Nemotron returned duplicate generated paths")
        claim = claim_by_id.get(proposed.claim_id)
        if claim is None:
            raise NemotronResponseError(f"test {proposed.test_id!r} references an unknown claim")
        if proposed.test_id not in claim.linked_test_ids:
            raise NemotronResponseError(
                f"test {proposed.test_id!r} is not linked by claim {claim.claim_id!r}"
            )
        if proposed.expected_relation is not claim.expected_relation:
            raise NemotronResponseError(
                f"test {proposed.test_id!r} disagrees with its claim relation"
            )
        _validate_generated_path(proposed.path)
        if proposed.language != "python" or proposed.framework != "pytest":
            raise NemotronResponseError("generated tests must use Python and pytest")
        if (
            not proposed.test_id.startswith("nemotron.")
            or not proposed.test_name.startswith("test_nemotron_")
            or not PurePosixPath(proposed.path).name.startswith("test_nemotron_")
        ):
            raise NemotronResponseError("generated tests must use the reserved model prefix")
        content = _encode_bounded(proposed.content, "generated test", MAX_TEST_BYTES)
        if b"\x00" in content:
            raise NemotronResponseError("generated test content contains a NUL byte")
        _validate_python_test(proposed.content, proposed.test_name)
        total_bytes += len(content)
        if total_bytes > MAX_TOTAL_TEST_BYTES:
            raise NemotronResponseError(
                f"generated test content exceeds {MAX_TOTAL_TEST_BYTES} bytes"
            )
        generated.append(
            GeneratedTestSpec(
                test_id=proposed.test_id,
                claim_id=proposed.claim_id,
                path=proposed.path,
                test_name=proposed.test_name,
                language="python",
                framework="pytest",
                content=proposed.content,
                content_hash=sha256_bytes(content),
                expected_relation=proposed.expected_relation,
            )
        )
        seen_test_ids.add(proposed.test_id)
        seen_paths.add(proposed.path)

    linked = {test_id for claim in payload.claims for test_id in claim.linked_test_ids}
    if linked != seen_test_ids:
        raise NemotronResponseError("claim links do not exactly match generated test IDs")
    if set(claim_by_id) != {test.claim_id for test in generated}:
        raise NemotronResponseError("every claim must own at least one generated test")
    return tuple(generated)


def _validate_generated_path(raw: str) -> None:
    if "\\" in raw:
        raise NemotronResponseError("generated path must use POSIX separators")
    path = PurePosixPath(raw)
    if (
        raw != path.as_posix()
        or path.is_absolute()
        or len(path.parts) < 2
        or path.parts[0] != "generated"
        or any(part in {"", ".", ".."} or not _SAFE_PART.fullmatch(part) for part in path.parts)
        or path.suffix != ".py"
        or not path.name.startswith("test_")
    ):
        raise NemotronResponseError(
            "generated path must be a safe relative pytest file under generated/"
        )


def _validate_python_test(content: str, declared_name: str) -> None:
    try:
        tree = ast.parse(content)
    except SyntaxError as exc:
        raise NemotronResponseError("generated test is invalid Python") from exc

    tests = [
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith("test_")
    ]
    if tests != [declared_name]:
        raise NemotronResponseError("generated file must define exactly its declared test function")

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name not in _ALLOWED_IMPORTS:
                    raise NemotronResponseError(
                        f"generated test import is not allowed: {alias.name}"
                    )
                _validate_public_name(alias.asname)
        elif isinstance(node, ast.ImportFrom):
            if node.level or node.module not in _ALLOWED_IMPORTS:
                raise NemotronResponseError(
                    f"generated test import is not allowed: {node.module or '<relative>'}"
                )
            for alias in node.names:
                if alias.name == "*":
                    raise NemotronResponseError("generated wildcard imports are not allowed")
                _validate_public_name(alias.name)
                _validate_public_name(alias.asname)
        elif isinstance(node, ast.Name):
            if node.id in _DANGEROUS_NAMES:
                raise NemotronResponseError(f"generated test uses dangerous builtin: {node.id}")
            _validate_public_name(node.id)
        elif isinstance(node, ast.Attribute):
            _validate_public_name(node.attr)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            _validate_public_name(node.name)
        elif isinstance(node, ast.arg):
            _validate_public_name(node.arg)


def _validate_public_name(name: str | None) -> None:
    if name and name.startswith("_"):
        raise NemotronResponseError(f"generated test accesses private name: {name}")


def _completion_content(completion: object) -> str:
    choices = _field(completion, "choices", required=False)
    if not isinstance(choices, Sequence) or isinstance(choices, (str, bytes, bytearray)):
        raise NemotronResponseError("Nemotron response has no choices")
    if len(choices) != 1:
        raise NemotronResponseError("Nemotron response must contain exactly one choice")
    message = _field(choices[0], "message")
    refusal = _field(message, "refusal", required=False)
    if refusal:
        raise NemotronResponseError("Nemotron refused to generate verification tests")
    content = _field(message, "content", required=False)
    if not isinstance(content, str) or not content:
        raise NemotronResponseError("Nemotron response did not contain JSON content")
    return content


def _field(value: object, name: str, *, required: bool = True) -> object:
    result = value.get(name) if isinstance(value, Mapping) else getattr(value, name, None)
    if required and result is None:
        raise NemotronResponseError(f"provider response is missing {name!r}")
    return result


def _encode_bounded(value: str, label: str, maximum: int) -> bytes:
    try:
        encoded = value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise NemotronResponseError(f"{label} is not valid UTF-8") from exc
    if len(encoded) > maximum:
        raise NemotronResponseError(f"{label} exceeds {maximum} bytes")
    return encoded


def _provider_error(exc: Exception, operation: str) -> NemotronError:
    status = getattr(exc, "status_code", None)
    name = type(exc).__name__.lower()
    if status in {401, 403} or "authentication" in name or "permission" in name:
        return NemotronAuthenticationError(
            f"Token Factory authentication failed during {operation}"
        )
    if status == 429 or "ratelimit" in name or "rate_limit" in name:
        return NemotronRateLimitError(f"Token Factory rate limit reached during {operation}")
    if "timeout" in name:
        return NemotronTimeoutError(f"Token Factory timed out during {operation}")
    status_suffix = f" (HTTP {status})" if isinstance(status, int) else ""
    return NemotronError(f"Token Factory failed during {operation}{status_suffix}")


def _validate_base_url(value: str) -> None:
    parsed = urlparse(value)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or not _TOKEN_FACTORY_HOST.fullmatch(parsed.hostname)
        or parsed.port not in {None, 443}
        or parsed.username
        or parsed.password
        or parsed.path not in {"/v1", "/v1/"}
        or parsed.params
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("Token Factory base URL must be an official Nebius HTTPS /v1 endpoint")


def _endpoint_region(base_url: str) -> str:
    hostname = urlparse(base_url).hostname
    if not hostname:
        raise ValueError("Token Factory base URL has no hostname")
    if hostname == "api.tokenfactory.nebius.com":
        return "global"
    prefix = hostname.removeprefix("api.tokenfactory.").removesuffix(".nebius.com")
    return prefix if prefix != hostname else hostname
