"""Mutation-test the CrashCheck kernel: flip one operator of a refusal and see if the suite notices.

The checker of the checker. Every refusal in the kernel is a comparison, a boolean, a constant, or
a literal; this tool rewrites one of them at a time and runs the suite. A mutant the suite fails on
is *killed*: some test depends on that operator. A mutant the suite still passes is a *survivor*:
either the mutant is provably equivalent to the original, or nothing tests that operator and the
survivor names a hole.

Usage::

    uv run python tools/mutants.py \\
        --target src/nemisis/sqlite_runner.py::_require_only_the_store_wrote \\
        --tests tests/test_crash_models.py tests/test_sqlite_runner.py \\
        --out docs/reports/mutation-ledger.json

``--target`` takes ``path.py::name`` and repeats; ``name`` is a module-level function, a
module-level assignment (``_SEED_MODE``, ``_HEADER_PRAGMAS``), or ``Class.method``.

Operators (fixed, small, one edit each):

===============  ==========================================================================
``cmp-flip``     ``==``/``!=``, ``<``/``<=``, ``>``/``>=``, ``is``/``is not``, ``in``/``not in``
``bool-swap``    ``and`` <-> ``or``
``not-drop``     drop a ``not``
``usub-drop``    drop a unary minus (``-signal.SIGKILL`` -> ``signal.SIGKILL``)
``int-const``    an integer constant to ``n+1``, ``n-1``, and ``-n``
``seq-drop``     drop one element of a set, tuple, list, or dict literal
``slice-drop``   ``x[a:b]`` -> ``x``
``raise-pass``   a ``raise`` statement -> ``pass``
``return-none``  ``return X`` -> ``return None``
``ledger-field`` ``.content`` <-> ``.snapshot``
===============  ==========================================================================

``ledger-field`` is the one domain-specific operator: the runner's ``_Ledger`` carries both the
whole database (``.content``) and the four numbers the scenario reads from it (``.snapshot``), and
confusing them silently narrows a whole-database comparison to four integers.

Two test files must stay out of ``--tests``: ``tests/test_docs_identity.py`` and
``tests/test_static_hero.py``. Both quote ``engine_code_digest()``, which hashes the engine sources
this tool edits, so they fail for *every* mutant and would report a kill the suite did not earn.

The original bytes come from ``git show HEAD:<path>``, are restored in a ``finally``, and
``git diff --stat`` is checked after every mutant; the tool refuses to start on a dirty target file.
A mutant whose run hit a wall-clock timeout, or whose failure output mentions the engine's own IPC
timeout, is rerun once before its status counts, because the wall clock is not evidence.
"""

from __future__ import annotations

import argparse
import ast
import json
import subprocess
import sys
import time
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path

_CMP_FLIP: dict[type[ast.cmpop], type[ast.cmpop]] = {
    ast.Eq: ast.NotEq,
    ast.NotEq: ast.Eq,
    ast.Lt: ast.LtE,
    ast.LtE: ast.Lt,
    ast.Gt: ast.GtE,
    ast.GtE: ast.Gt,
    ast.Is: ast.IsNot,
    ast.IsNot: ast.Is,
    ast.In: ast.NotIn,
    ast.NotIn: ast.In,
}

# A failure that says only this is the machine talking, not the mutant; rerun it once.
_FLAKY_MARKERS = ("IPC timed out", "ExecutionStatus.TIMEOUT")


@dataclass(frozen=True)
class _Site:
    """One edit: the node whose source segment is replaced, and the text that replaces it."""

    node: ast.expr | ast.stmt
    operator: str
    replacement: str


@dataclass(frozen=True)
class _Mutant:
    target: str
    path: str
    line: int
    operator: str
    description: str
    source: str


def _git_show(root: Path, relative: str) -> bytes:
    done = subprocess.run(
        ["git", "show", f"HEAD:{relative}"],
        cwd=root,
        capture_output=True,
        check=True,
    )
    return done.stdout


def _require_clean(root: Path, relative: str) -> None:
    done = subprocess.run(
        ["git", "diff", "--stat", "--", relative],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    if done.stdout.strip():
        raise RuntimeError(f"{relative} is not the committed source: {done.stdout.strip()}")


def _char_column(line: str, byte_column: int) -> int:
    """``col_offset`` counts UTF-8 bytes; this file has a ``…`` in it, so convert."""
    return len(line.encode("utf-8")[:byte_column].decode("utf-8"))


def _span(source: str, node: ast.expr | ast.stmt) -> tuple[int, int]:
    if node.end_lineno is None or node.end_col_offset is None:
        raise RuntimeError(f"node at line {node.lineno} carries no end position")
    lines = source.splitlines(keepends=True)
    starts = [0]
    for line in lines:
        starts.append(starts[-1] + len(line))
    begin = starts[node.lineno - 1] + _char_column(lines[node.lineno - 1], node.col_offset)
    end = starts[node.end_lineno - 1] + _char_column(
        lines[node.end_lineno - 1], node.end_col_offset
    )
    return begin, end


def _defined_name(statement: ast.stmt) -> str | None:
    """The single name a statement binds at this level, if it binds exactly one plain name."""
    if isinstance(statement, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
        return statement.name
    targets: list[ast.expr] = []
    if isinstance(statement, ast.Assign):
        targets = list(statement.targets)
    elif isinstance(statement, ast.AnnAssign):
        targets = [statement.target]
    names = [target.id for target in targets if isinstance(target, ast.Name)]
    return names[0] if names else None


def _find(module: ast.Module, dotted: str) -> ast.stmt:
    body: Sequence[ast.stmt] = module.body
    found: ast.stmt | None = None
    for part in dotted.split("."):
        found = next((item for item in body if _defined_name(item) == part), None)
        if found is None:
            raise SystemExit(f"no such target: {dotted}")
        body = found.body if isinstance(found, ast.ClassDef) else []
    assert found is not None
    return found


def _wrapped(node: ast.expr) -> str:
    """Parenthesize every expression replacement so precedence at the splice cannot change."""
    return f"({ast.unparse(node)})"


def _sites(target: ast.stmt) -> Iterator[_Site]:
    skipped = _skipped(target)
    for node in ast.walk(target):
        if id(node) in skipped or not isinstance(node, ast.expr | ast.stmt):
            continue
        yield from _node_sites(node)


def _skipped(target: ast.stmt) -> set[int]:
    """Two regions no mutant belongs in.

    An f-string's internals: splicing replacement text between the quotes can change what the
    string delimits, not what the code decides. A type annotation: it states an intent the runtime
    never checks here, so flipping it mutates documentation, not a refusal.
    """
    skip: set[int] = set()
    for node in ast.walk(target):
        regions: list[ast.expr | None] = []
        if isinstance(node, ast.JoinedStr):
            regions = [node]
        elif isinstance(node, ast.AnnAssign):
            regions = [node.annotation]
        elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            arguments = node.args
            every = [
                *arguments.posonlyargs,
                *arguments.args,
                *arguments.kwonlyargs,
                arguments.vararg,
                arguments.kwarg,
            ]
            regions = [node.returns, *(item.annotation for item in every if item is not None)]
        for region in regions:
            if region is not None:
                skip.update(id(child) for child in ast.walk(region))
    return skip


def _node_sites(node: ast.expr | ast.stmt) -> Iterator[_Site]:
    if isinstance(node, ast.Compare):
        for index, operator in enumerate(node.ops):
            flipped = _CMP_FLIP.get(type(operator))
            if flipped is None:
                continue
            ops = list(node.ops)
            ops[index] = flipped()
            mutated = ast.Compare(left=node.left, ops=ops, comparators=node.comparators)
            yield _Site(node, "cmp-flip", _wrapped(mutated))
    elif isinstance(node, ast.BoolOp):
        swapped: ast.boolop = ast.Or() if isinstance(node.op, ast.And) else ast.And()
        yield _Site(node, "bool-swap", _wrapped(ast.BoolOp(op=swapped, values=node.values)))
    elif isinstance(node, ast.UnaryOp):
        if isinstance(node.op, ast.Not):
            yield _Site(node, "not-drop", _wrapped(node.operand))
        elif isinstance(node.op, ast.USub):
            yield _Site(node, "usub-drop", _wrapped(node.operand))
    elif isinstance(node, ast.Constant):
        if isinstance(node.value, int) and not isinstance(node.value, bool):
            seen = {node.value}
            for value in (node.value + 1, node.value - 1, -node.value):
                if value in seen:
                    continue
                seen.add(value)
                yield _Site(node, "int-const", f"({value})")
    elif isinstance(node, ast.Set | ast.Tuple | ast.List):
        yield from _sequence_sites(node)
    elif isinstance(node, ast.Dict):
        yield from _dict_sites(node)
    elif isinstance(node, ast.Subscript):
        if isinstance(node.slice, ast.Slice) and isinstance(node.ctx, ast.Load):
            yield _Site(node, "slice-drop", _wrapped(node.value))
    elif isinstance(node, ast.Attribute):
        if node.attr in ("content", "snapshot") and isinstance(node.ctx, ast.Load):
            other = "snapshot" if node.attr == "content" else "content"
            swap = ast.Attribute(value=node.value, attr=other, ctx=ast.Load())
            yield _Site(node, "ledger-field", _wrapped(swap))
    elif isinstance(node, ast.Raise):
        yield _Site(node, "raise-pass", "pass")
    elif isinstance(node, ast.Return):
        empty = isinstance(node.value, ast.Constant) and node.value.value is None
        if node.value is not None and not empty:
            yield _Site(node, "return-none", "return None")


def _sequence_sites(node: ast.Set | ast.Tuple | ast.List) -> Iterator[_Site]:
    store = isinstance(node, ast.Tuple | ast.List) and not isinstance(node.ctx, ast.Load)
    if store or len(node.elts) < 2:
        return
    for index in range(len(node.elts)):
        kept = [element for position, element in enumerate(node.elts) if position != index]
        mutated: ast.expr
        if isinstance(node, ast.Set):
            mutated = ast.Set(elts=kept)
        elif isinstance(node, ast.Tuple):
            mutated = ast.Tuple(elts=kept, ctx=ast.Load())
        else:
            mutated = ast.List(elts=kept, ctx=ast.Load())
        yield _Site(node, "seq-drop", _wrapped(mutated))


def _dict_sites(node: ast.Dict) -> Iterator[_Site]:
    if len(node.keys) < 2 or any(key is None for key in node.keys):
        return
    for index in range(len(node.keys)):
        keys = [key for position, key in enumerate(node.keys) if position != index]
        values = [value for position, value in enumerate(node.values) if position != index]
        yield _Site(node, "seq-drop", _wrapped(ast.Dict(keys=keys, values=values)))


def _shortened(text: str, limit: int = 68) -> str:
    collapsed = " ".join(text.split())
    return collapsed if len(collapsed) <= limit else collapsed[: limit - 1] + "…"


def _mutants(root: Path, target: str) -> list[_Mutant]:
    relative, _, dotted = target.partition("::")
    if not dotted:
        raise SystemExit(f"--target wants path.py::name, got {target!r}")
    source = _git_show(root, relative).decode("utf-8")
    node = _find(ast.parse(source), dotted)
    built: list[_Mutant] = []
    for site in _sites(node):
        begin, end = _span(source, site.node)
        original = source[begin:end]
        built.append(
            _Mutant(
                target=target,
                path=relative,
                line=site.node.lineno,
                operator=site.operator,
                description=f"{_shortened(original)} -> {_shortened(site.replacement)}",
                source=source[:begin] + site.replacement + source[end:],
            )
        )
    built.sort(key=lambda mutant: (mutant.line, mutant.operator, mutant.description))
    return built


def _first_failure(output: str) -> str | None:
    for line in output.splitlines():
        for prefix in ("FAILED ", "ERROR "):
            if line.startswith(prefix):
                return line[len(prefix) :].split(" ")[0]
    return None


def _pytest(root: Path, tests: Sequence[str], timeout: float) -> tuple[str, str | None, float, str]:
    argv = ["uv", "run", "pytest", "-q", "-x", "-p", "no:cacheprovider", *tests]
    started = time.monotonic()
    try:
        done = subprocess.run(argv, cwd=root, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return "timeout", None, time.monotonic() - started, ""
    seconds = time.monotonic() - started
    output = done.stdout + done.stderr
    if done.returncode == 0:
        return "survived", None, seconds, output
    return "killed", _first_failure(output), seconds, output


def _machine_noise(status: str, output: str) -> bool:
    return status == "timeout" or any(marker in output for marker in _FLAKY_MARKERS)


def _run_one(
    root: Path, mutant: _Mutant, original: bytes, tests: Sequence[str], timeout: float
) -> dict[str, object]:
    full = root / mutant.path
    try:
        full.write_bytes(mutant.source.encode("utf-8"))
        status, killed_by, seconds, output = _pytest(root, tests, timeout)
        reruns = 0
        if _machine_noise(status, output):
            reruns = 1
            status, killed_by, again, output = _pytest(root, tests, timeout)
            seconds += again
    finally:
        full.write_bytes(original)
        _require_clean(root, mutant.path)
    return {
        "target": mutant.target,
        "path": mutant.path,
        "line": mutant.line,
        "operator": mutant.operator,
        "description": mutant.description,
        "status": status,
        "killed_by": killed_by,
        "seconds": round(seconds, 1),
        "reruns": reruns,
    }


def _engine_digest(root: Path) -> str:
    done = subprocess.run(
        [
            "uv",
            "run",
            "python",
            "-c",
            "from nemisis.crashcheck import engine_code_digest; print(engine_code_digest())",
        ],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    return done.stdout.strip()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", action="append", required=True, metavar="FILE.py::NAME")
    parser.add_argument("--tests", nargs="+", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--timeout", type=float, default=900.0)
    parser.add_argument("--limit", type=int, default=0, help="run only the first N mutants")
    parser.add_argument("--list", action="store_true", help="enumerate mutants and stop")
    arguments = parser.parse_args(argv)

    root: Path = arguments.root.resolve()
    targets: list[str] = arguments.target
    tests: list[str] = arguments.tests
    for name in ("tests/test_docs_identity.py", "tests/test_static_hero.py"):
        if any(name in test for test in tests):
            raise SystemExit(f"{name} fails for every mutant (engine digest); drop it from --tests")

    planned: list[_Mutant] = []
    for target in targets:
        planned.extend(_mutants(root, target))
    if arguments.limit:
        planned = planned[: arguments.limit]

    for index, mutant in enumerate(planned, start=1):
        print(
            f"[{index}/{len(planned)}] {mutant.target}:{mutant.line} "
            f"{mutant.operator} {mutant.description}",
            flush=True,
        )
    if arguments.list:
        return 0

    originals: dict[str, bytes] = {}
    for mutant in planned:
        if mutant.path not in originals:
            _require_clean(root, mutant.path)
            originals[mutant.path] = _git_show(root, mutant.path)

    command = (
        "uv run python tools/mutants.py "
        + " ".join(f"--target {target}" for target in targets)
        + " --tests "
        + " ".join(tests)
        + f" --out {arguments.out}"
    )
    ledger: dict[str, object] = {
        "command": command,
        "engine_code_digest": _engine_digest(root),
        "tests": tests,
        "targets": targets,
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "results": [],
    }
    results: list[dict[str, object]] = []
    started = time.monotonic()
    for index, mutant in enumerate(planned, start=1):
        record = _run_one(root, mutant, originals[mutant.path], tests, arguments.timeout)
        results.append(record)
        rerun = " (rerun)" if record["reruns"] else ""
        print(
            f"[{index}/{len(planned)}] {str(record['status']).upper():8} "
            f"{mutant.target}:{mutant.line} {mutant.operator} {mutant.description} "
            f"[{record['killed_by'] or '-'}] {record['seconds']}s{rerun}",
            flush=True,
        )
        ledger["results"] = results
        ledger["wall_clock_seconds"] = round(time.monotonic() - started, 1)
        ledger["totals"] = {
            "mutants": len(planned),
            "run": len(results),
            "killed": sum(1 for item in results if item["status"] == "killed"),
            "survived": sum(1 for item in results if item["status"] == "survived"),
            "timeout": sum(1 for item in results if item["status"] == "timeout"),
        }
        arguments.out.parent.mkdir(parents=True, exist_ok=True)
        arguments.out.write_text(json.dumps(ledger, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(ledger.get("totals", {})), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
