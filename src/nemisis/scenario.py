"""The scenario seam: everything CrashCheck knows about one bug shape, in one object.

The kernel (hunt, kill, replay, sweep, attribution, verdict) is written once. What a scenario
supplies is the catalog identity, the SQLite schema and seed, the trusted store the handler is
handed, the durable-state probe, the deltas each store operation may make, the checkpoint
predicate, and the words a human reads. ``sqlite-credit-v1`` is the first instance; a second
scenario is a second instance of this dataclass, not a second copy of the kernel.
"""

from __future__ import annotations

import json
import socket
import sqlite3
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from nemisis.crash_models import CrashVerdict, FaultBoundary, StateSnapshot
from nemisis.hashing import canonical_json

MAX_MESSAGE_BYTES = 8_192

Event = dict[str, str | int]
# Every row of every seeded table, in canonical JSON-able form: {"table": [[col, ...], ...]}.
# The kernel wraps it with the schema and header and attributes the whole database, so a table,
# a pragma, or a row the scenario did not seed and no store operation predicts is a write around
# the store.
Tables = dict[str, list[list[object]]]


@dataclass(frozen=True)
class Scenario:
    """One audited bug shape. Every field is read by the kernel; none is read by a handler."""

    scenario_id: str
    adapter_id: str
    fault_intent_id: str
    probe_id: str
    predicate_id: str
    event_fixture_id: str
    target: str
    # Packaged resources: ``fixtures/<fixture_package>/{issue.md,event.json,contract.json}`` plus
    # ``common/…`` files shared by every tree and ``trees/<variant>/<handler_relative>``.
    fixture_package: str
    handler_relative: str
    common_files: tuple[tuple[str, str], ...]
    hero_variants: tuple[str, ...]
    zoo_variants: tuple[str, ...]
    tree_digests: Mapping[str, str]
    issue_digest: str
    event_digest: str
    event_resource_digest: str
    audited_contract_digest: str
    contract_resource_digest: str
    # Artifacts.
    repro_dir: str
    # The database: how to seed it, how to read every row of it, how to project the four numbers
    # a receipt carries from those rows, and what each store operation does to them.
    schema: str
    seed_identity: Callable[[Event], dict[str, object]]
    seed: Callable[[sqlite3.Connection, Event], None]
    tables: Callable[[sqlite3.Connection], Tables]
    snapshot: Callable[[Tables, Event], StateSnapshot]
    apply: Callable[[Tables, str, Event], Tables]
    store_operations: tuple[str, ...]
    # The store the handler is handed.
    store_class: type[Any]
    store_remedy: str
    store_api_fallback: str
    # The event and the rule. ``effect_delta`` is the signed change one delivery makes to the
    # subject; ``initial_total`` is the seeded subject total; ``scalar_name`` is the event field a
    # contract proposal must reproduce, within ``scalar_bounds``.
    normalize_event: Callable[[object], Event]
    effect_delta: Callable[[Event], int]
    initial_total: Callable[[Event], int]
    checkpoint_reached: Callable[[StateSnapshot, Event, FaultBoundary], bool]
    scalar_name: str
    scalar_bounds: tuple[int, int]
    # Words. ``subject_noun`` names the quantity ("balance", "stock"); ``effect_noun`` names one
    # delivery's durable effect ("credit", "reservation"); ``effect_verb`` is its third person.
    subject_noun: str
    effect_noun: str
    effect_verb: str
    others_noun: str
    format_subject: Callable[[int], str]
    describe_final: Callable[[StateSnapshot, Event], str]
    verdict_summary: Callable[[CrashVerdict, Event], str]

    @property
    def buggy_ref(self) -> str:
        return f"fixture:{self.scenario_id}/{self.hero_variants[0]}"

    def ref(self, variant: str) -> str:
        return f"fixture:{self.scenario_id}/{variant}"

    @property
    def variants(self) -> tuple[str, ...]:
        return (*self.hero_variants, *self.zoo_variants)


class StoreBase:
    """What every trusted store shares: exact-value checks and the commit report to the controller.

    A subclass adds the SQL. Each committing method must call ``_pause(operation)`` right after its
    commit; the controller probes the database at that instant, attributes the change to the named
    operation, and may kill the worker before it replies.
    """

    def __init__(self, database: Path, channel: socket.socket, event: Event) -> None:
        self._database = database
        self._channel = channel
        # A private copy: the handler holds the same event dict and may mutate its own.
        self._event = {name: value for name, value in event.items()}
        self._sequence = 0

    def _require(self, **supplied: object) -> None:
        """Every supplied value must be the event's exact value and exact type.

        ``type(x) is type(expected)`` (not ``isinstance``, not ``==`` alone) so a ``str`` subclass
        with a lying ``__eq__``, an object with ``__conform__``, a ``bool``, or ``None`` cannot
        smuggle a different row or a NULL into the trusted store's own SQL.
        """
        for name, value in supplied.items():
            if name not in self._event:
                raise ValueError("handler attempted an event outside the accepted contract")
            expected = self._event[name]
            if type(value) is not type(expected) or value != expected:
                raise ValueError("handler attempted an event outside the accepted contract")

    def _pause(self, operation: str) -> None:
        self._sequence += 1
        worker_send(
            self._channel,
            {"operation": operation, "sequence": self._sequence, "type": "commit"},
        )
        message = worker_receive(self._channel)
        if message != {"type": "continue"}:
            raise RuntimeError("controller returned an invalid commit acknowledgement")


def connect(path: Path) -> sqlite3.Connection:
    """The store's own write connection: WAL and synchronous=FULL, autocommit off by statement."""
    connection = sqlite3.connect(path, timeout=5, isolation_level=None)
    if connection.execute("PRAGMA journal_mode=WAL").fetchone() != ("wal",):
        connection.close()
        raise sqlite3.OperationalError("worker could not enable WAL")
    connection.execute("PRAGMA synchronous=FULL")
    return connection


def worker_send(channel: socket.socket, value: Mapping[str, object]) -> None:
    channel.sendall(canonical_json(value) + b"\n")


def worker_receive(channel: socket.socket) -> dict[str, object]:
    data = bytearray()
    while not data.endswith(b"\n"):
        chunk = channel.recv(min(1024, MAX_MESSAGE_BYTES + 1 - len(data)))
        if not chunk or len(data) + len(chunk) > MAX_MESSAGE_BYTES:
            raise RuntimeError("controller IPC closed or overflowed")
        data.extend(chunk)
    value = json.loads(data)
    if not isinstance(value, dict):
        raise RuntimeError("controller IPC was not a JSON object")
    return value


__all__ = [
    "MAX_MESSAGE_BYTES",
    "Event",
    "Scenario",
    "StoreBase",
    "Tables",
    "connect",
    "worker_receive",
    "worker_send",
]
