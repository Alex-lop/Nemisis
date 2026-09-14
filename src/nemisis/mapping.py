"""The crash-window map: what an agent wants to see *before* it writes the fix.

``map_windows`` runs the same commit sweep ``check`` runs, over the seam the kernel already has,
but stops before any verdict: no base, no bug, no hunt, no minimization, no capsule written to
disk, no ``CrashVerdict``. It seals a capsule from the scenario's audited contract alone, binds
the candidate's anchor, counts the handler's store commits with one no-fault census, and kills
once after each commit — reporting, per kill point, the durable state left behind and the state
after the retry. It answers "where can this handler die, and what survives each death?"

It is read-only and durable-state-free: the sweep runs under a temporary directory that is removed
when the map returns. Nothing is uploaded and no run directory is kept. The kernel it drives never
calls a model.

A census that does not complete cleanly (a handler that writes around the store forfeits its
census the same way it forfeits a verdict) degrades the map to the census's own refusal sentence;
it never prints a clean per-commit map for a tree the kernel could not attribute. An anchor that
cannot bind produces no map at all: ``mappable`` is ``False`` and the caller exits non-zero.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from nemisis import crashcheck as _engine
from nemisis.crash_models import (
    AnchorBinding,
    ExecutionStatus,
    IntegrityStatus,
    StateSnapshot,
    WorldRole,
)
from nemisis.crashcheck import engine_code_digest
from nemisis.models import StrictModel, TruthLabel
from nemisis.scenarios import scenario_for


class CrashWindow(StrictModel):
    """One kill point in the sweep: kill after this commit, and what the retry left behind.

    ``execution_status`` and ``detail`` are the attempt's own, verbatim; no verdict is inferred
    from them. ``post_kill`` is the durable state the instant the worker was killed; ``after_retry``
    is the state after a fresh worker replayed the same event.
    """

    kill_after_commit: int
    operation: str
    execution_status: str
    post_kill: StateSnapshot | None
    after_retry: StateSnapshot | None
    detail: str | None


class MapResult(StrictModel):
    """A verdict-free crash-window map for one candidate tree under one scenario.

    ``mappable`` is ``False`` only when the anchor could not bind (no windows can exist);
    ``census_refusal`` carries the census's sentence when the census did not complete cleanly, and
    ``windows`` is then empty by design — a tree the kernel cannot attribute gets its refusal, not
    a map. ``truth_label`` is the label of the local execution this wraps and is never upgraded.
    """

    scenario_id: str
    truth_label: str
    engine_code_digest: str
    source_ref: str
    tree_digest: str | None
    mappable: bool
    anchor_failure: str | None
    census_status: str
    census_integrity: str
    census_refusal: str | None
    commits: tuple[str, ...]
    windows: tuple[CrashWindow, ...]


def map_windows(candidate: str | Path, scenario_id: str) -> MapResult:
    """Map every crash window in ``candidate`` under ``scenario_id`` without issuing a verdict."""
    scenario = scenario_for(scenario_id)
    contract = _engine._audited_contract(scenario)
    capsule = _engine._seal_capsule(contract)
    label = TruthLabel.LOCAL
    with tempfile.TemporaryDirectory(prefix="nemisis-map-") as tmp:
        scratch = _engine._Scratch(Path(tmp))
        source = scratch.source(candidate, "map-candidate")
        binding = _engine._bind_anchor(contract, source, WorldRole.CANDIDATE, label, capsule.digest)
        if not isinstance(binding, AnchorBinding):
            return MapResult(
                scenario_id=scenario_id,
                truth_label=label.value,
                engine_code_digest=engine_code_digest(),
                source_ref=source.ref,
                tree_digest=None,
                mappable=False,
                anchor_failure=_engine._anchor_failure_summary(binding),
                census_status=ExecutionStatus.UNSUPPORTED.value,
                census_integrity=IntegrityStatus.INVALID.value,
                census_refusal=None,
                commits=(),
                windows=(),
            )
        sweep = _engine._execute_sweep(
            capsule, binding, source.path, scratch.phase(), WorldRole.CANDIDATE
        )
        census = sweep.census
        census_clean = (
            census.execution_status is ExecutionStatus.COMPLETED
            and census.integrity_status is IntegrityStatus.VALID
        )
        windows: tuple[CrashWindow, ...] = ()
        if census_clean:
            operations = census.first_delivery_operations
            windows = tuple(
                CrashWindow(
                    kill_after_commit=attempt.kill_after_commit or 0,
                    operation=(
                        operations[attempt.kill_after_commit - 1]
                        if attempt.kill_after_commit is not None
                        and attempt.kill_after_commit <= len(operations)
                        else "unknown"
                    ),
                    execution_status=attempt.execution_status.value,
                    post_kill=attempt.post_kill_snapshot,
                    after_retry=attempt.final_snapshot,
                    detail=attempt.failure_detail,
                )
                for attempt in sweep.attempts
            )
        return MapResult(
            scenario_id=scenario_id,
            truth_label=label.value,
            engine_code_digest=engine_code_digest(),
            source_ref=source.ref,
            tree_digest=binding.tree_digest,
            mappable=True,
            anchor_failure=None,
            census_status=census.execution_status.value,
            census_integrity=census.integrity_status.value,
            census_refusal=None if census_clean else census.failure_detail,
            commits=tuple(census.first_delivery_operations),
            windows=windows,
        )


__all__ = ["CrashWindow", "MapResult", "map_windows"]
