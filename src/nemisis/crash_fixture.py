"""Audited, package-relative SQLite credit hero fixture."""

from __future__ import annotations

import json
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Literal, TypedDict, cast

from nemisis.hashing import canonical_json, sha256_bytes, sha256_json, sha256_tree
from nemisis.safety import safe_destination, safe_relative_path

SCENARIO_ID = "sqlite-credit-v1"
BUGGY_REF = f"fixture:{SCENARIO_ID}/buggy"
MISLEADING_GREEN_REF = f"fixture:{SCENARIO_ID}/misleading-green"
ATOMIC_REF = f"fixture:{SCENARIO_ID}/atomic"
FIXTURE_REFS = (BUGGY_REF, MISLEADING_GREEN_REF, ATOMIC_REF)

ISSUE_DIGEST = "dca9933dc39177cd391972f8ec6945b01a27d3559990566788cabb12c51c0f77"
EVENT_DIGEST = "4ad9ce16a3a060a5dbde7dffafdd7fd2f047e612c4e34c6ca30635355778b293"
EVENT_RESOURCE_DIGEST = "95db3d29c50d2c2bbb0058e4e82d8705c77e51a98e25887defc8366e96bd0e33"
AUDITED_CONTRACT_DIGEST = "3b121eed2abbb011d5e769600690c5502bca561233007b0df5787cd49fb67e10"
CONTRACT_RESOURCE_DIGEST = "e364533418ea5060fb6abb17b0aa84ab633315d51b7f02646acb7a0dc5fa7249"

FixtureVariant = Literal["buggy", "misleading-green", "atomic"]

_RESOURCE_ROOT = ("fixtures", "sqlite_credit_v1")
_REF_TO_VARIANT: dict[str, FixtureVariant] = {
    BUGGY_REF: "buggy",
    MISLEADING_GREEN_REF: "misleading-green",
    ATOMIC_REF: "atomic",
}
_TREE_DIGESTS: dict[FixtureVariant, str] = {
    "buggy": "e0e3df5d3bdd0659fd4fcd7719c9047186eb2099dbab2bbb8092c1903a97c0b2",
    "misleading-green": ("3d79be420d3a92ee84ac66c15576d1fbfdb7ec3dba4f34dd9e6bfeb8489bf69f"),
    "atomic": "ccdce21b146ff0146fd93f3aa86f3d047f937153215cae4e2ab80c92d93954de",
}
_COMMON_FILES = (
    ("common/app/__init__.py", "app/__init__.py"),
    ("common/tests/test_credits.py", "tests/test_credits.py"),
)


class FixtureEvent(TypedDict):
    account_id: str
    amount_cents: int
    event_id: str


class AuditedContract(TypedDict):
    adapter_id: str
    event_digest: str
    event_fixture_id: str
    fault_intent_id: str
    issue_digest: str
    originating_base_ref: str
    originating_base_tree_digest: str
    predicate_ids: list[str]
    probe_id: str
    scenario_id: str
    schema_version: str
    target: str


@dataclass(frozen=True)
class MaterializedFixture:
    ref: str
    variant: FixtureVariant
    path: Path
    tree_digest: str


def load_issue() -> str:
    raw = _resource_bytes("issue.md")
    if sha256_bytes(raw) != ISSUE_DIGEST:
        raise ValueError("audited fixture issue digest mismatch")
    return raw.decode("utf-8")


def load_event() -> FixtureEvent:
    raw = _resource_bytes("event.json")
    if sha256_bytes(raw) != EVENT_RESOURCE_DIGEST:
        raise ValueError("audited fixture event bytes changed")
    value = _json_object(raw, "event")
    account_id = value.get("account_id")
    amount_cents = value.get("amount_cents")
    event_id = value.get("event_id")
    if (
        set(value) != {"account_id", "amount_cents", "event_id"}
        or not isinstance(account_id, str)
        or type(amount_cents) is not int
        or not isinstance(event_id, str)
    ):
        raise ValueError("audited fixture event has an invalid shape")
    event = FixtureEvent(
        account_id=account_id,
        amount_cents=amount_cents,
        event_id=event_id,
    )
    if sha256_json(event) != EVENT_DIGEST:
        raise ValueError("audited fixture event digest mismatch")
    return event


def load_event_bytes() -> bytes:
    """Return the canonical bytes replayed identically by every worker."""
    return canonical_json(load_event())


def load_contract() -> AuditedContract:
    raw = _resource_bytes("contract.json")
    if sha256_bytes(raw) != CONTRACT_RESOURCE_DIGEST:
        raise ValueError("audited fixture contract bytes changed")
    value = _json_object(raw, "contract")
    if sha256_json(value) != AUDITED_CONTRACT_DIGEST:
        raise ValueError("audited fixture contract digest mismatch")
    contract = cast(AuditedContract, value)
    if (
        contract["scenario_id"] != SCENARIO_ID
        or contract["originating_base_ref"] != BUGGY_REF
        or contract["originating_base_tree_digest"] != _TREE_DIGESTS["buggy"]
        or contract["issue_digest"] != ISSUE_DIGEST
        or contract["event_digest"] != EVENT_DIGEST
    ):
        raise ValueError("audited fixture contract bindings changed")
    load_issue()
    load_event()
    return contract


def materialize_fixture(ref: str, destination: Path) -> MaterializedFixture:
    """Materialize one exact packaged source tree into a new directory."""
    try:
        variant = _REF_TO_VARIANT[ref]
    except KeyError:
        raise ValueError(f"unknown fixture ref: {ref}") from None
    load_contract()
    destination.mkdir(parents=True, exist_ok=False)
    files = (*_COMMON_FILES, (f"trees/{variant}/app/credits.py", "app/credits.py"))
    for source, relative in files:
        output = safe_destination(destination, safe_relative_path(relative))
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(_resource_bytes(source))
    tree_digest = sha256_tree(destination)
    if tree_digest != _TREE_DIGESTS[variant]:
        raise ValueError(f"audited fixture {variant} tree digest mismatch")
    return MaterializedFixture(
        ref=ref,
        variant=variant,
        path=destination.resolve(),
        tree_digest=tree_digest,
    )


def _resource_bytes(relative: str) -> bytes:
    path = safe_relative_path(relative)
    resource = resources.files("nemisis")
    for part in (*_RESOURCE_ROOT, *path.parts):
        resource = resource.joinpath(part)
    if not resource.is_file():
        raise ValueError(f"missing audited fixture resource: {relative}")
    return resource.read_bytes()


def _json_object(raw: bytes, label: str) -> dict[str, object]:
    try:
        value = cast(object, json.loads(raw))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"audited fixture {label} is not valid JSON") from error
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ValueError(f"audited fixture {label} must be a JSON object")
    return cast(dict[str, object], value)
