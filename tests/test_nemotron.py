from __future__ import annotations

import json
from dataclasses import dataclass
from inspect import signature
from typing import cast

import pytest

import nemisis.nemotron as nemotron
from nemisis.hashing import sha256_json, sha256_text
from nemisis.models import TruthLabel
from nemisis.nemotron import (
    CONTRACT_PROMPT_TEMPLATE_DIGEST,
    DEFAULT_BASE_URL,
    DEFAULT_MODEL_ID,
    MAX_RETRIES,
    TIMEOUT_SECONDS,
    MissingCredentialsError,
    ModelUnavailableError,
    NemotronAuthenticationError,
    NemotronClient,
    NemotronRateLimitError,
    NemotronResponseError,
    NemotronTimeoutError,
    _Client,
)


def _payload(
    *,
    path: str = "generated/test_nemotron_retry.py",
    content: str = "def test_nemotron_retry():\n    assert True\n",
) -> dict[str, object]:
    return {
        "claims": [
            {
                "claim_id": "nemotron.retry-idempotency",
                "statement": "A crashed reservation retry does not decrement twice.",
                "rationale": "The marker may lag the inventory side effect.",
                "risk_category": "idempotency",
                "expected_relation": "CHANGE_WITNESS",
                "referenced_files": ["inventory.py"],
                "referenced_symbols": ["reserve_inventory"],
                "linked_test_ids": ["nemotron.crash-retry"],
            }
        ],
        "generated_tests": [
            {
                "test_id": "nemotron.crash-retry",
                "claim_id": "nemotron.retry-idempotency",
                "path": path,
                "test_name": "test_nemotron_retry",
                "language": "python",
                "framework": "pytest",
                "content": content,
                "expected_relation": "CHANGE_WITNESS",
            }
        ],
    }


def _contract_payload(
    *,
    catalog_ids: list[str] | None = None,
    scalars: dict[str, int] | None = None,
) -> dict[str, object]:
    return {
        "catalog_ids": catalog_ids or ["sqlite-credit-v1"],
        "scalars": [
            {"name": name, "value": value}
            for name, value in (scalars or {"amount_cents": 2_500, "replay_count": 1}).items()
        ],
    }


@dataclass
class _ErrorWithStatus(Exception):
    status_code: int


class _Models:
    def __init__(
        self, *, error: Exception | None = None, features: list[str] | None = None
    ) -> None:
        self.error = error
        self.features = features if features is not None else ["structured_outputs"]
        self.calls: list[dict[str, object]] = []

    def list(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return {
            "data": [
                {
                    "id": DEFAULT_MODEL_ID,
                    "status": "active",
                    "architecture": {"modality": "text->text"},
                    "supported_features": self.features,
                }
            ]
        }


class _Completions:
    def __init__(self, payload: object, *, error: Exception | None = None) -> None:
        self.payload = payload
        self.error = error
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        content = self.payload if isinstance(self.payload, str) else json.dumps(self.payload)
        return {"choices": [{"message": {"content": content, "refusal": None}}]}


class _Chat:
    def __init__(self, completions: _Completions) -> None:
        self.completions = completions


class _FakeClient:
    def __init__(
        self,
        payload: object,
        *,
        model_error: Exception | None = None,
        completion_error: Exception | None = None,
        features: list[str] | None = None,
    ) -> None:
        self.models = _Models(error=model_error, features=features)
        self.chat = _Chat(_Completions(payload, error=completion_error))


def _adapter(client: _FakeClient) -> NemotronClient:
    return NemotronClient(client=cast(_Client, client))


def test_generate_returns_validated_tests_and_sanitized_receipt() -> None:
    fake = _FakeClient(_payload())
    result = _adapter(fake).generate(
        ticket="Make retries safe", candidate_diff="diff --git a/x b/x"
    )

    assert result.generated_tests[0].content_hash == sha256_text(
        "def test_nemotron_retry():\n    assert True\n"
    )
    assert result.claims[0].linked_test_ids == ("nemotron.crash-retry",)
    assert result.receipt.truth_label is TruthLabel.MOCKED
    assert result.receipt.model_id == DEFAULT_MODEL_ID
    assert result.receipt.endpoint_region == "global"
    assert fake.models.calls == [{"extra_query": {"verbose": True}, "timeout": TIMEOUT_SECONDS}]
    call = fake.chat.completions.calls[0]
    assert call["temperature"] == 0
    response_format = cast(dict[str, object], call["response_format"])
    assert response_format["type"] == "json_schema"
    json_schema = cast(dict[str, object], response_format["json_schema"])
    assert json_schema["name"] == "nemisis_claim_bundle"
    assert json_schema["strict"] is True
    assert isinstance(json_schema["schema"], dict)
    assert result.receipt.input_digest == sha256_json(
        {
            "base_url": DEFAULT_BASE_URL,
            "max_generated_tests": 8,
            "max_retries": MAX_RETRIES,
            "request": call,
        }
    )
    serialized = result.model_dump_json()
    assert "Make retries safe" not in serialized
    assert "diff --git" not in serialized


def test_generate_contract_is_candidate_blind_and_returns_only_trusted_values() -> None:
    fake = _FakeClient(_contract_payload())
    result = _adapter(fake).generate_contract(
        "Credit retries must be atomic",
        "app.credits.apply_credit uses CreditStore",
        ("sqlite-credit-v1", "sqlite-credit-refinement-v1"),
        {"amount_cents": (1, 10_000), "replay_count": (1, 2)},
    )

    assert "candidate" not in signature(NemotronClient.generate_contract).parameters
    assert result.catalog_ids == ("sqlite-credit-v1",)
    assert result.scalars == {"amount_cents": 2_500, "replay_count": 1}
    assert result.receipt.truth_label is TruthLabel.MOCKED
    assert result.receipt.prompt_template_digest == CONTRACT_PROMPT_TEMPLATE_DIGEST
    call = fake.chat.completions.calls[0]
    messages = cast(list[dict[str, str]], call["messages"])
    assert "candidate" not in "\n".join(message["content"] for message in messages).lower()
    response_format = cast(dict[str, object], call["response_format"])
    json_schema = cast(dict[str, object], response_format["json_schema"])
    assert json_schema["name"] == "nemisis_retry_contract"
    schema = cast(dict[str, object], json_schema["schema"])
    assert set(cast(dict[str, object], schema["properties"])) == {"catalog_ids", "scalars"}
    serialized = result.model_dump_json()
    assert "Credit retries" not in serialized
    assert "CreditStore" not in serialized


def test_contract_input_digest_is_stable_across_mapping_and_catalog_order() -> None:
    first = _adapter(_FakeClient(_contract_payload())).generate_contract(
        "issue",
        "base",
        ("sqlite-credit-v2", "sqlite-credit-v1"),
        {"replay_count": (1, 2), "amount_cents": (1, 10_000)},
    )
    second = _adapter(_FakeClient(_contract_payload())).generate_contract(
        "issue",
        "base",
        ("sqlite-credit-v1", "sqlite-credit-v2"),
        {"amount_cents": (1, 10_000), "replay_count": (1, 2)},
    )

    assert first.receipt.input_digest == second.receipt.input_digest


@pytest.mark.parametrize(
    "payload,error",
    [
        (_contract_payload(catalog_ids=["unknown"]), "unknown"),
        (_contract_payload(scalars={"amount_cents": 20_000, "replay_count": 1}), "outside"),
        (_contract_payload(scalars={"amount_cents": 2_500}), "exactly"),
        ({**_contract_payload(), "python": "assert True"}, "schema"),
    ],
)
def test_generate_contract_rejects_untrusted_or_unbounded_output(
    payload: dict[str, object], error: str
) -> None:
    with pytest.raises(NemotronResponseError, match=error):
        _adapter(_FakeClient(payload)).generate_contract(
            "issue",
            "base",
            ("sqlite-credit-v1",),
            {"amount_cents": (1, 10_000), "replay_count": (1, 2)},
        )


def test_generate_contract_rejects_invalid_bounds_before_provider_calls() -> None:
    fake = _FakeClient(_contract_payload())
    with pytest.raises(ValueError, match="bound"):
        _adapter(fake).generate_contract(
            "issue", "base", ("sqlite-credit-v1",), {"amount_cents": (10, 1)}
        )
    assert fake.models.calls == []
    assert fake.chat.completions.calls == []


def test_only_an_internally_constructed_authenticated_client_emits_live(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _FakeClient(_payload())

    def openai_client(**kwargs: object) -> object:
        assert kwargs["api_key"] == "secret"
        return fake

    monkeypatch.setattr(nemotron, "OpenAI", openai_client)
    result = NemotronClient(api_key="secret").generate(ticket="ticket", candidate_diff="diff")
    assert result.receipt.truth_label is TruthLabel.LIVE
    assert "secret" not in result.model_dump_json()


def test_requires_credentials_without_an_injected_client(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NEBIUS_API_KEY", raising=False)
    with pytest.raises(MissingCredentialsError, match="NEBIUS_API_KEY"):
        NemotronClient()
    assert DEFAULT_BASE_URL == "https://api.tokenfactory.nebius.com/v1/"


@pytest.mark.parametrize(
    "base_url",
    [
        "https://example.com/v1/",
        "https://api.tokenfactory.nebius.com.evil.invalid/v1/",
        "https://api.tokenfactory.nebius.com:8443/v1/",
        "https://api.tokenfactory.nebius.com/v1/?redirect=evil",
    ],
)
def test_rejects_non_nebius_or_ambiguous_credential_destinations(base_url: str) -> None:
    with pytest.raises(ValueError, match="official Nebius"):
        NemotronClient(client=cast(_Client, _FakeClient(_payload())), base_url=base_url)


def test_accepts_the_documented_regional_token_factory_endpoint() -> None:
    client = NemotronClient(
        client=cast(_Client, _FakeClient(_payload())),
        base_url="https://api.tokenfactory.us-central1.nebius.com/v1/",
    )
    assert client.base_url == "https://api.tokenfactory.us-central1.nebius.com/v1/"


@pytest.mark.parametrize(
    "path",
    [
        "/generated/test_escape.py",
        "generated/../test_escape.py",
        "generated\\test_escape.py",
        "elsewhere/test_escape.py",
        "generated/conftest.py",
    ],
)
def test_rejects_unsafe_generated_paths(path: str) -> None:
    with pytest.raises(NemotronResponseError, match="generated path"):
        _adapter(_FakeClient(_payload(path=path))).generate(ticket="ticket", candidate_diff="diff")


def test_rejects_extra_command_field_and_malformed_json() -> None:
    payload = _payload()
    payload["command"] = "pytest generated"
    with pytest.raises(NemotronResponseError, match="schema"):
        _adapter(_FakeClient(payload)).generate(ticket="ticket", candidate_diff="diff")
    with pytest.raises(NemotronResponseError, match="schema"):
        _adapter(_FakeClient("not json")).generate(ticket="ticket", candidate_diff="diff")


def test_rejects_model_output_without_reserved_names() -> None:
    payload = _payload()
    claim = cast(dict[str, object], cast(list[object], payload["claims"])[0])
    test = cast(dict[str, object], cast(list[object], payload["generated_tests"])[0])
    claim["claim_id"] = "unreserved"
    test["claim_id"] = "unreserved"

    with pytest.raises(NemotronResponseError, match="reserved prefix"):
        _adapter(_FakeClient(payload)).generate(ticket="ticket", candidate_diff="diff")


@pytest.mark.parametrize(
    "content,error",
    [
        ("def test_nemotron_retry(:\n    pass\n", "invalid Python"),
        (
            "def test_nemotron_retry():\n    assert True\n\ndef test_extra():\n    assert True\n",
            "exactly its declared test",
        ),
        (
            "import atexit\n\ndef test_nemotron_retry():\n    assert True\n",
            "import is not allowed",
        ),
        (
            "def test_nemotron_retry():\n"
            "    open('__nemisis_results__/junit.xml', 'w').write('<testsuite/>')\n",
            "dangerous builtin",
        ),
        (
            "from inventory import _private_state\n\ndef test_nemotron_retry():\n"
            "    assert _private_state\n",
            "private name",
        ),
    ],
)
def test_rejects_malformed_or_unsafe_generated_python(content: str, error: str) -> None:
    with pytest.raises(NemotronResponseError, match=error):
        _adapter(_FakeClient(_payload(content=content))).generate(
            ticket="ticket", candidate_diff="diff"
        )


def test_rejects_requested_count_and_oversized_content() -> None:
    with pytest.raises(NemotronResponseError, match="limit is 1"):
        payload = _payload()
        first = cast(dict[str, object], cast(list[object], payload["generated_tests"])[0])
        second = first.copy()
        second["test_id"] = "another-test"
        second["path"] = "generated/test_another.py"
        payload["generated_tests"] = [first, second]
        claims = cast(list[object], payload["claims"])
        claim = cast(dict[str, object], claims[0])
        cast(list[str], claim["linked_test_ids"]).append("another-test")
        _adapter(_FakeClient(payload)).generate(
            ticket="ticket", candidate_diff="diff", max_generated_tests=1
        )

    with pytest.raises(NemotronResponseError, match="schema"):
        _adapter(_FakeClient(_payload(content="x" * 30_001))).generate(
            ticket="ticket", candidate_diff="diff"
        )


def test_model_catalog_must_list_structured_text_model() -> None:
    with pytest.raises(ModelUnavailableError, match="JSON-schema"):
        _adapter(_FakeClient(_payload(), features=[])).generate(
            ticket="ticket", candidate_diff="diff"
        )


@pytest.mark.parametrize(
    "error,expected",
    [
        (_ErrorWithStatus(401), NemotronAuthenticationError),
        (_ErrorWithStatus(429), NemotronRateLimitError),
        (TimeoutError(), NemotronTimeoutError),
    ],
)
def test_provider_failures_are_clear_and_sanitized(
    error: Exception, expected: type[Exception]
) -> None:
    with pytest.raises(expected, match="Token Factory") as caught:
        _adapter(_FakeClient(_payload(), completion_error=error)).generate(
            ticket="ticket", candidate_diff="diff"
        )
    if str(error):
        assert str(error) not in str(caught.value)


def test_truncated_completion_is_reported_as_truncation_not_schema_failure() -> None:
    class _Truncated(_Completions):
        def create(self, **kwargs: object) -> object:
            self.calls.append(kwargs)
            return {
                "choices": [
                    {
                        "message": {
                            "content": '{"catalog_ids":["sqlite-credit-v1"',
                            "refusal": None,
                        },
                        "finish_reason": "length",
                    }
                ]
            }

    fake = _FakeClient(_contract_payload())
    fake.chat = _Chat(_Truncated(_contract_payload()))

    with pytest.raises(NemotronResponseError, match="truncated at max_tokens"):
        _adapter(fake).generate_contract(
            "issue", "base", ("sqlite-credit-v1",), {"amount_cents": (1, 10_000)}
        )
