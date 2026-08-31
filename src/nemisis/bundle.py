"""Build and materialize the immutable trusted verification bundle."""

from __future__ import annotations

import ast
from collections.abc import Sequence
from pathlib import Path

from nemisis.hashing import sha256_json, sha256_text
from nemisis.models import BundleFile, ClaimSpec, GeneratedTestSpec, VerificationBundle
from nemisis.safety import safe_destination, safe_relative_path

MAX_TOTAL_TEST_BYTES = 60_000
RUNNER_ARGV = (
    "python",
    "-m",
    "pytest",
    "-q",
    "-p",
    "no:cacheprovider",
    "-p",
    "nemisis_pytest_plugin",
    "-c",
    "__nemisis_bundle__/harness/pytest.ini",
    "--junitxml=__nemisis_results__/junit.xml",
    "__nemisis_bundle__/baseline",
    "__nemisis_bundle__/generated",
)
RUNNER_ID = "pytest-fixed-v1"
PARSER_VERSION = "nemisis-junit-v1"


def _validate_test(test: GeneratedTestSpec, *, root: str) -> None:
    safe_relative_path(test.path, required_root=root)
    if test.content_hash != sha256_text(test.content):
        raise ValueError(f"content hash mismatch: {test.test_id}")
    try:
        tree = ast.parse(test.content)
    except SyntaxError as error:
        raise ValueError(f"invalid Python test: {test.test_id}") from error
    test_names = {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith("test_")
    }
    if test_names != {test.test_name}:
        raise ValueError(f"test file must define exactly its declared test: {test.test_id}")


def _payload(bundle: VerificationBundle) -> dict[str, object]:
    return bundle.model_dump(mode="json", exclude={"digest"})


def build_bundle(
    *,
    claims: Sequence[ClaimSpec],
    baseline_tests: Sequence[GeneratedTestSpec],
    generated_tests: Sequence[GeneratedTestSpec],
    harness_files: Sequence[BundleFile],
    runner_version: str,
    parser_digest: str,
    dependency_lock_digest: str,
    model_id: str,
    prompt_template_digest: str,
    model_input_digest: str | None = None,
    model_response_digest: str | None = None,
) -> VerificationBundle:
    if not claims or not baseline_tests or not generated_tests or not harness_files:
        raise ValueError("claims, baseline, generated tests, and harness are required")
    all_tests = (*baseline_tests, *generated_tests)
    total_bytes = sum(len(test.content.encode()) for test in all_tests)
    if len(generated_tests) > 8 or total_bytes > MAX_TOTAL_TEST_BYTES:
        raise ValueError("generated test count or total test bytes exceeds the limit")
    ids = [test.test_id for test in all_tests]
    paths = [test.path for test in all_tests]
    names = [test.test_name for test in all_tests]
    if len(ids) != len(set(ids)) or len(paths) != len(set(paths)) or len(names) != len(set(names)):
        raise ValueError("test IDs, paths, and function names must be unique")
    claim_map = {claim.claim_id: claim for claim in claims}
    if len(claim_map) != len(claims):
        raise ValueError("claim IDs must be unique")
    if any(len(claim.linked_test_ids) != len(set(claim.linked_test_ids)) for claim in claims):
        raise ValueError("claim test links must be unique")
    for test in baseline_tests:
        _validate_test(test, root="baseline")
    for test in generated_tests:
        _validate_test(test, root="generated")
    for test in all_tests:
        claim = claim_map.get(test.claim_id)
        if claim is None or test.test_id not in claim.linked_test_ids:
            raise ValueError(f"test is not linked to its claim: {test.test_id}")
        if test.expected_relation is not claim.expected_relation:
            raise ValueError(f"test relation differs from claim: {test.test_id}")
    for claim in claims:
        linked = {test.test_id for test in all_tests if test.claim_id == claim.claim_id}
        if linked != set(claim.linked_test_ids):
            raise ValueError(f"claim links do not match bundle tests: {claim.claim_id}")
    harness_paths = [file.path for file in harness_files]
    if len(harness_paths) != len(set(harness_paths)):
        raise ValueError("harness paths must be unique")
    for file in harness_files:
        safe_relative_path(file.path, required_root="harness")
        if file.content_hash != sha256_text(file.content):
            raise ValueError(f"harness content hash mismatch: {file.path}")
    draft = VerificationBundle(
        claims=tuple(claims),
        baseline_tests=tuple(baseline_tests),
        generated_tests=tuple(generated_tests),
        harness_files=tuple(harness_files),
        runner_id=RUNNER_ID,
        runner_argv=RUNNER_ARGV,
        runner_version=runner_version,
        result_format="junit-xml",
        parser_version=PARSER_VERSION,
        parser_digest=parser_digest,
        dependency_lock_digest=dependency_lock_digest,
        model_id=model_id,
        prompt_template_digest=prompt_template_digest,
        model_input_digest=model_input_digest,
        model_response_digest=model_response_digest,
        digest="0" * 64,
    )
    return draft.model_copy(update={"digest": sha256_json(_payload(draft))})


def verify_bundle_digest(bundle: VerificationBundle) -> None:
    if bundle.digest != sha256_json(_payload(bundle)):
        raise ValueError("verification bundle digest mismatch")


def materialize_bundle(bundle: VerificationBundle, destination: Path) -> None:
    verify_bundle_digest(bundle)
    destination.mkdir(parents=True, exist_ok=False)
    for test in (*bundle.baseline_tests, *bundle.generated_tests):
        path = safe_destination(destination, safe_relative_path(test.path))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(test.content)
    for file in bundle.harness_files:
        relative = safe_relative_path(file.path, required_root="harness")
        path = safe_destination(destination, relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(file.content)
