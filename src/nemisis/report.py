"""Judge-readable, static evidence report."""

from __future__ import annotations

from html import escape
from pathlib import Path

from nemisis.models import ArtifactStatus, RunManifest


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
