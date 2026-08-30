"""The single trusted fixture used by the first vertical slice."""

from __future__ import annotations

from dataclasses import dataclass
from importlib import resources

from nemisis.hashing import sha256_bytes, sha256_json, sha256_text
from nemisis.models import BundleFile, ClaimSpec, ExpectedRelation, GeneratedTestSpec

FIXTURE_ID = "idempotency-retry"


@dataclass(frozen=True)
class Fixture:
    ticket: str
    candidate_patch: bytes
    repository_files: tuple[tuple[str, bytes], ...]
    claims: tuple[ClaimSpec, ...]
    baseline_tests: tuple[GeneratedTestSpec, ...]
    generated_tests: tuple[GeneratedTestSpec, ...]
    harness_files: tuple[BundleFile, ...]

    @property
    def base_digest(self) -> str:
        entries = [
            {"path": path, "sha256": sha256_bytes(content)}
            for path, content in sorted(self.repository_files)
        ]
        return sha256_json(entries)


def _read(relative: str) -> bytes:
    return resources.files("nemisis").joinpath("fixtures/idempotency_retry", relative).read_bytes()


def _test(
    *,
    test_id: str,
    claim_id: str,
    path: str,
    test_name: str,
    source: str,
    relation: ExpectedRelation,
) -> GeneratedTestSpec:
    content = _read(source).decode()
    return GeneratedTestSpec(
        test_id=test_id,
        claim_id=claim_id,
        path=path,
        test_name=test_name,
        language="python",
        framework="pytest",
        content=content,
        content_hash=sha256_text(content),
        expected_relation=relation,
    )


def load_fixture(fixture_id: str = FIXTURE_ID) -> Fixture:
    if fixture_id != FIXTURE_ID:
        raise ValueError(f"unknown fixture: {fixture_id}")
    baseline_ids = ("baseline.reserve", "baseline.out-of-stock")
    claims = (
        ClaimSpec(
            claim_id="regression-suite",
            statement="Existing inventory behavior remains intact.",
            rationale="The patch must preserve successful reservations and out-of-stock safety.",
            risk_category="regression",
            expected_relation=ExpectedRelation.INVARIANT,
            referenced_files=("inventory.py",),
            referenced_symbols=("reserve_inventory",),
            linked_test_ids=baseline_ids,
        ),
        ClaimSpec(
            claim_id="duplicate-retry",
            statement="Retrying a completed order does not decrement stock twice.",
            rationale="Ordinary duplicate delivery is the visible idempotency promise.",
            risk_category="idempotency",
            expected_relation=ExpectedRelation.CHANGE_WITNESS,
            referenced_files=("inventory.py",),
            referenced_symbols=("reserve_inventory",),
            linked_test_ids=("adversarial.duplicate",),
        ),
        ClaimSpec(
            claim_id="crash-retry",
            statement="A retry after a crash following the side effect does not decrement twice.",
            rationale="The ticket explicitly covers the side-effect-to-marker failure window.",
            risk_category="crash-consistency",
            expected_relation=ExpectedRelation.CHANGE_WITNESS,
            referenced_files=("inventory.py",),
            referenced_symbols=("reserve_inventory",),
            linked_test_ids=("adversarial.crash-retry",),
        ),
    )
    invariant = ExpectedRelation.INVARIANT
    witness = ExpectedRelation.CHANGE_WITNESS
    baseline_tests = (
        _test(
            test_id=baseline_ids[0],
            claim_id="regression-suite",
            path="baseline/test_reservation.py",
            test_name="test_reserves_available_inventory",
            source="repository/tests/test_reservation.py",
            relation=invariant,
        ),
        _test(
            test_id=baseline_ids[1],
            claim_id="regression-suite",
            path="baseline/test_out_of_stock.py",
            test_name="test_rejects_insufficient_inventory_without_decrementing",
            source="repository/tests/test_out_of_stock.py",
            relation=invariant,
        ),
    )
    generated_tests = (
        _test(
            test_id="adversarial.duplicate",
            claim_id="duplicate-retry",
            path="generated/test_duplicate.py",
            test_name="test_ordinary_duplicate_retry_does_not_decrement_twice",
            source="adversarial_tests/test_duplicate.py",
            relation=witness,
        ),
        _test(
            test_id="adversarial.crash-retry",
            claim_id="crash-retry",
            path="generated/test_crash_retry.py",
            test_name="test_crash_then_retry_does_not_decrement_twice",
            source="adversarial_tests/test_crash_retry.py",
            relation=witness,
        ),
    )
    harness_files = tuple(
        BundleFile(path=f"harness/{name}", content=content, content_hash=sha256_text(content))
        for name in ("nemisis_pytest_plugin.py", "pytest.ini")
        if (content := _read(f"adversarial_tests/{name}").decode())
    )
    repository_files = tuple(
        (path, _read(f"repository/{path}"))
        for path in ("inventory.py", "tests/test_reservation.py", "tests/test_out_of_stock.py")
    )
    return Fixture(
        ticket=_read("ticket.md").decode(),
        candidate_patch=_read("candidate.patch"),
        repository_files=repository_files,
        claims=claims,
        baseline_tests=baseline_tests,
        generated_tests=generated_tests,
        harness_files=harness_files,
    )
