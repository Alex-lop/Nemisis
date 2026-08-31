"""Judge-readable, static evidence report."""

from __future__ import annotations

import json
from html import escape
from pathlib import Path

from nemisis.crash_models import CrashCheckResult, CreditSnapshot, ReproCapsule
from nemisis.models import ArtifactStatus, RunManifest


def write_crash_report(result: CrashCheckResult, capsule: ReproCapsule, path: Path) -> None:
    """Render verdict-first static CrashCheck evidence with no executable controls."""
    rows = "".join(
        "<tr>"
        f'<th scope="row"><code>{escape(attempt.receipt_id)}</code><br>'
        f"{escape(attempt.role.value)}</th>"
        f"<td>{escape(attempt.execution_status.value)}</td>"
        f"<td>{escape(attempt.observation.value)}</td>"
        f"<td>{escape(_snapshot_text(attempt.checkpoint_snapshot))}</td>"
        f"<td>{escape(_snapshot_text(attempt.final_snapshot))}</td>"
        "</tr>"
        for attempt in result.attempts
    )
    binding_rows = "".join(
        "<tr>"
        f'<th scope="row"><code>{escape(binding.source_ref)}</code></th>'
        f"<td><code>{escape(binding.resolved_source_identity)}</code></td>"
        f"<td><code>{escape(binding.tree_digest)}</code></td>"
        "</tr>"
        for binding in result.bindings
    )
    hypothesis_rows = "".join(
        "<tr>"
        f'<th scope="row">{receipt.canonical_rank}</th>'
        f"<td><code>{escape(receipt.hypothesis_id)}</code></td>"
        f"<td><code>{escape(receipt.fault_boundary.value)}</code></td>"
        f"<td>{receipt.trusted_operation_count}</td>"
        f"<td>{'REPRODUCED' if receipt.reproduced else 'NOT REPRODUCED'}</td>"
        f"<td>{'SELECTED' if receipt.selected else 'NOT SELECTED'}</td>"
        "</tr>"
        for receipt in result.hypothesis_receipts
    )
    selected_hypothesis = next(
        (receipt for receipt in result.hypothesis_receipts if receipt.selected), None
    )
    if selected_hypothesis is not None:
        selection_summary = (
            f"<strong>Selected outcome: "
            f"{'REPRODUCED' if selected_hypothesis.reproduced else 'NOT REPRODUCED'} · "
            f"1 of {len(result.hypothesis_receipts)} selected</strong> — "
            f"<code>{escape(selected_hypothesis.hypothesis_id)}</code> at "
            f"<code>{escape(selected_hypothesis.fault_boundary.value)}</code> with "
            f"{selected_hypothesis.trusted_operation_count} trusted operation(s)."
        )
    else:
        selection_summary = (
            f"<strong>Selected outcome: none · 0 of "
            f"{len(result.hypothesis_receipts)} selected</strong>."
        )
    hunt_section = (
        f"""<section class="card" aria-labelledby="hypothesis-hunt">
<h2 id="hypothesis-hunt">{len(result.hypothesis_receipts)}-hypothesis candidate-blind hunt</h2>
<p>{selection_summary}</p>
<div class="table-wrap" role="region" aria-label="Hypothesis hunt receipts" tabindex="0"><table>
<caption>Stored candidate-blind hunt receipts; no hypotheses are reconstructed by this \
report.</caption>
<thead><tr><th scope="col">Rank</th><th scope="col">Hypothesis</th>
<th scope="col">Fault boundary</th><th scope="col">Trusted operations</th>
<th scope="col">Outcome</th><th scope="col">Selection</th></tr></thead>
<tbody>{hypothesis_rows}</tbody></table></div></section>"""
        if result.hypothesis_receipts
        else ""
    )
    minimization_receipts = getattr(result, "minimization_receipts", ())
    if minimization_receipts:
        minimization = minimization_receipts[0]
        observations = ", ".join(
            attempt.observation.value for attempt in minimization.confirmations
        )
        reduction_outcome = (
            "deletion rejected; the sole fault action is necessary for this fixture witness"
            if minimization.irreducible
            else "empty-schedule evidence incomplete; no minimization claim"
        )
        minimization_section = f"""<section class="card" aria-labelledby="minimization">
<h2 id="minimization">Single-action deletion / necessity check</h2>
<p>Tried deleting the capsule's sole <code>{escape(minimization.removed_fault.value)}</code>
fault action in {len(minimization.confirmations)} fresh base worlds. The empty schedule observed
<code>{escape(observations)}</code>; {escape(reduction_outcome)}.</p>
<p>No general minimizer claim. Stable deletion trace
<code>{escape(minimization.trace_digest)}</code></p></section>"""
    else:
        minimization_section = ""
    representative = next(
        (attempt for attempt in result.attempts if attempt.execution_status.value != "COMPLETED"),
        next(
            (
                attempt
                for attempt in result.attempts
                if attempt.role.value in {"candidate", "corrected"}
            ),
            result.attempts[0],
        ),
    )
    checkpoint = representative.checkpoint_snapshot
    final = representative.final_snapshot
    first_spawn = next((spawn for spawn in representative.spawns if spawn.phase == "first"), None)
    replay_spawn = next((spawn for spawn in representative.spawns if spawn.phase == "replay"), None)
    checkpoint_story = (
        f"<strong>Checkpoint reached.</strong> {escape(_snapshot_text(checkpoint))}"
        if representative.checkpoint_reached and checkpoint is not None
        else "<strong>Checkpoint not recorded.</strong>"
    )
    if representative.kill_signal is not None and first_spawn is not None:
        kill_story = (
            f"<strong>Kill recorded.</strong> Signal {representative.kill_signal}; first worker "
            f"PID {first_spawn.pid}, process group {first_spawn.process_group_id}, "
            f"exit {first_spawn.exit_code}."
        )
    elif representative.kill_signal is not None:
        kill_story = (
            f"<strong>Kill recorded.</strong> Signal {representative.kill_signal}; "
            "no first-worker spawn receipt."
        )
    else:
        kill_story = "<strong>No kill signal recorded.</strong>"
    fresh_worker_story = (
        f"<strong>Fresh replay worker.</strong> Spawn {replay_spawn.spawn_index}; "
        f"PID {replay_spawn.pid}, process group {replay_spawn.process_group_id}; "
        f"worker nonce <code>{escape(replay_spawn.worker_nonce)}</code>; "
        f"IPC session <code>{escape(replay_spawn.ipc_session_id)}</code>."
        if replay_spawn is not None
        else "<strong>No replay-worker spawn receipt recorded.</strong>"
    )
    replay_story = (
        f"<strong>Replay acknowledged.</strong> Event <code>{escape(capsule.event_id)}</code>; "
        f"receipt event digest <code>{escape(representative.event_digest)}</code>."
        if representative.replay_acknowledged
        else "<strong>Replay not acknowledged.</strong>"
    )
    final_story = (
        f"<strong>Final state observed.</strong> {escape(_snapshot_text(final))}"
        if final is not None
        else "<strong>Final state not recorded.</strong>"
    )
    failure = (
        f"<p><strong>Failure detail:</strong> {escape(representative.failure_detail)}</p>"
        if representative.failure_detail
        else ""
    )
    evidence = escape(
        json.dumps(
            {
                "capsule": capsule.model_dump(mode="json"),
                "result": result.model_dump(mode="json"),
            },
            indent=2,
            sort_keys=True,
        )
    )
    tone = _verdict_tone(result.verdict.value)
    observed = _money(final.account_balance_cents) if final is not None else "Not recorded"
    document = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Nemisis CrashCheck — {escape(result.verdict.value)}</title>
<style>
:root {{ color-scheme: dark; font-family: ui-sans-serif, system-ui, sans-serif; line-height: 1.5; }}
* {{ box-sizing: border-box; }}
body {{ margin: 0 auto; max-width: 1100px; padding: 1.5rem; background: #090d12; color: #edf2f7; }}
.verdict-pass {{ --accent: #70e5ad; --tint: #10241d; }}
.verdict-fail {{ --accent: #ff8a96; --tint: #2a1318; }}
.verdict-warn {{ --accent: #ffd166; --tint: #2a2211; }}
.skip-link {{ position: absolute; left: -9999px; }} .skip-link:focus {{ left: 1rem; top: 1rem; }}
.hero {{ padding: clamp(1.2rem,4vw,2.5rem); background: var(--tint);
border: 2px solid var(--accent); }}
.label,.verdict-code {{ color: var(--accent); letter-spacing: .1em; text-transform: uppercase; }}
h1 {{ margin: .25rem 0; font-size: clamp(2rem,6vw,4rem); line-height: 1.05; }}
.summary {{ max-width: 70ch; font-size: 1.1rem; }}
.comparison {{ display: grid; grid-template-columns: minmax(0,1fr) auto minmax(0,1fr);
gap: 1rem; align-items: center; margin: 1.5rem 0; }}
.measure {{ padding: 1rem; background: #090d12; border: 1px solid #465364; }}
.measure span,.measure small {{ display: block; color: #b7c3d1; }}
.measure strong {{ display: block; color: var(--accent); font-size: clamp(2rem,6vw,3.5rem); }}
.versus {{ color: #b7c3d1; font-weight: 700; }}
.identity,.axes {{ display: grid; gap: .75rem;
grid-template-columns: repeat(auto-fit,minmax(200px,1fr)); }}
.identity {{ margin: 0; }} .identity div {{ min-width: 0; }}
.identity dt,.axes dt {{ color: #b7c3d1; }}
.identity dd {{ margin: .25rem 0 0; }}
.card {{ margin: 1rem 0; padding: 1rem; background: #121923; border: 1px solid #2a3747; }}
.axes {{ margin: 1rem 0; }} .axes dd {{ margin: .35rem 0 0; font-size: 1.3rem; }}
.timeline {{ display: grid; gap: .75rem; padding-left: 1.8rem; }}
.timeline li {{ padding: .8rem; border-left: 3px solid var(--accent); }}
.table-wrap {{ overflow-x: auto; }}
table {{ border-collapse: collapse; width: 100%; }} th,td {{ padding: .65rem; text-align: left;
border-bottom: 1px solid #2a3747; }} code,pre {{ overflow-wrap: anywhere; white-space: pre-wrap; }}
caption {{ padding: 0 0 .75rem; text-align: left; color: #a8b6c7; }}
@media (max-width: 640px) {{
body {{ padding: .75rem; }} .comparison {{ grid-template-columns: 1fr; }}
.versus {{ display: none; }}
}}
</style>
</head>
<body>
<a class="skip-link" href="#main">Skip to evidence</a>
<main id="main" class="verdict-{tone}">
<header class="hero">
<p class="label">{escape(_transport_label(result.transport.value))} · \
{escape(_capsule_label(capsule.truth_label.value))}</p>
<p class="verdict-code">CrashCheck verdict · <code>{escape(result.verdict.value)}</code></p>
<h1>{escape(_verdict_title(result.verdict.value))}</h1>
<p class="summary">{escape(result.summary)}</p>
<div class="comparison" aria-label="Expected and observed effects">
<div class="measure"><span>Expected single effect</span>
<strong>{_money(capsule.amount_cents)}</strong>
<small>event <code>{escape(capsule.event_id)}</code></small></div>
<span class="versus" aria-hidden="true">vs</span>
<div class="measure"><span>Observed final balance</span><strong>{observed}</strong>
<small>{escape(representative.observation.value)}</small></div>
</div>
<dl class="identity" aria-label="Evidence identity">
<div><dt>Capsule digest</dt><dd><code>{escape(capsule.digest)}</code></dd></div>
<div><dt>Engine code digest</dt><dd><code>{escape(result.engine_code_digest)}</code></dd></div>
<div><dt>Engine source commit</dt><dd><code>\
{escape(result.engine_source_commit or "not recorded")}</code></dd></div>
</dl>
</header>
<dl class="axes" aria-label="Independent result axes">
<div class="card"><dt>Transport</dt><dd>{escape(result.transport.value)}</dd></div>
<div class="card"><dt>Execution</dt><dd>{escape(result.execution_status.value)}</dd></div>
<div class="card"><dt>Provenance</dt><dd>{escape(result.integrity_status.value)}</dd></div>
<div class="card"><dt>CrashCheck verdict</dt><dd>{escape(result.verdict.value)}</dd></div>
</dl>
<section class="card" aria-labelledby="attempt-story"><h2 id="attempt-story">Representative \
{escape(representative.role.value)} attempt</h2>
<p>Receipt <code>{escape(representative.receipt_id)}</code></p>
<ol class="timeline">
<li>{checkpoint_story}</li>
<li>{kill_story}</li>
<li>{fresh_worker_story}</li>
<li>{replay_story}</li>
<li>{final_story}</li>
</ol>{failure}</section>
{hunt_section}
{minimization_section}
<section class="card" aria-labelledby="source-bindings">
<h2 id="source-bindings">Source bindings</h2>
<div class="table-wrap" role="region" aria-label="Source bindings" tabindex="0"><table>
<caption>Exact source identities and trees evaluated by this result.</caption>
<thead><tr><th scope="col">Source reference</th><th scope="col">Resolved identity</th>
<th scope="col">Tree digest</th></tr></thead>
<tbody>{binding_rows}</tbody></table></div></section>
<section class="card" aria-labelledby="attempt-receipts">
<h2 id="attempt-receipts">Attempt receipts \
({len(result.attempts)})</h2>
<div class="table-wrap" role="region" aria-label="Attempt receipts" tabindex="0"><table>
<caption>{len(result.attempts)} receipt(s) across {len(result.bindings)} \
source-tree binding(s).</caption>
<thead><tr><th scope="col">Attempt / role</th><th scope="col">Execution</th>
<th scope="col">Observation</th><th scope="col">Checkpoint</th>
<th scope="col">Final</th></tr></thead>
<tbody>{rows}</tbody></table></div></section>
<details class="card"><summary>Full evidence</summary>
<pre>{evidence}</pre></details>
</main>
</body>
</html>"""
    path.write_text(document, encoding="utf-8")


def _snapshot_text(snapshot: CreditSnapshot | None) -> str:
    if snapshot is None:
        return "not recorded"
    return (
        f"{snapshot.account_balance_cents}¢ / ledger {snapshot.event_ledger_count} / "
        f"marker {snapshot.event_marker_count}"
    )


def _money(cents: int) -> str:
    sign = "-" if cents < 0 else ""
    absolute = abs(cents)
    return f"{sign}${absolute // 100:,}.{absolute % 100:02d}"


def _transport_label(label: str) -> str:
    return {"LOCAL": "LOCAL EXECUTION", "LIVE": "LIVE MODE REQUESTED"}.get(
        label, label.replace("_", " ")
    )


def _capsule_label(label: str) -> str:
    return {"FIXTURE": "AUDITED FIXTURE CAPSULE", "LOCAL": "ACCEPTED LOCAL CAPSULE"}.get(
        label, f"{label.replace('_', ' ')} CAPSULE"
    )


def _verdict_tone(verdict: str) -> str:
    if verdict == "FIX_PROVEN_FOR_THIS_CAPSULE":
        return "pass"
    if verdict in {"EVIDENCE_INCOMPLETE", "UNSUPPORTED_TARGET"}:
        return "warn"
    return "fail"


def _verdict_title(verdict: str) -> str:
    return {
        "BUG_REPRODUCED": "Crash/retry bug reproduced",
        "PATCH_FAILED_STILL_REPRODUCES": "Patch still duplicates the effect",
        "FIX_PROVEN_FOR_THIS_CAPSULE": "Fix proven for this capsule only",
        "EVIDENCE_INCOMPLETE": "Evidence incomplete",
        "UNSUPPORTED_TARGET": "Target unsupported",
    }.get(verdict, verdict.replace("_", " ").title())


def write_html_report(manifest: RunManifest, path: Path) -> None:
    claims = {claim.claim_id: claim.statement for claim in manifest.bundle.claims}
    rows = "".join(
        "<tr>"
        f"<td>{escape(claims[cell.claim_id])}<br><code>{escape(cell.test_id)}</code></td>"
        f"<td>{escape(cell.expected_relation.value)}</td>"
        f"<td>{escape(cell.base_outcome.value)}</td>"
        f"<td>{escape(cell.candidate_outcome.value)}</td>"
        f"<td class='{cell.classification.value.lower()}'>{escape(cell.classification.value)}</td>"
        "</tr>"
        for cell in manifest.matrix
    )
    worlds = "".join(
        f"<li><code>{escape(world.kind.value)}</code> {escape(world.world_id)} — "
        f"tree <code>{world.resulting_tree_digest}</code>"
        f"{f' — image {escape(world.image_uuid)}' if world.image_uuid else ''}</li>"
        for world in manifest.worlds
    )
    executions = "".join(
        "<tr>"
        f"<td><code>{escape(receipt.world_id)}</code></td>"
        f"<td><code>{escape(receipt.test_id)}</code></td>"
        f"<td>{escape(receipt.operation_id or '—')}</td>"
        f"<td>{receipt.exit_code if receipt.exit_code is not None else '—'}</td>"
        f"<td>{escape(receipt.outcome.value)}</td>"
        f"<td>{receipt.duration_ms} ms</td>"
        f"<td><code>{receipt.result_report_hash}</code></td>"
        "</tr>"
        for receipt in manifest.executions
    )
    accepted = manifest.artifact.status is ArtifactStatus.ACCEPTED
    html = f"""<!doctype html>
<html lang="en">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Nemisis evidence — {escape(manifest.request.run_id)}</title>
<style>
:root {{ color-scheme: dark; font-family: ui-sans-serif, system-ui, sans-serif; }}
body {{ margin: 0 auto; max-width: 1100px; padding: 2rem; background: #0a0d12; color: #e8edf3; }}
.badge {{ display: inline-block; padding: .35rem .65rem; border: 1px solid #57d6a0;
color: #57d6a0; }}
.card {{ margin: 1.4rem 0; padding: 1.2rem; overflow-x: auto; background: #121821;
border: 1px solid #293343; }}
table {{ border-collapse: collapse; width: 100%; }} th, td {{ padding: .75rem; text-align: left;
border-bottom: 1px solid #293343; }} th {{ color: #9eacbc; }} code {{ overflow-wrap: anywhere; }}
caption {{ color: #9eacbc; padding: .5rem; text-align: left; }}
.supported {{ color: #57d6a0; }} .unresolved,.regression,.incomplete {{ color: #ff7272; }}
.non_discriminating {{ color: #f2c66d; }}
</style>
<body>
<p class="badge">{escape(_truth_badge(manifest))}</p>
<h1>Nemisis claim matrix</h1>
<p>Don't ask whether the coding agent says it is done. Make the exact patch prove each claim.</p>
<div class="card"><table><caption>Observed claim-by-world results</caption>
<thead><tr><th>Claim / test</th><th>Expected</th><th>Base</th>
<th>Candidate</th><th>Verdict</th></tr></thead><tbody>{rows}</tbody></table></div>
<div class="card"><h2>{"ACCEPTED" if accepted else "REJECTED"}</h2>
<p>{escape(manifest.artifact.reason)}</p>
<p>Patch <code>{manifest.artifact.final_patch_digest}</code></p>
<p>Bundle <code>{manifest.bundle.digest}</code></p></div>
<div class="card"><h2>Exact worlds</h2><ul>{worlds}</ul></div>
<div class="card"><h2>Execution receipts</h2><table>
<caption>Provider identifiers are shown only when returned by the active runtime.</caption>
<thead><tr><th>World</th><th>Test</th><th>Operation</th><th>Exit</th><th>Outcome</th>
<th>Duration</th><th>JUnit hash</th></tr></thead><tbody>{executions}</tbody></table></div>
<div class="card"><h2>Run binding</h2>
<p>Model <code>{escape(manifest.model_id or "not used — local fixture")}</code></p>
<p>Prompt <code>{manifest.prompt_template_digest}</code></p>
<p>Source commit <code>{escape(manifest.source_commit or "unavailable")}</code></p></div>
</body></html>"""
    path.write_text(html)


def _truth_badge(manifest: RunManifest) -> str:
    if manifest.truth_label.value == "FIXTURE":
        return "LOCAL FIXTURE"
    if manifest.truth_label.value == "LIVE":
        return "LIVE TOKEN FACTORY"
    return manifest.truth_label.value.replace("_", " ")
