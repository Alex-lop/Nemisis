"""Nemotron as the coding agent: ``nemisis propose-patch``.

This is the model's load-bearing job. It receives the bug report, the base handler module, and
the storage API, and returns a complete replacement module. It never sees how CrashCheck kills,
which boundary the capsule froze, or what the verdict rules are; it is a coding agent, and its
output is a candidate tree that ``check`` executes exactly like a human's patch.

Deterministic rules decide whether the module may be written at all: one top-level handler with
the exact ``(store, event)`` signature, imports from ``typing`` only, no private attributes, no
dangerous builtins. A rejected module writes nothing. An accepted one becomes a candidate tree
and the sanitized receipt is written to the operator's own ``.nemisis/agent-patches/`` keyed by
the candidate tree digest, never inside the candidate tree: a tree that arrives in a pull request
cannot carry its own claim of who wrote it. ``check`` attaches the receipt only when the operator
holds one for exactly that tree and the receipt's module digest matches the bound handler. The
receipt never contains the credential or the raw model response.
"""

from __future__ import annotations

import ast
import shutil
import tempfile
from pathlib import Path
from typing import Protocol

from nemisis.crash_fixture import SCENARIO_ID
from nemisis.crash_models import PatchProposal
from nemisis.crashcheck import (
    MAX_CONFIG_BYTES,
    CrashCheckError,
    _audited_contract,
    _copy_tree,
    _materialize_source,
    _write_exact,
)
from nemisis.hashing import canonical_json, sha256_text, sha256_tree
from nemisis.nemotron import NemotronClient, NemotronPatchGeneration
from nemisis.sqlite_credit import AnchorResolutionError, bind_anchor

RECEIPTS_DIR = Path(".nemisis/agent-patches")
_ALLOWED_IMPORT_MODULES = frozenset({"typing", "__future__"})
_DANGEROUS_NAMES = frozenset(
    {
        "__import__",
        "breakpoint",
        "compile",
        "delattr",
        "eval",
        "exec",
        "exit",
        "getattr",
        "globals",
        "input",
        "locals",
        "memoryview",
        "open",
        "quit",
        "setattr",
        "vars",
    }
)


class PatchError(ValueError):
    """The model's module was not accepted; no candidate tree was written."""


class Patcher(Protocol):
    def generate_patch(
        self, issue: str, module_source: str, store_api: str
    ) -> NemotronPatchGeneration: ...


def propose_patch(
    issue: str | Path,
    base: str | Path,
    output: Path,
    scenario_id: str = SCENARIO_ID,
    *,
    client: Patcher | None = None,
) -> PatchProposal:
    """Have the model fix the base handler; write the result as a candidate tree if it is safe."""
    if scenario_id != SCENARIO_ID:
        raise PatchError(f"unsupported scenario: {scenario_id}")
    output = Path(output)
    if output.exists():
        raise PatchError(f"output directory already exists: {output}")
    issue_path = Path(issue)
    try:
        if not issue_path.is_file() or issue_path.stat().st_size > MAX_CONFIG_BYTES:
            raise PatchError("issue must be a UTF-8 file no larger than 100,000 bytes")
        issue_text = issue_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise PatchError("issue must be a readable UTF-8 file") from error

    with tempfile.TemporaryDirectory(prefix="nemisis-agent-") as temporary:
        source = _materialize_source(base, Path(temporary) / "base")
        try:
            binding = bind_anchor(
                _audited_contract(),
                source.path,
                source_ref=source.ref,
                resolved_source_identity=source.resolved_identity,
            )
        except AnchorResolutionError as error:
            raise PatchError(f"base handler did not bind: {error}") from error
        handler_file = source.path / binding.handler_path
        try:
            module_source = handler_file.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as error:
            raise PatchError("base handler is not readable UTF-8") from error

        proposer = client if client is not None else NemotronClient()
        generation = proposer.generate_patch(issue_text, module_source, _store_api(module_source))
        _validate_module(generation.module_source, binding.handler_symbol)

        # Write the candidate tree: the exact base tree with only the handler module replaced.
        try:
            _copy_tree(source.path, output)
            (output / binding.handler_path).write_text(generation.module_source, encoding="utf-8")
            candidate_tree_digest = sha256_tree(output)
            proposal = PatchProposal.with_digest(
                scenario_id=scenario_id,
                issue_digest=sha256_text(issue_text),
                base_ref=source.ref,
                base_tree_digest=source.tree_digest,
                handler_path=binding.handler_path,
                module_digest=sha256_text(generation.module_source),
                candidate_tree_digest=candidate_tree_digest,
                rationale=generation.rationale,
                model_call=generation.receipt,
            )
            _write_exact(
                receipt_path(candidate_tree_digest), canonical_json(proposal) + b"\n", replace=True
            )
        except (CrashCheckError, ValueError, OSError) as error:
            cleanup_rejected(output)
            raise PatchError(f"candidate tree could not be written: {error}") from error
    return proposal


def receipt_path(candidate_tree_digest: str) -> Path:
    """Where the operator keeps the authorship receipt for one exact candidate tree."""
    return Path.cwd() / RECEIPTS_DIR / f"{candidate_tree_digest}.json"


def _store_api(module_source: str) -> str:
    """The storage surface the model may use: the store Protocol as written in the base module."""
    try:
        tree = ast.parse(module_source)
    except SyntaxError as error:
        raise PatchError("base handler module is not valid Python") from error
    protocol = next(
        (
            node
            for node in tree.body
            if isinstance(node, ast.ClassDef)
            and any(getattr(base, "id", None) == "Protocol" for base in node.bases)
        ),
        None,
    )
    if protocol is None:
        return (
            "store.processed(event_id) -> bool; store.credit(account_id, event_id, amount_cents); "
            "store.mark_processed(event_id); store.credit_and_mark(account_id, event_id, "
            "amount_cents). Every call is one durable SQLite commit."
        )
    return ast.unparse(protocol) + "\nEvery store call is one durable SQLite commit."


def _validate_module(source: str, symbol: str) -> None:
    """Accept only a module CrashCheck can bind and that stays inside the store API."""
    if "\x00" in source:
        raise PatchError("model module contains a NUL byte")
    try:
        tree = ast.parse(source)
    except SyntaxError as error:
        raise PatchError("model module is not valid Python") from error
    handlers = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name == symbol
    ]
    if len(handlers) != 1 or isinstance(handlers[0], ast.AsyncFunctionDef):
        raise PatchError(f"model module must define exactly one synchronous top-level {symbol}")
    arguments = handlers[0].args
    if (
        len(arguments.posonlyargs) + len(arguments.args) != 2
        or arguments.vararg is not None
        or arguments.kwarg is not None
        or arguments.kwonlyargs
        or arguments.defaults
    ):
        raise PatchError(f"model module must keep the exact {symbol}(store, event) signature")
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] not in _ALLOWED_IMPORT_MODULES:
                    raise PatchError(f"model module import is not allowed: {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            module = (node.module or "").split(".")[0]
            if node.level or module not in _ALLOWED_IMPORT_MODULES:
                raise PatchError(f"model module import is not allowed: {node.module or '.'}")
        elif isinstance(node, ast.Name) and node.id in _DANGEROUS_NAMES:
            raise PatchError(f"model module uses a dangerous builtin: {node.id}")
        elif isinstance(node, ast.Name) and node.id.startswith("_") and node.id != "_":
            # __builtins__["__import__"], __loader__, __spec__, __class__: every route to the
            # interpreter's internals starts with an underscore, so none are allowed by name.
            raise PatchError(f"model module uses a private name: {node.id}")
        elif isinstance(node, ast.Attribute) and node.attr.startswith("_"):
            raise PatchError(f"model module reads a private attribute: {node.attr}")
        elif isinstance(node, ast.Global | ast.Nonlocal):
            raise PatchError("model module uses global or nonlocal state")


def describe(proposal: PatchProposal) -> str:
    receipt = proposal.model_call
    return (
        f"{receipt.model_id} ({receipt.truth_label.value}) rewrote {proposal.handler_path}; "
        f"module {proposal.module_digest[:16]}, "
        f"candidate tree {proposal.candidate_tree_digest[:16]}"
    )


def cleanup_rejected(output: Path) -> None:
    """A rejected proposal must leave no half-written tree behind."""
    shutil.rmtree(output, ignore_errors=True)


__all__ = [
    "RECEIPTS_DIR",
    "PatchError",
    "Patcher",
    "cleanup_rejected",
    "describe",
    "propose_patch",
    "receipt_path",
]
