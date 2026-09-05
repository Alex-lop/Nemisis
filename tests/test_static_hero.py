import json
import re
from pathlib import Path

from nemisis.benchmark import BenchmarkResult
from nemisis.crash_models import CrashCheckResult, ReproCapsule
from nemisis.crashcheck import engine_code_digest

ROOT = Path(__file__).parents[1]
HERO = ROOT / "docs/assets/crashcheck-hero/index.html"


def test_static_hero_surface_is_verdict_first_and_accessible() -> None:
    page = HERO.read_text(encoding="utf-8")
    beats = [
        "Event delivered",
        "Durable checkpoint",
        "Worker killed",
        "Fresh worker replay",
        "Verdict",
    ]

    assert ">Replay fixture evidence</button>" in page
    assert "<title>Nemisis CrashCheck — loading bound fixture evidence</title>" in page
    assert 'id="skip-link" href="#evidence-status"' in page
    assert '<div id="bound-evidence" hidden>' in page
    assert 'id="evidence-status" aria-live="polite"' in page
    assert "No behavioral claim is shown until" in page
    assert '<h1 id="verdict-heading" data-field="candidate-verdict">' in page
    assert '<span class="badge local">LOCAL</span>' in page
    assert '<span class="badge fixture">FIXTURE</span>' in page
    assert "The browser does not run code or contact Token Factory." in page
    assert "Existing pytest suite" in page
    assert "Ordinary sequential duplicate" in page
    assert all(f"<h2>{beat}</h2>" in page for beat in beats)
    assert [page.index(f"<h2>{beat}</h2>") for beat in beats] == sorted(
        page.index(f"<h2>{beat}</h2>") for beat in beats
    )
    assert page.index("CrashCheck verdict") < page.index("Five-beat evidence story")
    assert '<dl class="axes" aria-label="Independent evidence axes">' in page
    assert all(
        axis in page for axis in ("Transport", "Execution", "Provenance", "Integrity", "Verdict")
    )
    assert "Single-action deletion / necessity check:" in page
    assert "no general minimizer claim" in page
    assert "minimization ratio" not in page
    assert 'field("provenance", capsule.truth_label)' in page
    assert 'field("integrity", result.integrity_status)' in page
    assert 'result.verdict === "PATCH_FAILED_STILL_REPRODUCES"' in page
    assert 'completeCase(candidate, "DUPLICATE_EFFECT")' in page
    assert 'completeCase(corrected, "EXACTLY_ONCE")' in page
    assert 'field("corrected-verdict", correctedVerdict)' in page
    assert 'field("corrected-verdict", "FIX_PROVEN_FOR_THIS_CAPSULE")' not in page
    assert "boundEvidence.hidden = true" in page
    assert 'evidenceStatusTitle.textContent = "Evidence unavailable"' in page
    assert 'document.title = "Nemisis CrashCheck — evidence unavailable"' in page
    assert 'skipLink.href = "#story"' in page
    assert all(
        field in page
        for field in (
            'data-field="source-commit"',
            'data-field="candidate-tree"',
            'data-field="capsule-digest"',
            'data-field="event-digest"',
        )
    )
    assert "@media (max-width: 760px)" in page
    assert "@media (prefers-reduced-motion: reduce)" in page
    assert 'aria-controls="receipt"' in page
    assert 'aria-live="polite"' in page
    assert "FIX_PROVEN_FOR_THIS_CAPSULE" in page
    assert "LIVE TOKEN FACTORY" not in page
    assert "RECORDED_LIVE" not in page


def test_static_hero_receipt_is_exactly_bound() -> None:
    page = HERO.read_text(encoding="utf-8")
    benchmark_bytes = (ROOT / "benchmarks/results/crashcheck-v1.json").read_bytes()
    benchmark = json.loads(benchmark_bytes)
    config_match = re.search(
        r'<script id="receipt-config" type="application/json">\s*(.*?)\s*</script>',
        page,
        re.DOTALL,
    )
    assert config_match is not None
    config = json.loads(config_match.group(1))
    manifest = json.loads(
        (
            ROOT / "docs/assets/crashcheck-hero/runs" / config["run_id"] / "manifest.json"
        ).read_bytes()
    )
    hero_engine = manifest["result"]["engine_code_digest"]
    if hero_engine == engine_code_digest():
        # Same engine build: the committed evidence must satisfy the live strict models.
        BenchmarkResult.model_validate_json(benchmark_bytes)
        CrashCheckResult.model_validate_json(json.dumps(manifest["result"]))
        ReproCapsule.model_validate_json(json.dumps(manifest["capsule"]))
    else:
        # Evidence recorded by an earlier engine build stays bound to that build: the docs must
        # name it, and the receipts below are checked structurally rather than re-validated by a
        # schema they were never produced under. Regenerating the hero re-enables the strict path.
        assert hero_engine in (ROOT / "docs/STATUS.md").read_text(encoding="utf-8")
        assert manifest["result"]["engine_source_commit"] in (ROOT / "docs/STATUS.md").read_text(
            encoding="utf-8"
        )

    assert ">Replay fixture evidence</button>" in page
    assert "<title>Nemisis CrashCheck — loading bound fixture evidence</title>" in page
    assert 'id="skip-link" href="#evidence-status"' in page
    assert '<div id="bound-evidence" hidden>' in page
    assert 'id="evidence-status" aria-live="polite"' in page
    assert "No behavioral claim is shown until" in page
    assert '<h1 id="verdict-heading" data-field="candidate-verdict">' in page
    assert '<span class="badge local">LOCAL</span>' in page
    assert '<span class="badge fixture">FIXTURE</span>' in page
    assert "The browser does not run code or contact Token Factory." in page
    assert "Existing pytest suite" in page
    assert "Ordinary sequential duplicate" in page
    beats = [
        "Event delivered",
        "Durable checkpoint",
        "Worker killed",
        "Fresh worker replay",
        "Verdict",
    ]
    assert all(f"<h2>{beat}</h2>" in page for beat in beats)
    assert [page.index(f"<h2>{beat}</h2>") for beat in beats] == sorted(
        page.index(f"<h2>{beat}</h2>") for beat in beats
    )
    assert page.index("CrashCheck verdict") < page.index("Five-beat evidence story")
    assert '<dl class="axes" aria-label="Independent evidence axes">' in page
    assert all(
        axis in page for axis in ("Transport", "Execution", "Provenance", "Integrity", "Verdict")
    )
    assert "Single-action deletion / necessity check:" in page
    assert "no general minimizer claim" in page
    assert "minimization ratio" not in page
    assert 'field("provenance", capsule.truth_label)' in page
    assert 'field("integrity", result.integrity_status)' in page
    assert 'result.verdict === "PATCH_FAILED_STILL_REPRODUCES"' in page
    assert 'completeCase(candidate, "DUPLICATE_EFFECT")' in page
    assert 'completeCase(corrected, "EXACTLY_ONCE")' in page
    assert 'field("corrected-verdict", correctedVerdict)' in page
    assert 'field("corrected-verdict", "FIX_PROVEN_FOR_THIS_CAPSULE")' not in page
    assert "boundEvidence.hidden = true" in page
    assert 'evidenceStatusTitle.textContent = "Evidence unavailable"' in page
    assert 'document.title = "Nemisis CrashCheck — evidence unavailable"' in page
    assert 'skipLink.href = "#story"' in page
    assert all(
        field in page
        for field in (
            'data-field="source-commit"',
            'data-field="candidate-tree"',
            'data-field="capsule-digest"',
            'data-field="event-digest"',
        )
    )
    assert "@media (max-width: 760px)" in page
    assert "@media (prefers-reduced-motion: reduce)" in page
    assert 'aria-controls="receipt"' in page
    assert 'aria-live="polite"' in page
    assert "FIX_PROVEN_FOR_THIS_CAPSULE" in page
    assert "LIVE TOKEN FACTORY" not in page
    assert "RECORDED_LIVE" not in page
    assert benchmark["source_commit"] == manifest["result"]["engine_source_commit"]
    assert manifest["result"]["verdict"] == "PATCH_FAILED_STILL_REPRODUCES"
    assert manifest["result"]["transport"] == "LOCAL"
    assert manifest["capsule"]["truth_label"] == "FIXTURE"
    assert benchmark["capsule_digest"] == manifest["capsule"]["digest"]
    assert benchmark["engine_code_digest"] == manifest["result"]["engine_code_digest"]
    assert benchmark["hunt"]["fault_action_deletion_trial_count"] == 1
    assert benchmark["hunt"]["deletion_confirmation_world_count"] == 2
    assert benchmark["hunt"]["initial_fault_action_count"] == 1
    assert benchmark["hunt"]["final_fault_action_count"] == 1
    assert benchmark["hunt"]["fault_action_retention_ratio"] == 1.0
    assert "minimization_ratio" not in benchmark["hunt"]
    assert {case["tree_digest"] for case in benchmark["cases"]} == {
        binding["tree_digest"] for binding in manifest["result"]["bindings"]
    }
    candidate = next(case for case in benchmark["cases"] if case["variant"] == "misleading-green")
    corrected = next(case for case in benchmark["cases"] if case["variant"] == "atomic")
    assert candidate["pytest"]["outcome"] == "PASS"
    assert candidate["sequential"]["outcome"] == "PASS"
    assert candidate["crashcheck"]["observation"] == "DUPLICATE_EFFECT"
    assert corrected["crashcheck"]["observation"] == "EXACTLY_ONCE"
    candidate_attempt = next(
        attempt for attempt in manifest["result"]["attempts"] if attempt["role"] == "candidate"
    )
    assert candidate_attempt["kill_signal"] == 9
    assert candidate_attempt["spawns"][0]["exit_code"] == -9
    assert (
        candidate_attempt["spawns"][0]["worker_nonce"]
        != candidate_attempt["spawns"][1]["worker_nonce"]
    )
    assert manifest["capsule"]["event_digest"] == candidate_attempt["event_digest"]
    artifacts = manifest["result"]["artifacts"]
    for artifact in ("report", "capsule", "regression_test"):
        assert (ROOT / "docs/assets/crashcheck-hero" / artifacts[artifact]).is_file()
