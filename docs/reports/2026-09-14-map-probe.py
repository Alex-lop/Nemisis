"""Probe: does the commit sweep run with no base, no hunt, no capsule-from-a-bug, no verdict?"""
import sys, tempfile, os
from pathlib import Path

from nemisis import crashcheck as cc
from nemisis.crash_models import WorldRole
from nemisis.scenarios import scenario_for

def crash_map(tree: Path, scenario_id: str = "sqlite-credit-v1"):
    scenario = scenario_for(scenario_id)
    contract = cc._audited_contract(scenario)
    capsule = cc._seal_capsule(contract)            # built from the contract alone
    with tempfile.TemporaryDirectory(prefix="probe-map-") as tmp:
        root = Path(tmp)
        scratch = cc._Scratch(root)
        source = scratch.source(tree, "source-candidate")
        binding = cc._bind_anchor(
            contract, source, WorldRole.CANDIDATE, cc.TruthLabel.LOCAL, capsule.digest
        )
        if not isinstance(binding, cc.AnchorBinding):
            return ("ANCHOR_FAILED", cc._anchor_failure_summary(binding), [])
        sweep = cc._execute_sweep(
            capsule, binding, source.path, scratch.phase(), WorldRole.CANDIDATE
        )
        rows = []
        for a in sweep.attempts:
            ops = a.first_worker_operations
            k = a.kill_after_commit
            op = ops[k - 1] if k and k <= len(ops) else "?"
            rows.append((k, op, a.execution_status.value,
                         a.post_kill_snapshot, a.final_snapshot, a.failure_detail))
        return (sweep.census.execution_status.value,
                list(sweep.census.first_delivery_operations), rows)

if __name__ == "__main__":
    ref = sys.argv[1]
    census, ops, rows = crash_map(Path(ref) if os.path.isdir(ref) else ref)
    print(f"census={census} commits={ops}")
    for k, op, status, post, final, detail in rows:
        p = f"{post.subject_total}/{post.event_effect_count}/{post.event_marker_count}" if post else "-"
        f = f"{final.subject_total}/{final.event_effect_count}/{final.event_marker_count}" if final else "-"
        print(f"  kill after commit {k} ({op}): {status} post-kill={p} after-retry={f} {detail or ''}")
