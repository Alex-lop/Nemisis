"""Audited, package-relative fixture trees for every registered scenario."""

from __future__ import annotations

import json
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Literal, TypedDict, cast

from nemisis.hashing import canonical_json, sha256_bytes, sha256_json, sha256_tree
from nemisis.safety import safe_destination, safe_relative_path
from nemisis.scenario import Event, Scenario
from nemisis.scenarios import SCENARIOS
from nemisis.scenarios.sqlite_credit_v1 import (
    AUDITED_CONTRACT_DIGEST,
    CONTRACT_RESOURCE_DIGEST,
    EVENT_DIGEST,
    EVENT_RESOURCE_DIGEST,
    ISSUE_DIGEST,
)
from nemisis.scenarios.sqlite_credit_v1 import SCENARIO as CREDIT

# The hero scenario's refs, by name, for the code and tests that tell its story.
SCENARIO_ID = CREDIT.scenario_id
BUGGY_REF = CREDIT.ref("buggy")
MISLEADING_GREEN_REF = CREDIT.ref("misleading-green")
ATOMIC_REF = CREDIT.ref("atomic")
MARK_FIRST_REF = CREDIT.ref("mark-first")
LEFTOVER_CREDIT_REF = CREDIT.ref("leftover-credit")
NEVER_MARKS_REF = CREDIT.ref("never-marks")
RAW_SQL_REF = CREDIT.ref("raw-sql")
# The three-tree hero the benchmark measures, in canonical order.
HERO_REFS = tuple(CREDIT.ref(variant) for variant in CREDIT.hero_variants)
# Every packaged tree of every registered scenario; each is one flag away for anyone to rerun.
FIXTURE_REFS = tuple(
    scenario.ref(variant) for scenario in SCENARIOS.values() for variant in scenario.variants
)

HeroVariant = Literal["buggy", "misleading-green", "atomic"]


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
    variant: str
    path: Path
    tree_digest: str


def parse_ref(ref: str) -> tuple[Scenario, str]:
    """``fixture:<scenario id>/<variant>`` -> the registered scenario and one of its variants."""
    scenario_id, _, variant = ref.removeprefix("fixture:").partition("/")
    scenario = SCENARIOS.get(scenario_id) if ref.startswith("fixture:") else None
    if scenario is None or variant not in scenario.variants:
        raise ValueError(f"unknown fixture ref: {ref}")
    return scenario, variant


def load_issue(scenario: Scenario = CREDIT) -> str:
    raw = _resource_bytes(scenario, "issue.md")
    if sha256_bytes(raw) != scenario.issue_digest:
        raise ValueError("audited fixture issue digest mismatch")
    return raw.decode("utf-8")


def load_event(scenario: Scenario = CREDIT) -> Event:
    raw = _resource_bytes(scenario, "event.json")
    if sha256_bytes(raw) != scenario.event_resource_digest:
        raise ValueError("audited fixture event bytes changed")
    try:
        event = scenario.normalize_event(_json_object(raw, "event"))
    except ValueError as error:
        raise ValueError("audited fixture event has an invalid shape") from error
    if sha256_json(event) != scenario.event_digest:
        raise ValueError("audited fixture event digest mismatch")
    return event


def load_event_bytes(scenario: Scenario = CREDIT) -> bytes:
    """Return the canonical bytes replayed identically by every worker."""
    return canonical_json(load_event(scenario))


def load_contract(scenario: Scenario = CREDIT) -> AuditedContract:
    raw = _resource_bytes(scenario, "contract.json")
    if sha256_bytes(raw) != scenario.contract_resource_digest:
        raise ValueError("audited fixture contract bytes changed")
    value = _json_object(raw, "contract")
    if sha256_json(value) != scenario.audited_contract_digest:
        raise ValueError("audited fixture contract digest mismatch")
    contract = cast(AuditedContract, value)
    if (
        contract["scenario_id"] != scenario.scenario_id
        or contract["originating_base_ref"] != scenario.buggy_ref
        or contract["originating_base_tree_digest"]
        != scenario.tree_digests[scenario.hero_variants[0]]
        or contract["issue_digest"] != scenario.issue_digest
        or contract["event_digest"] != scenario.event_digest
    ):
        raise ValueError("audited fixture contract bindings changed")
    load_issue(scenario)
    load_event(scenario)
    return contract


def materialize_fixture(ref: str, destination: Path) -> MaterializedFixture:
    """Materialize one exact packaged source tree into a new directory."""
    scenario, variant = parse_ref(ref)
    load_contract(scenario)
    destination.mkdir(parents=True, exist_ok=False)
    files = (
        *scenario.common_files,
        (f"trees/{variant}/{scenario.handler_relative}", scenario.handler_relative),
    )
    for source, relative in files:
        output = safe_destination(destination, safe_relative_path(relative))
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(_resource_bytes(scenario, source))
    tree_digest = sha256_tree(destination)
    if tree_digest != scenario.tree_digests[variant]:
        raise ValueError(f"audited fixture {variant} tree digest mismatch")
    return MaterializedFixture(
        ref=ref,
        variant=variant,
        path=destination.resolve(),
        tree_digest=tree_digest,
    )


def _resource_bytes(scenario: Scenario, relative: str) -> bytes:
    path = safe_relative_path(relative)
    resource = resources.files("nemisis")
    for part in ("fixtures", scenario.fixture_package, *path.parts):
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


__all__ = [
    "ATOMIC_REF",
    "AUDITED_CONTRACT_DIGEST",
    "BUGGY_REF",
    "CONTRACT_RESOURCE_DIGEST",
    "EVENT_DIGEST",
    "EVENT_RESOURCE_DIGEST",
    "FIXTURE_REFS",
    "HERO_REFS",
    "ISSUE_DIGEST",
    "LEFTOVER_CREDIT_REF",
    "MARK_FIRST_REF",
    "MISLEADING_GREEN_REF",
    "NEVER_MARKS_REF",
    "RAW_SQL_REF",
    "SCENARIO_ID",
    "AuditedContract",
    "FixtureEvent",
    "HeroVariant",
    "MaterializedFixture",
    "load_contract",
    "load_event",
    "load_event_bytes",
    "load_issue",
    "materialize_fixture",
    "parse_ref",
]
