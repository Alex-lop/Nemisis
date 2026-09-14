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


class WroteAroundTheStore(RuntimeError):
    """SQL was committed to the store's database around the store's methods."""


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
        # One connection for the worker's whole life, closed by the worker only after the
        # controller has read the database and released it. Closing the last connection
        # checkpoints the WAL, and a checkpoint truncates the file to its page count; when a
        # per-call connection was closed was decided by the garbage collector, which erased bytes
        # a handler appended past the last page before the controller looked (the nightly red
        # team, 2026-09-08). Now the close is a protocol step, after the read.
        self._connection = connect(database)
        # SQLite's data_version changes only when ANOTHER connection commits; total_changes counts
        # the rows THIS connection changed. Together they say whether any SQL ran around the
        # store's methods, through any connection, whatever bytes it left: a row inserted and
        # deleted again leaves its bytes in the page's free space and no trace in any row.
        self._data_version = self._read_data_version()
        self._changes = self._connection.total_changes

    def _read_data_version(self) -> int:
        return int(self._connection.execute("PRAGMA data_version").fetchone()[0])

    def audit(self) -> None:
        """Refuse the delivery if SQL was committed around the store's methods.

        Both checks run before the worker reports done. Between store calls they are split so
        the controller's own probe, which names what changed, speaks first: statements on the
        store's connection are noticed before the next method acts (nothing else can name
        them), and another connection's commit is noticed in ``_pause`` once the controller has
        accepted this method's commit (a table or a row it left is already named by the probe;
        bytes in a page's free space are not, and this is what names them).
        """
        self._audit_own_connection()
        self._audit_other_connections()

    def _audit_own_connection(self) -> None:
        if self._connection.total_changes != self._changes:
            raise WroteAroundTheStore(
                "statements ran on the store's connection outside its methods"
            )
        # A TEMP trigger or table on the store's connection runs inside the store's own
        # transaction and shows in no probe; the stores create none.
        if self._connection.execute("SELECT count(*) FROM sqlite_temp_master").fetchone()[0]:
            raise WroteAroundTheStore(
                "a temporary schema object was created on the store's connection"
            )

    def _audit_other_connections(self) -> None:
        if self._read_data_version() != self._data_version:
            raise WroteAroundTheStore("another connection committed to the store's database")

    def _settle(self) -> None:
        """Record the store's own changes after one of its methods, so they are not foreign."""
        self._changes = self._connection.total_changes

    def close(self) -> None:
        """Checkpoint and close the store's connection; the worker calls this after the release.

        The checkpoint is explicit so the state after the exit does not depend on whether this
        was the last connection: a handler that opened one of its own and let it fall out of scope
        would otherwise leave the log full and the file behind the image, and be refused for a
        write it never made. A connection the handler left open with a transaction or an
        unexhausted cursor still keeps this checkpoint from completing, and the read after the
        exit says so.
        """
        self._connection.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
        self._connection.close()

    def _require(self, **supplied: object) -> None:
        """Every supplied value must be the event's exact value and exact type, and nothing may
        have been committed around the store since it last spoke.

        ``type(x) is type(expected)`` (not ``isinstance``, not ``==`` alone) so a ``str`` subclass
        with a lying ``__eq__``, an object with ``__conform__``, a ``bool``, or ``None`` cannot
        smuggle a different row or a NULL into the trusted store's own SQL.
        """
        self._audit_own_connection()
        for name, value in supplied.items():
            if name not in self._event:
                raise ValueError("handler attempted an event outside the accepted contract")
            expected = self._event[name]
            if type(value) is not type(expected) or value != expected:
                raise ValueError("handler attempted an event outside the accepted contract")

    def _pause(self, operation: str) -> None:
        self._settle()
        self._sequence += 1
        worker_send(
            self._channel,
            {"operation": operation, "sequence": self._sequence, "type": "commit"},
        )
        message = worker_receive(self._channel)
        if message != {"type": "continue"}:
            raise RuntimeError("controller returned an invalid commit acknowledgement")
        self._audit_other_connections()


def connect(path: Path) -> sqlite3.Connection:
    """The store's own write connection: WAL and synchronous=FULL, autocommit off by statement."""
    connection = sqlite3.connect(path, timeout=5, isolation_level=None)
    if connection.execute("PRAGMA journal_mode=WAL").fetchone() != ("wal",):
        connection.close()
        raise sqlite3.OperationalError("worker could not enable WAL")
    connection.execute("PRAGMA synchronous=FULL")
    # No automatic checkpoint: every store commit lives in the WAL for the life of the worker,
    # so the main database file is byte-identical to the seed for the whole delivery and the
    # controller pins it whole (a flag in the header's change counter, which a checkpoint would
    # rewrite and the probe used to mask, is caught at the next commit). The store's close, after
    # the controller's release, is the only checkpoint the store runs; one a handler runs itself
    # changes the main file and is refused.
    connection.execute("PRAGMA wal_autocheckpoint=0")
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
    "WroteAroundTheStore",
    "Event",
    "Scenario",
    "StoreBase",
    "Tables",
    "connect",
    "worker_receive",
    "worker_send",
]
