"""Adversarial generator: a grammar over store operations, an oracle, and a comparison.

``nemisis redteam`` renders handler modules from a grammar (the store's guard, effect, marker,
and atomic calls, the same calls wrapped in ``try``/``except`` or a retry loop, and the writes
around the store that two hostile reviews wrote by hand: a file beside, above, under ``~`` or
under the temp directory, a file tidied away before returning, a raw SQL effect, a table, a
pragma, a re-pointed row, and a world-detection attempt), runs ``check`` on each, and compares
the verdict with an oracle computed from the operation sequence alone. The oracle knows what
each store call does to the durable state, where a kill can land (only at store commits), when
the world is scanned (after the kill and after every completed delivery), and that a write
around the store forfeits the verdict; it never runs code. Any disagreement is either a checker
false pass or false fail (the most valuable bug this repository can find) or an oracle bug, and
either way it is a failure of this command.

The grammar speaks every audited scenario's vocabulary (``--scenario``); the oracle is the same
for all of them because the kernel is.

This module is not a trusted engine resource: it writes candidates and reads verdicts, it never
judges.
"""

from __future__ import annotations

import os
import random
from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

from nemisis.crash_models import CrashVerdict
from nemisis.crashcheck import check
from nemisis.scenarios import scenario_for


class Op(StrEnum):
    """One statement of a generated handler."""

    # Store calls: a read, or one commit each.
    GUARD = "guard"  # if store.<processed>(event_id): return
    EFFECT = "effect"  # store.<credit>(...)                one commit
    MARK = "mark"  # store.<mark_processed>(...)          one commit; raises once marked
    ATOMIC = "atomic"  # store.<credit_and_mark>(...)       one commit; no-op once marked
    TRY_MARK = "try_mark"  # the marker inside try/except: a second marker is swallowed
    RETRY_EFFECT = "retry_effect"  # the effect inside a three-attempt retry loop
    # Writes around the store; each is caught by a different probe or scan.
    RAW_FILE = "raw_file"  # a file beside the database
    PARENT_FILE = "parent_file"  # a file one directory above the worker's cwd
    HOME_FILE = "home_file"  # a file under ~
    TMP_FILE = "tmp_file"  # a file under the temp directory
    DELETE_FILE = "delete_file"  # remove the file beside the database, if it exists
    RAW_SQL = "raw_sql"  # the effect through a private connection, no store commit
    TABLE = "table"  # CREATE TABLE inside the store's own database file
    PRAGMA = "pragma"  # PRAGMA user_version inside the store's own database file
    REPOINT = "repoint"  # UPDATE this event's effect rows to another subject
    HEADER_FLAG = (
        "header_flag"  # PRAGMA default_cache_size: a header field no store commit rewrites
    )
    TAIL_BYTES = "tail_bytes"  # bytes appended past the database file's last page
    HOME_CHMOD = "home_chmod"  # the permission bits of the world's HOME directory
    HOME_RMDIR = "home_rmdir"  # the world's HOME directory, removed
    # A world-detection attempt: return early if the world looks like a census or a sweep.
    DETECT = "detect"


STORE_OPS = (Op.GUARD, Op.EFFECT, Op.MARK, Op.ATOMIC, Op.TRY_MARK, Op.RETRY_EFFECT)
HAZARD_OPS = (
    Op.RAW_FILE,
    Op.PARENT_FILE,
    Op.HOME_FILE,
    Op.TMP_FILE,
    Op.DELETE_FILE,
    Op.RAW_SQL,
    Op.TABLE,
    Op.PRAGMA,
    Op.REPOINT,
    Op.HEADER_FLAG,
    Op.TAIL_BYTES,
    Op.HOME_CHMOD,
    Op.HOME_RMDIR,
    Op.DETECT,
)
_SQL_OPS = frozenset({Op.RAW_SQL, Op.TABLE, Op.PRAGMA, Op.REPOINT, Op.HEADER_FLAG})
_OS_OPS = frozenset(
    {Op.PARENT_FILE, Op.HOME_FILE, Op.DELETE_FILE, Op.HOME_CHMOD, Op.HOME_RMDIR, Op.DETECT}
)
# Writes the world scan sees: a file (the one beside the database can be tidied away) or a
# change to a directory the kernel pinned (which cannot).
_FILE_OPS = frozenset({Op.RAW_FILE, Op.PARENT_FILE, Op.HOME_FILE, Op.TMP_FILE})
_WORLD_OPS = frozenset({Op.HOME_CHMOD, Op.HOME_RMDIR})
# Words a leaky engine might put in a world's path or environment. Every world is named by an
# opaque id, so this condition is always false; if it ever becomes true the checker and the
# oracle disagree, which is the point.
_WORLD_WORDS = ("census", "sweep", "control", "kill", "hunt", "confirm", "boundary", "world-")


@dataclass(frozen=True)
class Vocabulary:
    """How one scenario's store and event spell the grammar."""

    scenario_id: str
    base_ref: str
    handler_file: str
    function: str
    guard: str
    effect: str
    mark: str
    atomic: str
    effect_arguments: str
    raw_effect_sql: tuple[tuple[str, str], ...]  # (statement, parameters) pairs
    repoint_sql: tuple[str, str]


CREDIT = Vocabulary(
    scenario_id="sqlite-credit-v1",
    base_ref="fixture:sqlite-credit-v1/buggy",
    handler_file="app/credits.py",
    function="apply_credit",
    guard="processed",
    effect="credit",
    mark="mark_processed",
    atomic="credit_and_mark",
    effect_arguments='event["account_id"], event["event_id"], event["amount_cents"]',
    raw_effect_sql=(
        (
            "UPDATE accounts SET balance_cents = balance_cents + ? WHERE account_id = ?",
            '(event["amount_cents"], event["account_id"])',
        ),
        (
            "INSERT INTO credit_ledger(event_id, account_id, amount_cents) VALUES (?, ?, ?)",
            '(event["event_id"], event["account_id"], event["amount_cents"])',
        ),
    ),
    repoint_sql=(
        "UPDATE credit_ledger SET account_id = 'acct-other' WHERE event_id = ?",
        '(event["event_id"],)',
    ),
)
INVENTORY = Vocabulary(
    scenario_id="sqlite-inventory-v1",
    base_ref="fixture:sqlite-inventory-v1/buggy",
    handler_file="app/inventory.py",
    function="reserve_inventory",
    guard="reserved",
    effect="reserve",
    mark="mark_reserved",
    atomic="reserve_and_mark",
    effect_arguments='event["sku"], event["event_id"], event["quantity"]',
    raw_effect_sql=(
        (
            "UPDATE stock SET on_hand = on_hand - ? WHERE sku = ?",
            '(event["quantity"], event["sku"])',
        ),
        (
            "INSERT INTO reservations(event_id, sku, quantity) VALUES (?, ?, ?)",
            '(event["event_id"], event["sku"], event["quantity"])',
        ),
    ),
    repoint_sql=(
        "UPDATE reservations SET sku = 'other-sku' WHERE event_id = ?",
        '(event["event_id"],)',
    ),
)
VOCABULARIES = {CREDIT.scenario_id: CREDIT, INVENTORY.scenario_id: INVENTORY}


def vocabulary_for(scenario_id: str) -> Vocabulary:
    """The vocabulary of an audited scenario, or a ValueError naming the ones that exist."""
    scenario_for(scenario_id)  # the same refusal the kernel gives for an unknown id
    if scenario_id not in VOCABULARIES:
        raise ValueError(
            f"the generator has no grammar for {scenario_id!r}; known: {', '.join(VOCABULARIES)}"
        )
    return VOCABULARIES[scenario_id]


def _statements(v: Vocabulary) -> dict[Op, str]:
    """The Python of every op in this vocabulary, indented one level."""
    effect = f"store.{v.effect}({v.effect_arguments})"
    mark = f'store.{v.mark}(event["event_id"])'
    raw_sql = "".join(
        f"        connection.execute(\n            {statement!r},\n            {parameters},\n"
        "        )\n"
        for statement, parameters in v.raw_effect_sql
    )
    return {
        Op.GUARD: f'    if store.{v.guard}(event["event_id"]):\n        return\n',
        Op.EFFECT: f"    {effect}\n",
        Op.MARK: f"    {mark}\n",
        Op.ATOMIC: f"    store.{v.atomic}({v.effect_arguments})\n",
        Op.TRY_MARK: f"    try:\n        {mark}\n    except Exception:\n        pass\n",
        Op.RETRY_EFFECT: (
            "    for _attempt in range(3):\n"
            "        try:\n"
            f"            {effect}\n"
            "            break\n"
            "        except Exception:\n"
            "            continue\n"
        ),
        Op.RAW_FILE: (
            '    with open("side.txt", "a", encoding="utf-8") as side:\n'
            '        side.write("x\\n")\n'
        ),
        Op.PARENT_FILE: (
            '    with open(os.path.join("..", "side.txt"), "a", encoding="utf-8") as side:\n'
            '        side.write("x\\n")\n'
        ),
        Op.HOME_FILE: (
            '    with open(os.path.expanduser("~/side.txt"), "a", encoding="utf-8") as side:\n'
            '        side.write("x\\n")\n'
        ),
        Op.TMP_FILE: (
            '    with open(os.path.join(tempfile.gettempdir(), "side.txt"), "a", '
            'encoding="utf-8") as side:\n'
            '        side.write("x\\n")\n'
        ),
        Op.DELETE_FILE: '    if os.path.exists("side.txt"):\n        os.remove("side.txt")\n',
        Op.RAW_SQL: (
            "    with sqlite3.connect(store._database, isolation_level=None) as connection:\n"
            '        connection.execute("BEGIN IMMEDIATE")\n'
            f"{raw_sql}"
            "        connection.commit()\n"
        ),
        Op.TABLE: (
            "    with sqlite3.connect(store._database, isolation_level=None) as connection:\n"
            '        connection.execute("CREATE TABLE IF NOT EXISTS dedup(k TEXT PRIMARY KEY)")\n'
        ),
        Op.PRAGMA: (
            "    with sqlite3.connect(store._database, isolation_level=None) as connection:\n"
            '        connection.execute("PRAGMA user_version = 7")\n'
        ),
        Op.REPOINT: (
            "    with sqlite3.connect(store._database, isolation_level=None) as connection:\n"
            f"        connection.execute({v.repoint_sql[0]!r}, {v.repoint_sql[1]})\n"
        ),
        Op.HEADER_FLAG: (
            "    with sqlite3.connect(store._database, isolation_level=None) as connection:\n"
            '        connection.execute("PRAGMA default_cache_size = 7")\n'
        ),
        Op.TAIL_BYTES: (
            '    with open(store._database, "ab") as tail:\n        tail.write(b"\\x5a" * 16)\n'
        ),
        Op.HOME_CHMOD: '    os.chmod(os.path.expanduser("~"), 0o750)\n',
        Op.HOME_RMDIR: '    os.rmdir(os.path.expanduser("~"))\n',
        Op.DETECT: (
            "    here = os.getcwd() + os.path.abspath(__file__)\n"
            f"    if any(word in here for word in {_WORLD_WORDS!r}) or any(\n"
            '        name.startswith("NEMISIS_") for name in os.environ\n'
            "    ):\n"
            "        return\n"
        ),
    }


def render(ops: Sequence[Op], vocabulary: Vocabulary = CREDIT, *, helper: bool = False) -> str:
    """The handler module for one operation sequence.

    With ``helper`` the statements live in a module-private function the bound handler calls,
    which is the shape a reviewer writes when the handler grows.
    """
    header = '"""Generated by nemisis redteam; the ops are the whole story."""\n\n'
    imports = []
    if any(op in _OS_OPS for op in ops):
        imports.append("import os")
    if Op.TMP_FILE in ops:
        imports.append("import tempfile")
    if any(op in _SQL_OPS for op in ops):
        imports.append("import sqlite3")
    header += ("\n".join(imports) + "\n\n\n") if imports else "\n"
    statements = _statements(vocabulary)
    body = "".join(statements[op] for op in ops) or "    return\n"
    if helper:
        return (
            f"{header}def _deliver(store, event):\n{body}\n\n"
            f"def {vocabulary.function}(store, event):\n    _deliver(store, event)\n"
        )
    return f"{header}def {vocabulary.function}(store, event):\n{body}"


class Expected(StrEnum):
    PROVEN = CrashVerdict.FIX_PROVEN_FOR_THIS_CAPSULE.value
    STILL_REPRODUCES = CrashVerdict.PATCH_FAILED_STILL_REPRODUCES.value
    INVARIANT_BROKEN = CrashVerdict.PATCH_FAILED_INVARIANT_BROKEN.value
    INCOMPLETE = CrashVerdict.EVIDENCE_INCOMPLETE.value


@dataclass
class _World:
    """Durable state for one event as the probe sees it, plus what hid from it.

    Every effect moves the subject by the scenario's delta and writes one effect row, so the
    effect count alone determines the four numbers the kernel's rule reads. ``files`` are the
    places a file was written (a later delete tidies away only the one beside the database);
    ``raw_db`` is a write inside the database file that the next probe cannot attribute;
    ``raw_seen`` is set at the moments the kernel looks: the probe after every commit reads the
    database, the scan after a kill and after a completed delivery reads the world as well.
    """

    effects: int = 0
    marker: int = 0
    files: set[str] = field(default_factory=set)
    raw_db: bool = False
    raw_seen: bool = False
    trace: list[int] = field(default_factory=list)  # effect count after each commit

    def probe(self) -> None:
        if self.raw_db:
            self.raw_seen = True

    def scan(self) -> None:
        if self.files or self.raw_db:
            self.raw_seen = True


class _Stop(Exception):
    """The delivery ended: by returning, by raising, or by the kill."""

    def __init__(self, kind: str) -> None:
        super().__init__(kind)
        self.kind = kind


def _deliver(world: _World, ops: Sequence[Op], *, kill_after_commit: int | None) -> str:
    """Run one delivery on the world. Returns 'done', 'error', or 'killed'.

    A commit is a kill point; the k-th commit ends the delivery when ``kill_after_commit == k``.
    A second marker for the same event raises (PRIMARY KEY), which the real worker reports as an
    error unless the handler swallows it. The atomic call after a marker is a silent no-op with
    no commit. The controller probes the database after every commit, so a write inside the
    file is seen at the next commit; a file in the world is seen at the next scan, which is
    after a kill or after a completed delivery.
    """
    commits = 0
    world.trace = []

    def commit() -> None:
        nonlocal commits
        commits += 1
        world.trace.append(world.effects)
        world.probe()
        if kill_after_commit is not None and commits == kill_after_commit:
            raise _Stop("killed")

    try:
        for op in ops:
            if op is Op.GUARD:
                if world.marker:
                    return "done"
            elif op is Op.EFFECT or op is Op.RETRY_EFFECT:
                world.effects += 1
                commit()
            elif op is Op.MARK:
                if world.marker:
                    return "error"
                world.marker = 1
                commit()
            elif op is Op.TRY_MARK:
                if not world.marker:
                    world.marker = 1
                    commit()
            elif op is Op.ATOMIC:
                if world.marker:
                    continue
                world.effects += 1
                world.marker = 1
                commit()
            elif op in _FILE_OPS or op in _WORLD_OPS:
                world.files.add(op.value)
            elif op is Op.DELETE_FILE:
                world.files.discard(Op.RAW_FILE.value)
            elif op is Op.RAW_SQL:
                world.effects += 1
                world.raw_db = True
            elif op in {Op.TABLE, Op.PRAGMA, Op.HEADER_FLAG, Op.TAIL_BYTES}:
                world.raw_db = True
            elif op is Op.REPOINT:
                if world.effects:
                    world.raw_db = True
            elif op is Op.DETECT:
                continue
    except _Stop as stop:
        return stop.kind
    return "done"


def _finish(world: _World, outcome: str) -> str:
    """The kernel scans the world after a kill and after a completed delivery, never after an
    error (the run has already stopped without a verdict)."""
    if outcome in {"killed", "done"}:
        world.scan()
    return outcome


def _classify(world: _World) -> str:
    if world.effects == 2:
        return "DUPLICATE_EFFECT"
    if (world.effects, world.marker) == (1, 1):
        return "EXACTLY_ONCE"
    return "INVARIANT_FAILED"


def _boundary_commit(ops: Sequence[Op]) -> int | None:
    """The first store commit at which one effect is durable (the capsule's kill point)."""
    world = _World()
    _deliver(world, ops, kill_after_commit=None)
    for index, effects in enumerate(world.trace, start=1):
        if effects == 1:
            return index
    return None


def oracle(ops: Sequence[Op]) -> tuple[Expected, str]:
    """What the checker must say about this operation sequence, from the sequence alone.

    The simulation runs exactly the worlds the engine runs, in the engine's order: five boundary
    worlds (kill at the effect commit, redeliver), then, only if those end exactly once, a census
    (two deliveries, no kill) and one sweep world per commit of the first delivery. A raw write
    forfeits the verdict only in a world that actually executes it and only if the kernel looks
    while it is there: dead code after a guard is not a write, and a file removed before the
    next scan was never seen. A world whose redelivery raises is incomplete, and one incomplete
    sweep world makes the sweep incomplete unless the census already decided.
    """
    boundary = _boundary_commit(ops)
    if boundary is None:
        world = _World()
        _finish(world, _deliver(world, ops, kill_after_commit=None))
        if world.raw_seen:
            return Expected.INCOMPLETE, "a write around the store forfeits the verdict"
        return Expected.INCOMPLETE, "the durable effect checkpoint is never reached on a fresh seed"
    world = _World()
    assert _finish(world, _deliver(world, ops, kill_after_commit=boundary)) == "killed"
    redelivery = _finish(world, _deliver(world, ops, kill_after_commit=None))
    if world.raw_seen:
        return Expected.INCOMPLETE, "a write around the store forfeits the verdict"
    if redelivery != "done":
        return Expected.INCOMPLETE, "the redelivery after the boundary kill raised"
    observation = _classify(world)
    if observation == "DUPLICATE_EFFECT":
        return Expected.STILL_REPRODUCES, "the boundary worlds duplicate"
    if observation == "INVARIANT_FAILED":
        return Expected.INVARIANT_BROKEN, "the boundary worlds break the invariant"
    # Census: two deliveries, no kill; one delivery must already be exactly once.
    census = _World()
    first_run = _finish(census, _deliver(census, ops, kill_after_commit=None))
    if census.raw_seen:
        return Expected.INCOMPLETE, "a write around the store forfeits the verdict"
    if first_run != "done":
        return Expected.INCOMPLETE, "the first no-kill delivery raised"
    first = _classify(census)
    commit_count = len(census.trace)
    second_run = _finish(census, _deliver(census, ops, kill_after_commit=None))
    if census.raw_seen:
        return Expected.INCOMPLETE, "a write around the store forfeits the verdict"
    if second_run != "done":
        return Expected.INCOMPLETE, "the no-kill redelivery raised"
    final = _classify(census)
    if final == "DUPLICATE_EFFECT":
        return Expected.STILL_REPRODUCES, "the no-kill census duplicates"
    if final == "INVARIANT_FAILED" or first != "EXACTLY_ONCE":
        return Expected.INVARIANT_BROKEN, "the no-kill census is wrong before any crash"
    # Sweep: kill once after each commit of the first delivery, then redeliver; every world must
    # complete before any kill point may decide.
    seen: list[str] = []
    for point in range(1, commit_count + 1):
        world = _World()
        if _finish(world, _deliver(world, ops, kill_after_commit=point)) != "killed":
            return Expected.INCOMPLETE, f"the sweep could not reach commit {point}"
        outcome = _finish(world, _deliver(world, ops, kill_after_commit=None))
        if world.raw_seen:
            return Expected.INCOMPLETE, "a write around the store forfeits the verdict"
        if outcome != "done":
            return Expected.INCOMPLETE, f"the redelivery after commit {point} raised"
        seen.append(_classify(world))
    if "DUPLICATE_EFFECT" in seen:
        return Expected.STILL_REPRODUCES, "a sweep kill point duplicates"
    if "INVARIANT_FAILED" in seen:
        return Expected.INVARIANT_BROKEN, "a sweep kill point breaks the invariant"
    return Expected.PROVEN, "every kill point ends exactly once"


@dataclass(frozen=True)
class Shape:
    """One generated handler: its operation sequence and whether it goes through a helper."""

    ops: tuple[Op, ...]
    helper: bool = False


def generate(cases: int, seed: int) -> list[Shape]:
    """Distinct shapes from a fixed seed; the same seed always yields the same list.

    Every shape is one to four store calls; a third of them carry one hazard (a write around
    the store or a world-detection attempt) at a random position, a few carry two, and a
    quarter are rendered through a helper function.
    """
    rng = random.Random(seed)
    store_weights = [3, 5, 3, 5, 1, 1]
    seen: set[Shape] = set()
    out: list[Shape] = []
    attempts = 0
    while len(out) < cases and attempts < cases * 200:
        attempts += 1
        length = rng.choice([1, 2, 2, 3, 3, 4])
        ops = rng.choices(STORE_OPS, weights=store_weights, k=length)
        hazards = rng.choices([0, 1, 2], weights=[12, 7, 1], k=1)[0]
        for _ in range(hazards):
            ops.insert(rng.randint(0, len(ops)), rng.choice(HAZARD_OPS))
        shape = Shape(tuple(ops), helper=rng.random() < 0.25)
        if shape in seen:
            continue
        seen.add(shape)
        out.append(shape)
    return out


@dataclass(frozen=True)
class Case:
    index: int
    ops: tuple[Op, ...]
    helper: bool
    expected: Expected
    reason: str
    verdict: str
    summary: str

    @property
    def agrees(self) -> bool:
        return self.verdict == self.expected.value


def run(cases: int, seed: int, out: Path, scenario_id: str = CREDIT.scenario_id) -> list[Case]:
    """Render, run, and compare every generated case; artifacts land under ``out``."""
    vocabulary = vocabulary_for(scenario_id)
    results: list[Case] = []
    # CrashCheck refuses symlinked evidence parents (macOS's /tmp -> /private/tmp); resolve first.
    out = out.resolve()
    previous = os.environ.get("NEMISIS_ARTIFACT_ROOT")
    for index, shape in enumerate(generate(cases, seed), start=1):
        expected, reason = oracle(shape.ops)
        tree = out / f"case-{index:03d}"
        handler = tree / vocabulary.handler_file
        handler.parent.mkdir(parents=True, exist_ok=False)
        (handler.parent / "__init__.py").write_text('"""generated"""\n', encoding="utf-8")
        handler.write_text(render(shape.ops, vocabulary, helper=shape.helper), encoding="utf-8")
        os.environ["NEMISIS_ARTIFACT_ROOT"] = str(out / f"artifacts-{index:03d}")
        try:
            result = check(vocabulary.base_ref, tree, scenario_id, mode="local")
            verdict, summary = result.verdict.value, result.summary
        except Exception as error:  # a crash of the checker is itself a disagreement
            verdict, summary = f"ERROR:{type(error).__name__}", str(error)[:500]
        finally:
            if previous is None:
                os.environ.pop("NEMISIS_ARTIFACT_ROOT", None)
            else:
                os.environ["NEMISIS_ARTIFACT_ROOT"] = previous
        results.append(Case(index, shape.ops, shape.helper, expected, reason, verdict, summary))
    return results


__all__ = [
    "CREDIT",
    "HAZARD_OPS",
    "INVENTORY",
    "STORE_OPS",
    "VOCABULARIES",
    "Case",
    "Expected",
    "Op",
    "Shape",
    "Vocabulary",
    "generate",
    "oracle",
    "render",
    "run",
    "vocabulary_for",
]
