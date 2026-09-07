# Mutation ledger, 2026-09-07

The checker of the checker: each operator of the kernel's refusals was flipped one at a time and the suite's fast-to-slow selection was run with `-x`. A killed mutant names the first test that failed; a surviving mutant is either provably equivalent (the change cannot move a verdict) or a hole (a refusal branch no test exercises). This run was made against the engine of the night's first branch, before the third hostile round's fix, which is why the surviving `_xattrs` mutants and the surviving header-pragma drops agree with what that review found by hand.

- engine code digest: `228430389fa7292570b4df0772ed0fdb9ee915a6e89fe49b7dcf9aa3ac588831`
- started: 2026-09-07T02:11:23-0400; wall clock: 6541 s, on a laptop that was also running two other test suites
- tests per mutant, in order: `tests/test_scenario.py`, `tests/test_crash_models.py`, `tests/test_sqlite_runner.py`, `tests/test_inventory_scenario.py`, `tests/test_crashcheck.py`, `tests/test_verdict_paths.py`
- mutants enumerated: 222; run: 222; killed: 179; survived: 43; timed out: 0
- survivors: 10 equivalent, 33 holes, 0 unclassified

Regenerate with:

```bash
uv run python tools/mutants.py --target src/nemisis/sqlite_runner.py::_require_only_the_store_wrote --target src/nemisis/sqlite_runner.py::_SEED_MODE --target src/nemisis/sqlite_runner.py::_xattrs --target src/nemisis/sqlite_runner.py::_read_content --target src/nemisis/sqlite_runner.py::_HEADER_PRAGMAS --target src/nemisis/sqlite_runner.py::_require_unchanged --target src/nemisis/sqlite_runner.py::_kill_and_wait --target src/nemisis/sqlite_runner.py::_finish_replay --target src/nemisis/sqlite_runner.py::_attributed_probe --target src/nemisis/crash_models.py::classify_final --target src/nemisis/crash_models.py::classify_delivery --target src/nemisis/crash_models.py::AttemptReceipt.evidence_is_coherent --target src/nemisis/crashcheck.py::_schedule_split --tests tests/test_scenario.py tests/test_crash_models.py tests/test_sqlite_runner.py tests/test_inventory_scenario.py tests/test_crashcheck.py tests/test_verdict_paths.py --out /private/tmp/claude-501/-Users-alexlopez-Desktop-repos-Nemisis/0b344d89-f5c8-4964-a9a6-55f2e6c6c9ea/scratchpad/run/ledger.json
```

## Per target

### `src/nemisis/sqlite_runner.py::_require_only_the_store_wrote`

20 mutants: 13 killed, 7 survived, 0 timed out.

| line | mutation | status | killed by / why it survives | s |
| ---: | -------- | ------ | --------------------------- | --: |
| 623 | `{ root / "sandbox", root / "sandbox" / "cwd", root / "home", root /… -> ({root / 'sandb...` | killed | `test_buggy_fixture_duplicates_at_effect_commit` | 4 |
| 623 | `{ root / "sandbox", root / "sandbox" / "cwd", root / "home", root /… -> ({root / 'sandb...` | killed | `test_buggy_fixture_duplicates_at_effect_commit` | 2 |
| 623 | `{ root / "sandbox", root / "sandbox" / "cwd", root / "home", root /… -> ({root / 'sandb...` | killed | `test_buggy_fixture_duplicates_at_effect_commit` | 2 |
| 623 | `{ root / "sandbox", root / "sandbox" / "cwd", root / "home", root /… -> ({root / 'sandb...` | killed | `test_buggy_fixture_duplicates_at_effect_commit` | 2 |
| 623 | `{ root / "sandbox", root / "sandbox" / "cwd", root / "home", root /… -> ({root / 'sandb...` | killed | `test_buggy_fixture_duplicates_at_effect_commit` | 2 |
| 623 | `{ root / "sandbox", root / "sandbox" / "cwd", root / "home", root /… -> ({root / 'sandb...` | killed | `test_buggy_fixture_duplicates_at_effect_commit` | 2 |
| 623 | `{ root / "sandbox", root / "sandbox" / "cwd", root / "home", root /… -> ({root / 'sandb...` | killed | `test_buggy_fixture_duplicates_at_effect_commit` | 2 |
| 635 | `path not in expected -> (path in expected)` | killed | `test_buggy_fixture_duplicates_at_effect_commit` | 2 |
| 638 | `len(extra) > 5 -> (len(extra) >= 5)` | survived | **equivalent**: message truncation only (`extra[:5]`, the ellipsis); no verdict reads it | 182 |
| 638 | `5 -> (-5)` | survived | **equivalent**: message truncation only (`extra[:5]`, the ellipsis); no verdict reads it | 148 |
| 638 | `5 -> (-5)` | killed | `test_dedup_state_hidden_from_the_probes_forfeits_the_verdict[empty-dir` | 221 |
| 638 | `5 -> (4)` | survived | **equivalent**: message truncation only (`extra[:5]`, the ellipsis); no verdict reads it | 238 |
| 638 | `5 -> (4)` | survived | **equivalent**: message truncation only (`extra[:5]`, the ellipsis); no verdict reads it | 254 |
| 638 | `5 -> (6)` | survived | **equivalent**: message truncation only (`extra[:5]`, the ellipsis); no verdict reads it | 209 |
| 638 | `5 -> (6)` | survived | **equivalent**: message truncation only (`extra[:5]`, the ellipsis); no verdict reads it | 159 |
| 638 | `extra[:5] -> (extra)` | survived | **equivalent**: message truncation only (`extra[:5]`, the ellipsis); no verdict reads it | 154 |
| 639 | `raise _AttemptFailure( ExecutionStatus.UNSUPPORTED, f"the handler w… -> pass` | killed | `test_durable_files_beside_the_database_forfeit_the_verdict[audit-file-` | 52 |
| 646 | `stat.S_IMODE(status.st_mode) != _SEED_MODE or _xattrs(database) -> (stat.S_IMODE(status...` | killed | `test_side_channels_from_the_second_hostile_review_forfeit_the_verdict[` | 126 |
| 646 | `stat.S_IMODE(status.st_mode) != _SEED_MODE -> (stat.S_IMODE(status.st_mode) == _SEED_MODE)` | killed | `test_buggy_fixture_duplicates_at_effect_commit` | 2 |
| 647 | `raise _AttemptFailure( ExecutionStatus.UNSUPPORTED, "the handler ch… -> pass` | killed | `test_side_channels_from_the_second_hostile_review_forfeit_the_verdict[` | 130 |

### `src/nemisis/sqlite_runner.py::_SEED_MODE`

3 mutants: 2 killed, 1 survived, 0 timed out.

| line | mutation | status | killed by / why it survives | s |
| ---: | -------- | ------ | --------------------------- | --: |
| 654 | `0o600 -> (-384)` | killed | `test_seed_probe_and_checkpoint_predicate_describe_the_same_database` | 1 |
| 654 | `0o600 -> (383)` | killed | `test_seed_probe_and_checkpoint_predicate_describe_the_same_database` | 1 |
| 654 | `0o600 -> (385)` | survived | **equivalent**: the seed sets and the check compares the same constant; a consistent change is invisible by construction (the fixed engine records the observed mode instead) | 123 |

### `src/nemisis/sqlite_runner.py::_xattrs`

4 mutants: 1 killed, 3 survived, 0 timed out.

| line | mutation | status | killed by / why it survives | s |
| ---: | -------- | ------ | --------------------------- | --: |
| 659 | `listxattr is None -> (listxattr is not None)` | killed | `test_buggy_fixture_duplicates_at_effect_commit` | 2 |
| 660 | `return [] -> return None` | survived | **hole**: the xattr guard was inert on macOS (no `os.listxattr`), so every branch of it was dead; the third hostile review found the same channel; the fixed engine reads attributes through libc and pins `xattr-flag` | 127 |
| 662 | `return sorted(listxattr(path)) -> return None` | survived | **hole**: same: nothing exercised a listed attribute | 128 |
| 664 | `return [] -> return None` | survived | **hole**: same: the OSError branch | 123 |

### `src/nemisis/sqlite_runner.py::_read_content`

7 mutants: 5 killed, 2 survived, 0 timed out.

| line | mutation | status | killed by / why it survives | s |
| ---: | -------- | ------ | --------------------------- | --: |
| 817 | `0 -> (-1)` | survived | **equivalent**: `fetchone()[0]` on a one-tuple; index -1 is the same element | 124 |
| 817 | `0 -> (1)` | killed | `test_seed_probe_and_checkpoint_predicate_describe_the_same_database` | 1 |
| 824 | `raise _AttemptFailure( ExecutionStatus.PROBE_ERROR, f"read-only sta… -> pass` | survived | **hole**: a probe that fails with a sqlite3 error (a locked or corrupt file) has no test; the run would continue past a failed read | 125 |
| 827 | `return {"header": header, "schema": schema, "tables": tables} -> return None` | killed | `test_seed_probe_and_checkpoint_predicate_describe_the_same_database` | 1 |
| 827 | `{"header": header, "schema": schema, "tables": tables} -> ({'header': header, 'schema':...` | killed | `test_seed_probe_and_checkpoint_predicate_describe_the_same_database` | 1 |
| 827 | `{"header": header, "schema": schema, "tables": tables} -> ({'header': header, 'tables':...` | killed | `test_attributed_probe_accepts_only_the_delta_its_operation_explains` | 2 |
| 827 | `{"header": header, "schema": schema, "tables": tables} -> ({'schema': schema, 'tables':...` | killed | `test_attributed_probe_accepts_only_the_delta_its_operation_explains` | 1 |

### `src/nemisis/sqlite_runner.py::_HEADER_PRAGMAS`

8 mutants: 2 killed, 6 survived, 0 timed out.

| line | mutation | status | killed by / why it survives | s |
| ---: | -------- | ------ | --------------------------- | --: |
| 834 | `( "application_id", "auto_vacuum", "encoding", "freelist_count", "j… -> (('application_...` | survived | **hole**: dropping a pragma from the header read is caught only for `freelist_count` and `schema_version`; the fixed engine reads the raw header bytes, which cover every field, and pins `default_cache_size`, but a unit test per pragma is still owed | 123 |
| 834 | `( "application_id", "auto_vacuum", "encoding", "freelist_count", "j… -> (('application_...` | killed | `test_side_channels_from_the_second_hostile_review_forfeit_the_verdict[` | 117 |
| 834 | `( "application_id", "auto_vacuum", "encoding", "freelist_count", "j… -> (('application_...` | killed | `test_dedup_state_hidden_from_the_probes_forfeits_the_verdict[user-vers` | 99 |
| 834 | `( "application_id", "auto_vacuum", "encoding", "freelist_count", "j… -> (('application_...` | survived | **hole**: dropping a pragma from the header read is caught only for `freelist_count` and `schema_version`; the fixed engine reads the raw header bytes, which cover every field, and pins `default_cache_size`, but a unit test per pragma is still owed | 115 |
| 834 | `( "application_id", "auto_vacuum", "encoding", "freelist_count", "j… -> (('application_...` | survived | **hole**: dropping a pragma from the header read is caught only for `freelist_count` and `schema_version`; the fixed engine reads the raw header bytes, which cover every field, and pins `default_cache_size`, but a unit test per pragma is still owed | 122 |
| 834 | `( "application_id", "auto_vacuum", "encoding", "freelist_count", "j… -> (('application_...` | survived | **hole**: dropping a pragma from the header read is caught only for `freelist_count` and `schema_version`; the fixed engine reads the raw header bytes, which cover every field, and pins `default_cache_size`, but a unit test per pragma is still owed | 118 |
| 834 | `( "application_id", "auto_vacuum", "encoding", "freelist_count", "j… -> (('application_...` | survived | **hole**: dropping a pragma from the header read is caught only for `freelist_count` and `schema_version`; the fixed engine reads the raw header bytes, which cover every field, and pins `default_cache_size`, but a unit test per pragma is still owed | 114 |
| 834 | `( "application_id", "auto_vacuum", "encoding", "freelist_count", "j… -> (('auto_vacuum'...` | survived | **hole**: dropping a pragma from the header read is caught only for `freelist_count` and `schema_version`; the fixed engine reads the raw header bytes, which cover every field, and pins `default_cache_size`, but a unit test per pragma is still owed | 122 |

### `src/nemisis/sqlite_runner.py::_require_unchanged`

6 mutants: 5 killed, 1 survived, 0 timed out.

| line | mutation | status | killed by / why it survives | s |
| ---: | -------- | ------ | --------------------------- | --: |
| 902 | `sha256_json(observed.content) != sha256_json(ledger.content) -> (sha256_json(observed.c...` | killed | `test_buggy_fixture_duplicates_at_effect_commit` | 2 |
| 902 | `ledger.content -> (ledger.snapshot)` | killed | `test_buggy_fixture_duplicates_at_effect_commit` | 1 |
| 902 | `observed.content -> (observed.snapshot)` | killed | `test_buggy_fixture_duplicates_at_effect_commit` | 2 |
| 903 | `raise _AttemptFailure( ExecutionStatus.INTEGRITY_ERROR, f"{what}: {… -> pass` | survived | **hole**: the post-kill 'durable checkpoint changed after worker death' refusal has no test; a detached child writing after the kill is the shape | 124 |
| 908 | `observed.snapshot -> (observed.content)` | killed | `test_buggy_fixture_duplicates_at_effect_commit` | 2 |
| 908 | `return observed.snapshot -> return None` | killed | `test_buggy_fixture_duplicates_at_effect_commit` | 1 |

### `src/nemisis/sqlite_runner.py::_kill_and_wait`

5 mutants: 2 killed, 3 survived, 0 timed out.

| line | mutation | status | killed by / why it survives | s |
| ---: | -------- | ------ | --------------------------- | --: |
| 1091 | `raise _AttemptFailure(ExecutionStatus.KILL_ERROR, "process-group SI… -> pass` | survived | **hole**: a failed process-group SIGKILL has no test | 122 |
| 1095 | `raise _AttemptFailure(ExecutionStatus.WAIT_ERROR, "killed worker wa… -> pass` | survived | **hole**: a killed worker that is not reaped within the budget has no test | 122 |
| 1096 | `return_code != -signal.SIGKILL -> (return_code == -signal.SIGKILL)` | killed | `test_buggy_fixture_duplicates_at_effect_commit` | 2 |
| 1096 | `-signal.SIGKILL -> (signal.SIGKILL)` | killed | `test_buggy_fixture_duplicates_at_effect_commit` | 2 |
| 1097 | `raise _AttemptFailure(ExecutionStatus.WAIT_ERROR, "worker did not e… -> pass` | survived | **hole**: a worker that exited before the kill landed (not from SIGKILL) has no test; the receipt validator catches it one layer up as a ValidationError | 117 |

### `src/nemisis/sqlite_runner.py::_finish_replay`

19 mutants: 16 killed, 3 survived, 0 timed out.

| line | mutation | status | killed by / why it survives | s |
| ---: | -------- | ------ | --------------------------- | --: |
| 1117 | `kind == "commit" -> (kind != 'commit')` | killed | `test_buggy_fixture_duplicates_at_effect_commit` | 1 |
| 1122 | `kind == "error" -> (kind != 'error')` | killed | `test_buggy_fixture_duplicates_at_effect_commit` | 1 |
| 1123 | `raise _AttemptFailure( ExecutionStatus.REPLAY_ERROR, f"the handler … -> pass` | killed | `test_handler_that_never_credits_is_reported_with_its_no_crash_money` | 48 |
| 1128 | `{ "event_digest": capsule.event_digest, "execution_nonce": executio… -> ({'event_digest...` | killed | `test_buggy_fixture_duplicates_at_effect_commit` | 2 |
| 1128 | `{ "event_digest": capsule.event_digest, "execution_nonce": executio… -> ({'event_digest...` | killed | `test_buggy_fixture_duplicates_at_effect_commit` | 2 |
| 1128 | `{ "event_digest": capsule.event_digest, "execution_nonce": executio… -> ({'execution_no...` | killed | `test_buggy_fixture_duplicates_at_effect_commit` | 1 |
| 1133 | `message != expected -> (message == expected)` | killed | `test_buggy_fixture_duplicates_at_effect_commit` | 1 |
| 1134 | `raise _AttemptFailure(ExecutionStatus.PROTOCOL_ERROR, "replay compl… -> pass` | survived | **hole**: a malformed `done` message has no test | 108 |
| 1139 | `raise _AttemptFailure( ExecutionStatus.TIMEOUT, f"the {spawn.phase}… -> pass` | survived | **hole**: a worker that reports done and does not exit has no test; the message names it, nothing proves it | 109 |
| 1145 | `return_code != 0 -> (return_code == 0)` | killed | `test_buggy_fixture_duplicates_at_effect_commit` | 1 |
| 1145 | `0 -> (-1)` | killed | `test_buggy_fixture_duplicates_at_effect_commit` | 1 |
| 1145 | `0 -> (1)` | killed | `test_buggy_fixture_duplicates_at_effect_commit` | 1 |
| 1146 | `raise _AttemptFailure(ExecutionStatus.REPLAY_ERROR, "replay worker … -> pass` | survived | **hole**: a replay worker that exits nonzero after `done` has no test | 108 |
| 1148 | `sha256_json(observed.content) != sha256_json(ledger.content) -> (sha256_json(observed.c...` | killed | `test_buggy_fixture_duplicates_at_effect_commit` | 1 |
| 1148 | `ledger.content -> (ledger.snapshot)` | killed | `test_buggy_fixture_duplicates_at_effect_commit` | 1 |
| 1148 | `observed.content -> (observed.snapshot)` | killed | `test_buggy_fixture_duplicates_at_effect_commit` | 1 |
| 1149 | `raise _AttemptFailure( ExecutionStatus.INTEGRITY_ERROR, "the databa… -> pass` | killed | `test_writes_to_other_accounts_or_events_are_an_integrity_failure` | 50 |
| 1158 | `observed.snapshot -> (observed.content)` | killed | `test_buggy_fixture_duplicates_at_effect_commit` | 1 |
| 1158 | `return observed.snapshot -> return None` | killed | `test_buggy_fixture_duplicates_at_effect_commit` | 1 |

### `src/nemisis/sqlite_runner.py::_attributed_probe`

20 mutants: 20 killed, 0 survived, 0 timed out.

| line | mutation | status | killed by / why it survives | s |
| ---: | -------- | ------ | --------------------------- | --: |
| 1178 | `operation not in scenario.store_operations -> (operation in scenario.store_operations)` | killed | `test_attributed_probe_accepts_only_the_delta_its_operation_explains` | 1 |
| 1179 | `raise _AttemptFailure( ExecutionStatus.PROTOCOL_ERROR, f"worker rep… -> pass` | killed | `test_attributed_probe_accepts_only_the_delta_its_operation_explains` | 1 |
| 1183 | `ledger.content -> (ledger.snapshot)` | killed | `test_attributed_probe_accepts_only_the_delta_its_operation_explains` | 1 |
| 1184 | `{ "header": ledger.content["header"], "schema": ledger.content["sch… -> ({'header': led...` | killed | `test_attributed_probe_accepts_only_the_delta_its_operation_explains` | 1 |
| 1184 | `{ "header": ledger.content["header"], "schema": ledger.content["sch… -> ({'header': led...` | killed | `test_attributed_probe_accepts_only_the_delta_its_operation_explains` | 1 |
| 1184 | `{ "header": ledger.content["header"], "schema": ledger.content["sch… -> ({'schema': led...` | killed | `test_attributed_probe_accepts_only_the_delta_its_operation_explains` | 1 |
| 1185 | `ledger.content -> (ledger.snapshot)` | killed | `test_attributed_probe_accepts_only_the_delta_its_operation_explains` | 1 |
| 1186 | `ledger.content -> (ledger.snapshot)` | killed | `test_attributed_probe_accepts_only_the_delta_its_operation_explains` | 1 |
| 1190 | `sha256_json(observed.content) == sha256_json(predicted) -> (sha256_json(observed.conten...` | killed | `test_attributed_probe_accepts_only_the_delta_its_operation_explains` | 1 |
| 1190 | `observed.content -> (observed.snapshot)` | killed | `test_attributed_probe_accepts_only_the_delta_its_operation_explains` | 1 |
| 1191 | `return observed -> return None` | killed | `test_attributed_probe_accepts_only_the_delta_its_operation_explains` | 1 |
| 1192 | `scenario.snapshot -> (scenario.content)` | killed | `test_attributed_probe_accepts_only_the_delta_its_operation_explains` | 1 |
| 1193 | `ledger.snapshot -> (ledger.content)` | killed | `test_attributed_probe_accepts_only_the_delta_its_operation_explains` | 1 |
| 1193 | `observed.snapshot -> (observed.content)` | killed | `test_attributed_probe_accepts_only_the_delta_its_operation_explains` | 1 |
| 1193 | `ledger.snapshot, observed.snapshot -> ((ledger.snapshot,))` | killed | `test_attributed_probe_accepts_only_the_delta_its_operation_explains` | 1 |
| 1193 | `ledger.snapshot, observed.snapshot -> ((observed.snapshot,))` | killed | `test_attributed_probe_accepts_only_the_delta_its_operation_explains` | 1 |
| 1194 | `scenario.subject_noun, f"{scenario.effect_noun} rows" -> ((f'{scenario.effect_noun} row...` | killed | `test_attributed_probe_accepts_only_the_delta_its_operation_explains` | 1 |
| 1194 | `scenario.subject_noun, f"{scenario.effect_noun} rows" -> ((scenario.subject_noun,))` | killed | `test_attributed_probe_accepts_only_the_delta_its_operation_explains` | 1 |
| 1195 | `seen.digest != wanted.digest -> (seen.digest == wanted.digest)` | killed | `test_attributed_probe_accepts_only_the_delta_its_operation_explains` | 1 |
| 1213 | `raise _AttemptFailure( ExecutionStatus.INTEGRITY_ERROR, detail, int… -> pass` | killed | `test_attributed_probe_accepts_only_the_delta_its_operation_explains` | 1 |

### `src/nemisis/crash_models.py::classify_final`

31 mutants: 31 killed, 0 survived, 0 timed out.

| line | mutation | status | killed by / why it survives | s |
| ---: | -------- | ------ | --------------------------- | --: |
| 339 | `state[:3] == (effect_delta * 2, 2, effect_delta * 2) -> (state[:3] != (effect_delta * 2...` | killed | `test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 1 |
| 339 | `2 -> (-2)` | killed | `test_duplicate_observation_accepts_a_missing_marker` | 1 |
| 339 | `2 -> (-2)` | killed | `test_duplicate_observation_accepts_a_missing_marker` | 1 |
| 339 | `2 -> (-2)` | killed | `test_duplicate_observation_accepts_a_missing_marker` | 1 |
| 339 | `2 -> (1)` | killed | `test_duplicate_observation_accepts_a_missing_marker` | 1 |
| 339 | `2 -> (1)` | killed | `test_duplicate_observation_accepts_a_missing_marker` | 1 |
| 339 | `2 -> (1)` | killed | `test_duplicate_observation_accepts_a_missing_marker` | 1 |
| 339 | `2 -> (3)` | killed | `test_duplicate_observation_accepts_a_missing_marker` | 1 |
| 339 | `2 -> (3)` | killed | `test_duplicate_observation_accepts_a_missing_marker` | 1 |
| 339 | `2 -> (3)` | killed | `test_duplicate_observation_accepts_a_missing_marker` | 1 |
| 339 | `3 -> (-3)` | killed | `test_duplicate_observation_accepts_a_missing_marker` | 1 |
| 339 | `3 -> (2)` | killed | `test_duplicate_observation_accepts_a_missing_marker` | 1 |
| 339 | `3 -> (4)` | killed | `test_duplicate_observation_accepts_a_missing_marker` | 1 |
| 339 | `(effect_delta * 2, 2, effect_delta * 2) -> ((2, effect_delta * 2))` | killed | `test_duplicate_observation_accepts_a_missing_marker` | 1 |
| 339 | `(effect_delta * 2, 2, effect_delta * 2) -> ((effect_delta * 2, 2))` | killed | `test_duplicate_observation_accepts_a_missing_marker` | 1 |
| 339 | `(effect_delta * 2, 2, effect_delta * 2) -> ((effect_delta * 2, effect_delta * 2))` | killed | `test_duplicate_observation_accepts_a_missing_marker` | 1 |
| 339 | `state[:3] -> (state)` | killed | `test_duplicate_observation_accepts_a_missing_marker` | 1 |
| 340 | `return CrashObservation.DUPLICATE_EFFECT -> return None` | killed | `test_duplicate_observation_accepts_a_missing_marker` | 1 |
| 341 | `state == (effect_delta, 1, effect_delta, 1) -> (state != (effect_delta, 1, effect_delta...` | killed | `test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 1 |
| 341 | `1 -> (-1)` | killed | `test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 1 |
| 341 | `1 -> (-1)` | killed | `test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 1 |
| 341 | `1 -> (0)` | killed | `test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 1 |
| 341 | `1 -> (0)` | killed | `test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 1 |
| 341 | `1 -> (2)` | killed | `test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 1 |
| 341 | `1 -> (2)` | killed | `test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 1 |
| 341 | `(effect_delta, 1, effect_delta, 1) -> ((1, effect_delta, 1))` | killed | `test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 1 |
| 341 | `(effect_delta, 1, effect_delta, 1) -> ((effect_delta, 1, 1))` | killed | `test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 1 |
| 341 | `(effect_delta, 1, effect_delta, 1) -> ((effect_delta, 1, effect_delta))` | killed | `test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 1 |
| 341 | `(effect_delta, 1, effect_delta, 1) -> ((effect_delta, effect_delta, 1))` | killed | `test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 1 |
| 342 | `return CrashObservation.EXACTLY_ONCE -> return None` | killed | `test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 1 |
| 343 | `return CrashObservation.INVARIANT_FAILED -> return None` | killed | `test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 1 |

### `src/nemisis/crash_models.py::classify_delivery`

4 mutants: 4 killed, 0 survived, 0 timed out.

| line | mutation | status | killed by / why it survives | s |
| ---: | -------- | ------ | --------------------------- | --: |
| 318 | `after_redelivery is not CrashObservation.EXACTLY_ONCE -> (after_redelivery is CrashObse...` | killed | `test_guarded_leftover_credit_is_caught_by_the_census_and_blamed_on_no_` | 36 |
| 319 | `return after_redelivery -> return None` | killed | `test_guarded_leftover_credit_is_caught_by_the_census_and_blamed_on_no_` | 36 |
| 321 | `return ( CrashObservation.EXACTLY_ONCE if after_one is CrashObserva… -> return None` | killed | `test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 1 |
| 323 | `after_one is CrashObservation.EXACTLY_ONCE -> (after_one is not CrashObservation.EXACTL...` | killed | `test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 1 |

### `src/nemisis/crash_models.py::AttemptReceipt.evidence_is_coherent`

87 mutants: 70 killed, 17 survived, 0 timed out.

| line | mutation | status | killed by / why it survives | s |
| ---: | -------- | ------ | --------------------------- | --: |
| 425 | `self.ended_at < self.started_at -> (self.ended_at <= self.started_at)` | survived | **equivalent**: `<` to `<=` only differs when a spawn's start and end timestamps are equal to the nanosecond | 108 |
| 426 | `raise ValueError("attempt ended before it started") -> pass` | killed | `test_worker_and_attempt_timestamps_must_be_ordered` | 1 |
| 427 | `self.effect_delta == 0 -> (self.effect_delta != 0)` | killed | `test_completed_attempt_requires_exact_kill_replay_evidence[integrity_s` | 1 |
| 427 | `0 -> (-1)` | survived | **hole**: the attempt's nonzero-effect rule has no direct test (the capsule's has one, from the seam decision) | 108 |
| 427 | `0 -> (1)` | survived | **hole**: the attempt's nonzero-effect rule has no direct test (the capsule's has one, from the seam decision) | 108 |
| 428 | `raise ValueError("an attempt must expect a nonzero effect") -> pass` | survived | **hole**: same rule, the raise itself | 109 |
| 430 | `timestamps != sorted(timestamps) -> (timestamps == sorted(timestamps))` | killed | `test_completed_attempt_requires_exact_kill_replay_evidence[integrity_s` | 1 |
| 431 | `raise ValueError("attempt timeline is not ordered") -> pass` | survived | **hole**: an unordered attempt timeline is never constructed by a test | 108 |
| 432 | `len({spawn.spawn_index for spawn in self.spawns}) != len(self.spawn… -> (len({spawn.spa...` | killed | `test_completed_attempt_requires_exact_kill_replay_evidence[integrity_s` | 1 |
| 433 | `raise ValueError("worker spawn indices must be unique") -> pass` | survived | **hole**: duplicate spawn indices are never constructed by a test | 108 |
| 434 | `spawn.event_digest != self.event_digest -> (spawn.event_digest == self.event_digest)` | killed | `test_completed_attempt_requires_exact_kill_replay_evidence[integrity_s` | 1 |
| 435 | `raise ValueError("worker event digest differs from attempt event") -> pass` | survived | **hole**: a spawn whose event digest differs from the attempt's is never constructed by a test | 108 |
| 436 | `len(self.spawns) == 2 -> (len(self.spawns) != 2)` | killed | `test_replay_worker_requires_distinct_nonce_and_session[nonce]` | 1 |
| 436 | `2 -> (-2)` | killed | `test_replay_worker_requires_distinct_nonce_and_session[nonce]` | 1 |
| 436 | `2 -> (1)` | killed | `test_replay_worker_requires_distinct_nonce_and_session[nonce]` | 1 |
| 436 | `2 -> (3)` | killed | `test_replay_worker_requires_distinct_nonce_and_session[nonce]` | 1 |
| 437 | `len({spawn.worker_nonce for spawn in self.spawns}) != 2 -> (len({spawn.worker_nonce for...` | killed | `test_replay_worker_requires_distinct_nonce_and_session[nonce]` | 1 |
| 437 | `2 -> (-2)` | killed | `test_completed_attempt_requires_exact_kill_replay_evidence[integrity_s` | 1 |
| 437 | `2 -> (1)` | killed | `test_completed_attempt_requires_exact_kill_replay_evidence[integrity_s` | 1 |
| 437 | `2 -> (3)` | killed | `test_completed_attempt_requires_exact_kill_replay_evidence[integrity_s` | 1 |
| 438 | `raise ValueError("worker nonces must be distinct") -> pass` | killed | `test_replay_worker_requires_distinct_nonce_and_session[nonce]` | 1 |
| 439 | `len({spawn.ipc_session_id for spawn in self.spawns}) != 2 -> (len({spawn.ipc_session_id...` | killed | `test_completed_attempt_requires_exact_kill_replay_evidence[integrity_s` | 1 |
| 439 | `2 -> (-2)` | killed | `test_completed_attempt_requires_exact_kill_replay_evidence[integrity_s` | 1 |
| 439 | `2 -> (1)` | killed | `test_completed_attempt_requires_exact_kill_replay_evidence[integrity_s` | 1 |
| 439 | `2 -> (3)` | killed | `test_completed_attempt_requires_exact_kill_replay_evidence[integrity_s` | 1 |
| 440 | `raise ValueError("IPC sessions must be distinct") -> pass` | killed | `test_replay_worker_requires_distinct_nonce_and_session[session]` | 1 |
| 441 | `( self.pre_crash_snapshot, self.checkpoint_snapshot, self.post_kill… -> ((self.checkpoi...` | survived | **hole**: a completed attempt missing one of its four snapshots is never constructed by a test | 107 |
| 441 | `( self.pre_crash_snapshot, self.checkpoint_snapshot, self.post_kill… -> ((self.pre_cras...` | survived | **hole**: a completed attempt missing one of its four snapshots is never constructed by a test | 109 |
| 441 | `( self.pre_crash_snapshot, self.checkpoint_snapshot, self.post_kill… -> ((self.pre_cras...` | survived | **hole**: a completed attempt missing one of its four snapshots is never constructed by a test | 109 |
| 441 | `( self.pre_crash_snapshot, self.checkpoint_snapshot, self.post_kill… -> ((self.pre_cras...` | survived | **hole**: a completed attempt missing one of its four snapshots is never constructed by a test | 108 |
| 447 | `snapshot is not None -> (snapshot is None)` | killed | `test_raw_sql_and_look_alike_arguments_get_the_inventory_words` | 9 |
| 449 | `self.execution_status is ExecutionStatus.COMPLETED -> (self.execution_status is not Exe...` | killed | `test_completed_attempt_requires_exact_kill_replay_evidence[integrity_s` | 1 |
| 450 | `self.integrity_status is not IntegrityStatus.VALID -> (self.integrity_status is Integri...` | killed | `test_completed_attempt_requires_exact_kill_replay_evidence[integrity_s` | 1 |
| 451 | `raise ValueError("completed attempt requires valid integrity") -> pass` | killed | `test_completed_attempt_requires_exact_kill_replay_evidence[integrity_s` | 1 |
| 452 | `self.failure_detail is not None -> (self.failure_detail is None)` | killed | `test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 1 |
| 453 | `raise ValueError("completed attempt cannot have a failure detail") -> pass` | survived | **hole**: a completed attempt carrying a failure detail is never constructed by a test | 109 |
| 454 | `not ( self.checkpoint_reached and self.kill_signal == 9 and self.re… -> (self.checkpoin...` | killed | `test_completed_attempt_requires_exact_kill_replay_evidence[checkpoint_` | 1 |
| 455 | `self.checkpoint_reached and self.kill_signal == 9 and self.replay_a… -> (self.checkpoin...` | killed | `test_completed_attempt_requires_exact_kill_replay_evidence[checkpoint_` | 1 |
| 456 | `self.kill_signal == 9 -> (self.kill_signal != 9)` | killed | `test_completed_attempt_requires_exact_kill_replay_evidence[kill_signal` | 1 |
| 456 | `9 -> (-9)` | killed | `test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 1 |
| 456 | `9 -> (10)` | killed | `test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 1 |
| 456 | `9 -> (8)` | killed | `test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 1 |
| 458 | `self.pre_crash_snapshot is not None -> (self.pre_crash_snapshot is None)` | killed | `test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 1 |
| 459 | `self.checkpoint_snapshot is not None -> (self.checkpoint_snapshot is None)` | killed | `test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 1 |
| 460 | `self.post_kill_snapshot is not None -> (self.post_kill_snapshot is None)` | killed | `test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 1 |
| 461 | `self.final_snapshot is not None -> (self.final_snapshot is None)` | killed | `test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 1 |
| 462 | `len(self.spawns) == 2 -> (len(self.spawns) != 2)` | killed | `test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 1 |
| 462 | `2 -> (-2)` | killed | `test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 1 |
| 462 | `2 -> (1)` | killed | `test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 1 |
| 462 | `2 -> (3)` | killed | `test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 1 |
| 463 | `self.spawns[0].phase == "first" -> (self.spawns[0].phase != 'first')` | killed | `test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 1 |
| 463 | `0 -> (-1)` | killed | `test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 1 |
| 463 | `0 -> (1)` | killed | `test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 1 |
| 464 | `self.spawns[0].exit_code == -9 -> (self.spawns[0].exit_code != -9)` | killed | `test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 1 |
| 464 | `0 -> (-1)` | killed | `test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 1 |
| 464 | `0 -> (1)` | killed | `test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 1 |
| 464 | `9 -> (-9)` | killed | `test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 1 |
| 464 | `9 -> (10)` | killed | `test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 1 |
| 464 | `9 -> (8)` | killed | `test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 1 |
| 464 | `-9 -> (9)` | killed | `test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 1 |
| 465 | `self.spawns[1].phase == "replay" -> (self.spawns[1].phase != 'replay')` | killed | `test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 1 |
| 465 | `1 -> (-1)` | survived | **hole**: a first spawn with the wrong index is never constructed by a test | 108 |
| 465 | `1 -> (0)` | killed | `test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 1 |
| 465 | `1 -> (2)` | killed | `test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 1 |
| 466 | `self.spawns[1].exit_code == 0 -> (self.spawns[1].exit_code != 0)` | killed | `test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 1 |
| 466 | `0 -> (-1)` | killed | `test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 1 |
| 466 | `0 -> (1)` | killed | `test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 1 |
| 466 | `1 -> (-1)` | survived | **hole**: a second spawn with the wrong index is never constructed by a test | 110 |
| 466 | `1 -> (0)` | killed | `test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 1 |
| 466 | `1 -> (2)` | killed | `test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 1 |
| 468 | `raise ValueError("completed attempt lacks exact kill/replay evidenc… -> pass` | killed | `test_completed_attempt_requires_exact_kill_replay_evidence[checkpoint_` | 1 |
| 469 | `self.post_execution_tree_digest != self.tree_digest -> (self.post_execution_tree_digest...` | killed | `test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 1 |
| 470 | `raise ValueError( "completed attempt post-execution tree differs fr… -> pass` | killed | `test_completed_attempt_binds_tree_and_observation_to_snapshots` | 1 |
| 477 | `pre is not None and checkpoint is not None and post_kill is not None -> (pre is not Non...` | survived | **hole**: the all-snapshots-present rule weakened to any-present is never caught | 108 |
| 477 | `checkpoint is not None -> (checkpoint is None)` | killed | `test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 1 |
| 477 | `post_kill is not None -> (post_kill is None)` | killed | `test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 1 |
| 477 | `pre is not None -> (pre is None)` | killed | `test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 1 |
| 478 | `final is not None -> (final is None)` | killed | `test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 1 |
| 479 | `not _seeded(pre) -> (_seeded(pre))` | killed | `test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 1 |
| 480 | `raise ValueError("completed attempt pre-crash snapshot is not the s… -> pass` | survived | **hole**: a completed attempt whose pre-crash snapshot is not the seed is never constructed by a test | 108 |
| 481 | `post_kill.digest != checkpoint.digest -> (post_kill.digest == checkpoint.digest)` | killed | `test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 1 |
| 482 | `raise ValueError("completed attempt checkpoint changed after worker… -> pass` | killed | `test_completed_attempt_binds_tree_and_observation_to_snapshots` | 1 |
| 485 | `self.observation is not classify_final(final, self.effect_delta, pr… -> (self.observati...` | killed | `test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 1 |
| 486 | `raise ValueError("completed attempt observation contradicts its fin… -> pass` | killed | `test_duplicate_observation_accepts_a_missing_marker` | 1 |
| 487 | `self.failure_detail is None -> (self.failure_detail is not None)` | killed | `test_completed_result_cannot_contain_an_incomplete_attempt` | 1 |
| 488 | `raise ValueError("incomplete attempt requires a failure detail") -> pass` | survived | **hole**: an incomplete attempt without a failure detail is never constructed by a test | 108 |
| 489 | `return self -> return None` | killed | `test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 1 |

### `src/nemisis/crashcheck.py::_schedule_split`

8 mutants: 8 killed, 0 survived, 0 timed out.

| line | mutation | status | killed by / why it survives | s |
| ---: | -------- | ------ | --------------------------- | --: |
| 1374 | `sweep is None or sweep.census.execution_status is not ExecutionStat… -> (sweep is None ...` | killed | `test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 1 |
| 1374 | `sweep is None -> (sweep is not None)` | killed | `test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 1 |
| 1374 | `sweep.census.execution_status is not ExecutionStatus.COMPLETED -> (sweep.census.executi...` | killed | `test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 1 |
| 1379 | `attempt.execution_status is ExecutionStatus.COMPLETED and own != ce… -> (attempt.execut...` | killed | `test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 1 |
| 1379 | `attempt.execution_status is ExecutionStatus.COMPLETED -> (attempt.execution_status is n...` | killed | `test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 1 |
| 1379 | `own != census[: len(own)] -> (own == census[:len(own)])` | killed | `test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 1 |
| 1379 | `census[: len(own)] -> (census)` | killed | `test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 1 |
| 1380 | `return ( f"a kill world committed {', '.join(own) or 'nothing'} whe… -> return None` | killed | `test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 1 |

## What the holes say

Every hole is a refusal branch that fires only on a failure the suite never stages: a probe that cannot read, a kill that does not land, a worker that lingers or exits wrong, a receipt built by hand with contradictory fields. None of them is a false pass on a handler a judge could write; each is a test the kernel is owed, and the exit -9 confirmation in `_kill_and_wait` is the one that matters most, because it is the sentence the README rests on. They are the first work item of the next night.

