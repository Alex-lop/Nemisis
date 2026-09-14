"""``nemisis mcp`` — a stdio Model Context Protocol server, so the customer can be an AI coding
agent instead of a person.

Each tool is a thin wrapper over an existing code path. Where the wrapped path has a ``--json``
flag the tool returns the same JSON it prints; ``list_scenarios`` and ``port_template`` are new,
deterministic, read-only views the CLI has no command for. Every tool carries the truth label of
the thing it wraps and never upgrades it. The kernel these tools drive never calls a model; only
``draft_contract`` and ``propose_patch`` do, and both are ``BLOCKED`` without a Token Factory key
rather than mocked silently.

Trust boundary: the server runs on the developer's machine, on the developer's checkout. The
local tools (``check``, ``map``, ``list_scenarios``, ``port_template``, ``doctor``) upload nothing
and write only under the artifact root they name (``.nemisis`` by default, or
``NEMISIS_ARTIFACT_ROOT``): a ``check`` writes a run directory there, and its report and receipt
are exposed as resources addressable by run id. ``draft_contract`` and ``propose_patch`` are the
exceptions: with a key they send the issue text and the base handler you name to the Token Factory
endpoint, ``propose_patch`` also writes an author receipt under ``.nemisis/agent-patches/`` in the
working directory (kernel behavior), and both write their draft or candidate under the artifact
root. Without a key they are ``BLOCKED`` and write nothing.
"""

from __future__ import annotations

import inspect
import os
import tempfile
from pathlib import Path
from typing import Any, cast

from mcp.server.mcpserver import MCPServer

from nemisis.agent_patch import propose_patch as _propose_patch
from nemisis.crashcheck import (
    accept_contract as _accept_contract,
)
from nemisis.crashcheck import (
    check as _check,
)
from nemisis.crashcheck import (
    engine_code_digest,
    initialize,
)
from nemisis.doctor import doctor as _doctor
from nemisis.hashing import canonical_json
from nemisis.mapping import map_windows as _map_windows
from nemisis.models import TruthLabel
from nemisis.nemotron import DEFAULT_MODEL_ID, MODEL_ID_ENV, NemotronError
from nemisis.proposal import PROPOSAL_NAME, propose_contract, write_proposal
from nemisis.scenario import Scenario
from nemisis.scenarios import SCENARIOS, scenario_for

TRUST_BOUNDARY = (
    "This server runs on your machine, on your checkout. The local tools (check, map, "
    "list_scenarios, port_template, doctor) upload nothing and write only under the artifact root "
    "they name. The kernel never calls a model. draft_contract and propose_patch are the "
    "exceptions: with a key they send the issue text and the base handler you name to the Token "
    "Factory endpoint; without a key they are BLOCKED and write nothing. A verdict proves the port "
    "you handed it, not your real handler; you own the correspondence, and the port ledger is "
    "where you state it."
)

INSTRUCTIONS = (
    "Nemisis proves an idempotency/retry fix is crash-safe. When you are fixing a retry, replay, "
    "duplicate-delivery, or idempotency bug: list_scenarios to pick the shape; port_template to "
    "get the store API and the skeleton; write a minimal port of the real handler under "
    ".nemisis/port/<scenario>/; map to see the crash windows; check until "
    "FIX_PROVEN_FOR_THIS_CAPSULE. EVIDENCE_INCOMPLETE is never a pass — read the remedy and change "
    "the port, never the kernel. Then apply the same change to the real handler, fill in the port "
    "ledger (which real lines map to which store calls, and what the port does not carry), and "
    "attach the receipt and the ledger to the PR. " + TRUST_BOUNDARY
)


def _jsonable(value: Any) -> Any:
    """Exactly the bytes the ``--json`` flags print, decoded to a Python object."""
    import json

    return json.loads(canonical_json(value).decode())


def _artifact_root() -> Path:
    return Path(os.environ.get("NEMISIS_ARTIFACT_ROOT", ".nemisis")).resolve()


def _store_methods(scenario: Scenario) -> list[dict[str, str]]:
    """The committing store methods with their real signatures, read off the store class."""
    methods: list[dict[str, str]] = []
    for name in scenario.store_operations:
        function = getattr(scenario.store_class, name, None)
        signature = str(inspect.signature(function)) if callable(function) else "()"
        methods.append({"name": name, "signature": f"store.{name}{signature}"})
    # ``processed``/``reserved``/``sent`` is the read the handler guards on; name it too.
    for name in dir(scenario.store_class):
        if name in {m["name"] for m in methods} or name.startswith("_"):
            continue
        function = getattr(scenario.store_class, name, None)
        if callable(function) and name in {"processed", "reserved", "sent"}:
            methods.insert(
                0, {"name": name, "signature": f"store.{name}{inspect.signature(function)}"}
            )
    return methods


def _invariant(scenario: Scenario) -> str:
    return (
        f"each event's {scenario.effect_noun} is durable at most once; a crash between the "
        f"{scenario.effect_noun} and its marker must not double the {scenario.effect_noun} when "
        "the event is retried."
    )


def _forfeits(scenario: Scenario) -> list[dict[str, str]]:
    remedy = scenario.store_remedy
    return [
        {
            "shape": "raw SQL around the store",
            "verdict": "EVIDENCE_INCOMPLETE",
            "why": "a write the store did not make has no kill point, so no crash window can be "
            "reached and no verdict is issued",
            "remedy": remedy,
        },
        {
            "shape": "a dedup table or key of your own",
            "verdict": "EVIDENCE_INCOMPLETE",
            "why": "durable state the store did not commit is invisible to the sweep and forfeits "
            "the verdict the same way",
            "remedy": remedy,
        },
        {
            "shape": "any write beside the database (a file, a flag, an attribute)",
            "verdict": "EVIDENCE_INCOMPLETE",
            "why": "durable state outside the store has crash windows the sweep cannot reach",
            "remedy": remedy,
        },
    ]


def _run_paths(artifacts: dict[str, str]) -> dict[str, str | None]:
    """The absolute report and receipt paths of a run, and the run id, from its artifact map."""
    root = _artifact_root()
    report = artifacts.get("report")
    capsule = artifacts.get("capsule")
    run_id = Path(report).parent.name if report else None
    return {
        "run_id": run_id,
        "run_directory": str(root / "runs" / run_id) if run_id else None,
        "report_path": str(root / report) if report else None,
        "receipt_path": str(root / capsule) if capsule else None,
        "report_resource": f"nemisis://run/{run_id}/report" if run_id and report else None,
        "receipt_resource": f"nemisis://run/{run_id}/receipt" if run_id and capsule else None,
    }


# run id -> the absolute report and receipt paths a check produced this session.
_RUNS: dict[str, dict[str, str]] = {}


def build_server() -> MCPServer:
    server = MCPServer(
        "nemisis",
        instructions=INSTRUCTIONS,
        version=_version(),
    )

    @server.tool(
        description="List the audited scenarios: id, bound target, store methods with signatures, "
        "the invariant, and the fixture variants. Pick the shape that matches the bug."
    )
    def list_scenarios() -> dict[str, Any]:
        scenarios = []
        for scenario in SCENARIOS.values():
            scenarios.append(
                {
                    "id": scenario.scenario_id,
                    "target": scenario.target,
                    "handler_relative": scenario.handler_relative,
                    "store_methods": _store_methods(scenario),
                    "invariant": _invariant(scenario),
                    "variants": {
                        "hero": list(scenario.hero_variants),
                        "zoo": list(scenario.zoo_variants),
                    },
                }
            )
        return {
            "scenarios": scenarios,
            "truth_label": TruthLabel.FIXTURE.value,
            "engine_code_digest": engine_code_digest(),
        }

    @server.tool(
        description="A deterministic port template for one scenario: the bound file's skeleton, "
        "the store API, the invariant, and the three shapes that forfeit a verdict with the "
        "remedy for each. Write your port against this; do not restructure the kernel."
    )
    def port_template(scenario: str) -> dict[str, Any]:
        item = scenario_for(scenario)
        symbol = item.target.split(":", 1)[1] if ":" in item.target else item.target
        skeleton = (
            f'"""Port of your real handler to the {item.scenario_id} store. '
            f'Fill in {symbol}."""\n\n\n'
            f"def {symbol}(store, event):\n"
            f"    # store API: {item.store_api_fallback}\n"
            f"    # invariant: {_invariant(item)}\n"
            "    # EVIDENCE_INCOMPLETE (never a pass): raw SQL around the store, a dedup table of\n"
            "    # your own, or any write beside the database. Express the fix through the store.\n"
            "    ...\n"
        )
        return {
            "scenario": item.scenario_id,
            "target": item.target,
            "handler_relative": item.handler_relative,
            "handler_symbol": symbol,
            "skeleton": skeleton,
            "store_api": item.store_api_fallback,
            "invariant": _invariant(item),
            "forfeits": _forfeits(item),
            "truth_label": TruthLabel.FIXTURE.value,
        }

    @server.tool(
        description="Run a crash/retry counterexample on a candidate tree. Default base is the "
        "scenario's buggy fixture. Returns the verdict, exit code, run directory, and the report "
        "and receipt resources. FIX_PROVEN_FOR_THIS_CAPSULE (exit 0) is the pass; "
        "EVIDENCE_INCOMPLETE (exit 2) means read the summary's remedy and fix the port."
    )
    def check(candidate: str, scenario: str, base: str | None = None) -> dict[str, Any]:
        from nemisis.cli import _exit_code
        from nemisis.crashcheck import CrashCheckError

        try:
            scenario_ref = scenario_for(scenario).scenario_id
        except ValueError as error:
            return {"error": str(error), "truth_label": TruthLabel.LOCAL.value}
        base_ref = base or f"fixture:{scenario_ref}/buggy"
        try:
            with _artifact_root_env():
                result = _check(base_ref, candidate, scenario_ref, mode="local")
        except (CrashCheckError, ValueError, OSError) as error:
            return {
                "error": str(error),
                "verdict": "EVIDENCE_INCOMPLETE",
                "exit_code": 2,
                "truth_label": TruthLabel.LOCAL.value,
            }
        paths = _run_paths(dict(result.artifacts))
        if paths["run_id"] and paths["report_path"] and paths["receipt_path"]:
            _RUNS[str(paths["run_id"])] = {
                "report": str(paths["report_path"]),
                "receipt": str(paths["receipt_path"]),
            }
        return {
            "verdict": result.verdict.value,
            "exit_code": _exit_code(result.verdict),
            "summary": result.summary,
            "truth_label": result.transport.value,
            "engine_code_digest": result.engine_code_digest,
            **paths,
            "result": _jsonable(result),
        }

    @server.tool(
        description="A verdict-free crash-window map: for each store commit, the durable state a "
        "crash there leaves and the state after the retry. Run it before writing the fix. A tree "
        "the kernel cannot attribute gets its census refusal, not a map."
    )
    def map(candidate: str, scenario: str) -> dict[str, Any]:
        try:
            scenario_ref = scenario_for(scenario).scenario_id
        except ValueError as error:
            return {"error": str(error), "truth_label": TruthLabel.LOCAL.value}
        with _artifact_root_env():
            result = _map_windows(candidate, scenario_ref)
        return cast(dict[str, Any], _jsonable(result))

    @server.tool(
        description="Ask Nemotron on Token Factory to draft the contract from the issue and base "
        "only, candidate-blind. Returns the DRAFT and its digest; acceptance is a separate call. "
        "BLOCKED without NEBIUS_API_KEY."
    )
    def draft_contract(
        issue: str, target: str, base: str, scenario: str, model: str | None = None
    ) -> dict[str, Any]:
        if not os.getenv("NEBIUS_API_KEY"):
            return _blocked("NEBIUS_API_KEY is required for live Nemotron calls", model)
        scenario_ref = scenario_for(scenario).scenario_id
        with _model_env(model), tempfile.TemporaryDirectory(prefix="nemisis-mcp-") as tmp:
            issue_file = Path(tmp) / "issue.md"
            issue_file.write_text(issue, encoding="utf-8")
            try:
                with _artifact_root_env():
                    proposal = propose_contract(issue_file, target, base, scenario_ref)
                    config = initialize(issue_file, target, base, scenario_ref)
                    write_proposal(proposal, config.with_name(PROPOSAL_NAME))
            except NemotronError as error:
                return _blocked(str(error), model)
        return {
            "truth_label": proposal.model_call.truth_label.value,
            "contract_draft": proposal.model_dump(mode="json"),
            "draft_digest": proposal.digest,
            "model_id": proposal.model_call.model_id,
            "config": str(config),
            "accept_with": "call accept_contract(digest, config) to re-seal the draft as LOCAL",
        }

    @server.tool(
        description="Accept a contract DRAFT by its digest and re-seal it as LOCAL. Deterministic; "
        "no model call."
    )
    def accept_contract(digest: str, config: str) -> dict[str, Any]:
        with _artifact_root_env():
            contract = _accept_contract(digest, Path(config))
        return {
            "truth_label": TruthLabel.LOCAL.value,
            "accepted_digest": digest,
            "contract_digest": contract.digest,
        }

    @server.tool(
        description="Ask Nemotron on Token Factory to write the fix; the result is an ordinary "
        "candidate tree you then check. Super tier by default; pass a full Token Factory catalog "
        "model id via model= for another tier (tier names like 'ultra' are not aliases and are "
        "not resolved). BLOCKED without NEBIUS_API_KEY."
    )
    def propose_patch(
        issue: str, base: str, scenario: str, out: str | None = None, model: str | None = None
    ) -> dict[str, Any]:
        if not os.getenv("NEBIUS_API_KEY"):
            return _blocked("NEBIUS_API_KEY is required for live Nemotron calls", model)
        scenario_ref = scenario_for(scenario).scenario_id
        output = Path(out) if out else _artifact_root() / "port" / scenario_ref / "nemotron"
        with _model_env(model), tempfile.TemporaryDirectory(prefix="nemisis-mcp-") as tmp:
            issue_file = Path(tmp) / "issue.md"
            issue_file.write_text(issue, encoding="utf-8")
            try:
                with _artifact_root_env():
                    patch = _propose_patch(issue_file, base, output, scenario_ref)
            except NemotronError as error:
                return _blocked(str(error), model)
        return {
            "truth_label": patch.model_call.truth_label.value,
            "candidate": str(output),
            "model_id": patch.model_call.model_id,
            "patch_proposal": patch.model_dump(mode="json"),
            "next": f"check(candidate={str(output)!r}, scenario={scenario_ref!r})",
        }

    @server.tool(
        description="CrashCheck prerequisites and truth labels, verbatim. Live mode (the default) "
        "adds the secret-free presence checks for the Token Factory key and the live adapters, so "
        "what is READY and what is BLOCKED, and on what, is visible."
    )
    def doctor(mode: str = "live") -> dict[str, Any]:
        checked = mode if mode in {"local", "live"} else "live"
        return cast(dict[str, Any], _jsonable(_doctor(checked)))

    @server.resource("nemisis://run/{run_id}/report")
    def run_report(run_id: str) -> str:
        return _read_run(run_id, "report")

    @server.resource("nemisis://run/{run_id}/receipt")
    def run_receipt(run_id: str) -> str:
        return _read_run(run_id, "receipt")

    return server


def _read_run(run_id: str, kind: str) -> str:
    run = _RUNS.get(run_id)
    if run is None or kind not in run:
        raise ValueError(f"no {kind} for run {run_id!r} in this session")
    return Path(run[kind]).read_text(encoding="utf-8")


def _blocked(reason: str, model: str | None) -> dict[str, Any]:
    return {
        "truth_label": TruthLabel.BLOCKED.value,
        "blocked": reason,
        "requested_model": model or f"{MODEL_ID_ENV} or default {DEFAULT_MODEL_ID}",
        "note": "no model call was made and nothing was written; export NEBIUS_API_KEY to unblock",
    }


class _artifact_root_env:
    """Pin NEMISIS_ARTIFACT_ROOT to the resolved root for the duration of one wrapped call."""

    def __enter__(self) -> None:
        self._previous = os.environ.get("NEMISIS_ARTIFACT_ROOT")
        os.environ["NEMISIS_ARTIFACT_ROOT"] = str(_artifact_root())

    def __exit__(self, *_exc: object) -> None:
        if self._previous is None:
            os.environ.pop("NEMISIS_ARTIFACT_ROOT", None)
        else:
            os.environ["NEMISIS_ARTIFACT_ROOT"] = self._previous


class _model_env:
    """Select the Nemotron tier for one call via NEMISIS_MODEL_ID, if a model id was given.

    The exact catalog ids come from the Token Factory listing, not from this file; ``model`` is
    passed through verbatim as the id (no tier-name aliases). Super (the packaged default) is used
    when none is given.
    """

    def __init__(self, model: str | None) -> None:
        self._model = model

    def __enter__(self) -> None:
        self._previous = os.environ.get(MODEL_ID_ENV)
        if self._model:
            os.environ[MODEL_ID_ENV] = self._model

    def __exit__(self, *_exc: object) -> None:
        if self._previous is None:
            os.environ.pop(MODEL_ID_ENV, None)
        elif self._model:
            os.environ[MODEL_ID_ENV] = self._previous


def _version() -> str:
    from nemisis import __version__

    return __version__


def run() -> None:
    """Entry point for ``nemisis mcp`` and the ``nemisis-mcp`` console script."""
    build_server().run(transport="stdio")


__all__ = ["build_server", "run", "TRUST_BOUNDARY", "INSTRUCTIONS"]
