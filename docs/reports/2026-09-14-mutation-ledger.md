# Mutation ledger, 2026-09-14

The checker of the checker, rerun at the engine the nightly now judges: each operator of the kernel's refusals was flipped one at a time and the suite's fast-to-slow selection was run with `-x`. A killed mutant names the first test that failed; a surviving mutant is either provably equivalent (the change cannot move a verdict) or a hole (a refusal branch no test exercises). Every survivor was read at this engine: one reader per target function classified it, and one refuter per equivalence claim then tried to kill the mutant with a test. The rule: a mutant is equivalent when no verdict and no refusal can move (a type annotation; a sentence's wording, ellipsis, or trailing slash; a branch no read can reach), and a hole when a verdict or a refusal branch can move or a different cause is named, whether or not the test is easy to write. Six refuters killed wording-only mutants with tests that assert the refusal's sentence; by the rule those stay equivalent. Every hole names the test it is owed; the tests were written the same night, on the branch that follows this ledger, and are named here by their final names.

- engine code digest: `1afdb6ee88585074eaeda65c50223c18fb73c4b67710affb247ff8e55a51bb15` (at `230cc7c`)
- started: 2026-09-14T04:01:21-0400 on two parallel workers on a laptop also running the night's other suites; the machine killed the second worker at 113 of its 121 mutants (low memory), so its last target, `_xattrs`, was rerun alone from a clean tree (two earlier reruns of it were void, every mutant "killed" in a tenth of a second by no test because the shell had passed the test paths as one argument; they are discarded and the runner now calls such a run an error); the slowest worker took 5259 s
- tests per mutant, in order: `tests/test_scenario.py`, `tests/test_crash_models.py`, `tests/test_sqlite_runner.py`, `tests/test_inventory_scenario.py`, `tests/test_crashcheck.py`, `tests/test_verdict_paths.py`
- mutants enumerated: 288; run: 288; killed: 243; survived: 45; timed out: 0; errored: 0
- survivors: 24 equivalent, 21 holes, 0 unclassified

Regenerate with `tools/mutants.py` and the thirteen `--target`s below (the 2026-09-07 ledger has the one-line form), or the parallel script in the report.

## Per target

### `src/nemisis/sqlite_runner.py::_require_only_the_store_wrote`

28 mutants: 18 killed, 10 survived, 0 timed out.

| line | mutation | status | killed by / why it survives | s |
| ---: | -------- | ------ | --------------------------- | --: |
| 769 | `path.relative_to(root).as_posix() or "." -> (path.relative_to(root).as_posix() a` | killed | `tests/test_verdict_paths.py::test_dedup_state_hidden_from_the_probes_forfeits_the_verdict[empty-dir-import` | 119 |
| 769 | `return path.relative_to(root).as_posix() or "." -> return None` | killed | `tests/test_verdict_paths.py::test_durable_files_beside_the_database_forfeit_the_verdict[audit-file-def` | 59 |
| 771 | `{ database.with_name(f"{database.name}-wal"), database.with_name(f"… -> ({databa` | killed | `tests/test_sqlite_runner.py::test_buggy_fixture_duplicates_at_effect_commit` | 1 |
| 771 | `{ database.with_name(f"{database.name}-wal"), database.with_name(f"… -> ({databa` | killed | `tests/test_sqlite_runner.py::test_buggy_fixture_duplicates_at_effect_commit` | 1 |
| 776 | `not path.is_symlink() -> (path.is_symlink())` | killed | `tests/test_verdict_paths.py::test_dedup_state_hidden_from_the_probes_forfeits_the_verdict[empty-dir-import` | 104 |
| 776 | `path.is_dir() and not path.is_symlink() -> (path.is_dir() or not path.is_symlink` | survived | **equivalent**: The swapped condition only decides whether a name in the refusal sentence carries a trailing slash; wording only: the refusal, its status, and every verdict are unmoved (the ledger's rule since 2026-09-07; a refuter's test that asserts the sentence's ellipsis or slash is not a kill) | 195 |
| 778 | `path not in sidecars -> (path in sidecars)` | killed | `tests/test_sqlite_runner.py::test_buggy_fixture_duplicates_at_effect_commit` | 1 |
| 778 | `path not in world.expected -> (path in world.expected)` | killed | `tests/test_sqlite_runner.py::test_buggy_fixture_duplicates_at_effect_commit` | 1 |
| 778 | `path not in world.expected and path not in sidecars -> (path not in world.expect` | killed | `tests/test_sqlite_runner.py::test_buggy_fixture_duplicates_at_effect_commit` | 1 |
| 781 | `5 -> (-5)` | survived | **equivalent**: The ellipsis threshold, always true under the mutant; wording only: the refusal, its status, and every verdict are unmoved (the ledger's rule since 2026-09-07; a refuter's test that asserts the sentence's ellipsis or slash is not a kill) | 180 |
| 781 | `5 -> (-5)` | killed | `tests/test_verdict_paths.py::test_dedup_state_hidden_from_the_probes_forfeits_the_verdict[empty-dir-import` | 109 |
| 781 | `5 -> (4)` | survived | **equivalent**: Whether the sentence names four entries or five; wording only: the refusal, its status, and every verdict are unmoved (the ledger's rule since 2026-09-07; a refuter's test that asserts the sentence's ellipsis or slash is not a kill) | 179 |
| 781 | `5 -> (4)` | survived | **equivalent**: Whether the sentence names four entries or five; wording only: the refusal, its status, and every verdict are unmoved (the ledger's rule since 2026-09-07; a refuter's test that asserts the sentence's ellipsis or slash is not a kill) | 178 |
| 781 | `5 -> (6)` | survived | **equivalent**: Whether the sentence names six entries or five; wording only: the refusal, its status, and every verdict are unmoved (the ledger's rule since 2026-09-07; a refuter's test that asserts the sentence's ellipsis or slash is not a kill) | 175 |
| 781 | `5 -> (6)` | survived | **equivalent**: Whether the sentence names six entries or five; wording only: the refusal, its status, and every verdict are unmoved (the ledger's rule since 2026-09-07; a refuter's test that asserts the sentence's ellipsis or slash is not a kill) | 177 |
| 781 | `extra[:5] -> (extra)` | survived | **equivalent**: Names every extra entry instead of the first five; wording only: the refusal, its status, and every verdict are unmoved (the ledger's rule since 2026-09-07; a refuter's test that asserts the sentence's ellipsis or slash is not a kill) | 178 |
| 781 | `len(extra) > 5 -> (len(extra) >= 5)` | survived | **equivalent**: Decides only whether the sentence ends in an ellipsis; wording only: the refusal, its status, and every verdict are unmoved (the ledger's rule since 2026-09-07; a refuter's test that asserts the sentence's ellipsis or slash is not a kill) | 180 |
| 782 | `raise _AttemptFailure( ExecutionStatus.UNSUPPORTED, f"the handler w… -> pass` | killed | `tests/test_verdict_paths.py::test_durable_files_beside_the_database_forfeit_the_verdict[audit-file-def` | 51 |
| 789 | `(-len(item.parts), str(item)) -> ((-len(item.parts),))` | survived | **hole**: Without the name tie-break two equally deep entries in different bad states are visited in insertion order, so the refusal can name a mode bit on `sandbox` while a removed `home` goes unreported: a different cause, not a different wording. Owed: tests/test_sqlite_runner.py::test_the_world_audit_names_a_removed_home_before_a_touched_sandbox (written by a refuter tonight; removes `home` and chmods `sandbox`, asserts the removal is what is named) | 176 |
| 789 | `(-len(item.parts), str(item)) -> ((str(item),))` | killed | `tests/test_verdict_paths.py::test_side_channels_from_the_third_hostile_review_forfeit_the_verdict[home-rmdir-import` | 157 |
| 789 | `-len(item.parts) -> (len(item.parts))` | killed | `tests/test_verdict_paths.py::test_side_channels_from_the_third_hostile_review_forfeit_the_verdict[home-rmdir-import` | 152 |
| 792 | `expected.mtime_ns is not None -> (expected.mtime_ns is None)` | killed | `tests/test_sqlite_runner.py::test_buggy_fixture_duplicates_at_effect_commit` | 1 |
| 794 | `raise _AttemptFailure( ExecutionStatus.UNSUPPORTED, f"the handler r… -> pass` | killed | `tests/test_verdict_paths.py::test_side_channels_from_the_third_hostile_review_forfeit_the_verdict[home-rmdir-import` | 151 |
| 799 | `observed != expected -> (observed == expected)` | killed | `tests/test_sqlite_runner.py::test_buggy_fixture_duplicates_at_effect_commit` | 1 |
| 800 | `raise _AttemptFailure( ExecutionStatus.UNSUPPORTED, f"the handler c… -> pass` | killed | `tests/test_verdict_paths.py::test_side_channels_from_the_second_hostile_review_forfeit_the_verdict[chmod-import` | 147 |
| 809 | `_stat_entry(sidecar, False).kind != "file" -> (_stat_entry(sidecar, False).kind ` | killed | `tests/test_sqlite_runner.py::test_buggy_fixture_duplicates_at_effect_commit` | 1 |
| 809 | `sidecar.exists() and _stat_entry(sidecar, False).kind != "file" -> (sidecar.exis` | killed | `tests/test_sqlite_runner.py::test_buggy_fixture_duplicates_at_effect_commit` | 1 |
| 810 | `raise _AttemptFailure( ExecutionStatus.UNSUPPORTED, f"the handler r… -> pass` | survived | **hole**: The sidecar names are excluded from the extra-entry scan and absent from the pinned entries, so this raise is the only refusal that sees a `-wal` or `-shm` replaced by a directory or a FIFO; without it such a world earns a verdict, and no test puts anything but a regular file at either name. Owed: tests/test_sqlite_runner.py::test_a_sidecar_replaced_by_a_directory_is_state_no_store_commit_made (a `_make_sandbox` world, `<database>-shm` replaced by a directory, `_require_only_the_store_wrote` raises UNSUPPORTED naming it) | 202 |

### `src/nemisis/crash_models.py::AttemptReceipt.evidence_is_coherent`

87 mutants: 79 killed, 8 survived, 0 timed out.

| line | mutation | status | killed by / why it survives | s |
| ---: | -------- | ------ | --------------------------- | --: |
| 425 | `self.ended_at < self.started_at -> (self.ended_at <= self.started_at)` | survived | **hole**: An attempt whose start and end are the same instant is accepted today and refused as "ended before it started" under the mutant; no test builds a zero-duration attempt, so the 2026-09-07 label of equivalent was wrong. Owed: tests/test_crash_models.py::test_an_attempt_that_began_and_ended_in_the_same_instant_is_accepted (an AttemptReceipt with ended_at equal to started_at and its timeline collapsed to that instant; it validates) | 171 |
| 426 | `raise ValueError("attempt ended before it started") -> pass` | killed | `tests/test_crash_models.py::test_worker_and_attempt_timestamps_must_be_ordered` | 1 |
| 427 | `0 -> (-1)` | killed | `tests/test_crash_models.py::test_an_attempt_must_expect_a_nonzero_effect` | 1 |
| 427 | `0 -> (1)` | killed | `tests/test_crash_models.py::test_an_attempt_must_expect_a_nonzero_effect` | 1 |
| 427 | `self.effect_delta == 0 -> (self.effect_delta != 0)` | killed | `tests/test_crash_models.py::test_completed_attempt_requires_exact_kill_replay_evidence[integrity_status-INCOMPLETE]` | 0 |
| 428 | `raise ValueError("an attempt must expect a nonzero effect") -> pass` | killed | `tests/test_crash_models.py::test_an_attempt_must_expect_a_nonzero_effect` | 1 |
| 430 | `timestamps != sorted(timestamps) -> (timestamps == sorted(timestamps))` | killed | `tests/test_crash_models.py::test_completed_attempt_requires_exact_kill_replay_evidence[integrity_status-INCOMPLETE]` | 0 |
| 431 | `raise ValueError("attempt timeline is not ordered") -> pass` | killed | `tests/test_crash_models.py::test_an_unordered_attempt_timeline_is_refused` | 1 |
| 432 | `len({spawn.spawn_index for spawn in self.spawns}) != len(self.spawn… -> (len({sp` | killed | `tests/test_crash_models.py::test_completed_attempt_requires_exact_kill_replay_evidence[integrity_status-INCOMPLETE]` | 0 |
| 433 | `raise ValueError("worker spawn indices must be unique") -> pass` | killed | `tests/test_crash_models.py::test_worker_spawn_indices_must_be_unique` | 1 |
| 434 | `spawn.event_digest != self.event_digest -> (spawn.event_digest == self.event_dig` | killed | `tests/test_crash_models.py::test_completed_attempt_requires_exact_kill_replay_evidence[integrity_status-INCOMPLETE]` | 0 |
| 435 | `raise ValueError("worker event digest differs from attempt event") -> pass` | killed | `tests/test_crash_models.py::test_a_worker_bound_to_another_event_is_refused` | 1 |
| 436 | `2 -> (-2)` | killed | `tests/test_crash_models.py::test_replay_worker_requires_distinct_nonce_and_session[nonce]` | 1 |
| 436 | `2 -> (1)` | killed | `tests/test_crash_models.py::test_replay_worker_requires_distinct_nonce_and_session[nonce]` | 0 |
| 436 | `2 -> (3)` | killed | `tests/test_crash_models.py::test_replay_worker_requires_distinct_nonce_and_session[nonce]` | 0 |
| 436 | `len(self.spawns) == 2 -> (len(self.spawns) != 2)` | killed | `tests/test_crash_models.py::test_replay_worker_requires_distinct_nonce_and_session[nonce]` | 1 |
| 437 | `2 -> (-2)` | killed | `tests/test_crash_models.py::test_completed_attempt_requires_exact_kill_replay_evidence[integrity_status-INCOMPLETE]` | 0 |
| 437 | `2 -> (1)` | killed | `tests/test_crash_models.py::test_completed_attempt_requires_exact_kill_replay_evidence[integrity_status-INCOMPLETE]` | 0 |
| 437 | `2 -> (3)` | killed | `tests/test_crash_models.py::test_completed_attempt_requires_exact_kill_replay_evidence[integrity_status-INCOMPLETE]` | 0 |
| 437 | `len({spawn.worker_nonce for spawn in self.spawns}) != 2 -> (len({spawn.worker_no` | killed | `tests/test_crash_models.py::test_completed_attempt_requires_exact_kill_replay_evidence[integrity_status-INCOMPLETE]` | 0 |
| 438 | `raise ValueError("worker nonces must be distinct") -> pass` | killed | `tests/test_crash_models.py::test_replay_worker_requires_distinct_nonce_and_session[nonce]` | 1 |
| 439 | `2 -> (-2)` | killed | `tests/test_crash_models.py::test_completed_attempt_requires_exact_kill_replay_evidence[integrity_status-INCOMPLETE]` | 0 |
| 439 | `2 -> (1)` | killed | `tests/test_crash_models.py::test_completed_attempt_requires_exact_kill_replay_evidence[integrity_status-INCOMPLETE]` | 0 |
| 439 | `2 -> (3)` | killed | `tests/test_crash_models.py::test_completed_attempt_requires_exact_kill_replay_evidence[integrity_status-INCOMPLETE]` | 0 |
| 439 | `len({spawn.ipc_session_id for spawn in self.spawns}) != 2 -> (len({spawn.ipc_ses` | killed | `tests/test_crash_models.py::test_completed_attempt_requires_exact_kill_replay_evidence[integrity_status-INCOMPLETE]` | 0 |
| 440 | `raise ValueError("IPC sessions must be distinct") -> pass` | killed | `tests/test_crash_models.py::test_replay_worker_requires_distinct_nonce_and_session[session]` | 1 |
| 441 | `( self.pre_crash_snapshot, self.checkpoint_snapshot, self.post_kill… -> ((self.c` | survived | **hole**: Pydantic re-validates an existing instance with the exact-instance shortcut (`revalidate_instances` is "never"), so on a re-validated receipt this loop is the only check of the four nested snapshot digests; drop one and a forged snapshot passes. Pull request #27's argument held only for construction from a dict. Owed: tests/test_crash_models.py::test_every_snapshot_on_a_revalidated_attempt_is_checked_against_its_digest (written by a refuter tonight: `model_construct` a receipt around one `StateSnapshot.model_construct(digest=wrong)`, seal it, `model_validate` the instance, expect the digest refusal; one case per snapshot) | 196 |
| 441 | `( self.pre_crash_snapshot, self.checkpoint_snapshot, self.post_kill… -> ((self.p` | survived | **hole**: Pydantic re-validates an existing instance with the exact-instance shortcut (`revalidate_instances` is "never"), so on a re-validated receipt this loop is the only check of the four nested snapshot digests; drop one and a forged snapshot passes. Pull request #27's argument held only for construction from a dict. Owed: tests/test_crash_models.py::test_every_snapshot_on_a_revalidated_attempt_is_checked_against_its_digest (written by a refuter tonight: `model_construct` a receipt around one `StateSnapshot.model_construct(digest=wrong)`, seal it, `model_validate` the instance, expect the digest refusal; one case per snapshot) | 175 |
| 441 | `( self.pre_crash_snapshot, self.checkpoint_snapshot, self.post_kill… -> ((self.p` | survived | **hole**: Pydantic re-validates an existing instance with the exact-instance shortcut (`revalidate_instances` is "never"), so on a re-validated receipt this loop is the only check of the four nested snapshot digests; drop one and a forged snapshot passes. Pull request #27's argument held only for construction from a dict. Owed: tests/test_crash_models.py::test_every_snapshot_on_a_revalidated_attempt_is_checked_against_its_digest (written by a refuter tonight: `model_construct` a receipt around one `StateSnapshot.model_construct(digest=wrong)`, seal it, `model_validate` the instance, expect the digest refusal; one case per snapshot) | 248 |
| 441 | `( self.pre_crash_snapshot, self.checkpoint_snapshot, self.post_kill… -> ((self.p` | survived | **hole**: Pydantic re-validates an existing instance with the exact-instance shortcut (`revalidate_instances` is "never"), so on a re-validated receipt this loop is the only check of the four nested snapshot digests; drop one and a forged snapshot passes. Pull request #27's argument held only for construction from a dict. Owed: tests/test_crash_models.py::test_every_snapshot_on_a_revalidated_attempt_is_checked_against_its_digest (written by a refuter tonight: `model_construct` a receipt around one `StateSnapshot.model_construct(digest=wrong)`, seal it, `model_validate` the instance, expect the digest refusal; one case per snapshot) | 208 |
| 447 | `snapshot is not None -> (snapshot is None)` | killed | `tests/test_inventory_scenario.py::test_raw_sql_and_look_alike_arguments_get_the_inventory_words` | 13 |
| 449 | `self.execution_status is ExecutionStatus.COMPLETED -> (self.execution_status is ` | killed | `tests/test_crash_models.py::test_completed_attempt_requires_exact_kill_replay_evidence[integrity_status-INCOMPLETE]` | 1 |
| 450 | `self.integrity_status is not IntegrityStatus.VALID -> (self.integrity_status is ` | killed | `tests/test_crash_models.py::test_completed_attempt_requires_exact_kill_replay_evidence[integrity_status-INCOMPLETE]` | 0 |
| 451 | `raise ValueError("completed attempt requires valid integrity") -> pass` | killed | `tests/test_crash_models.py::test_completed_attempt_requires_exact_kill_replay_evidence[integrity_status-INCOMPLETE]` | 0 |
| 452 | `self.failure_detail is not None -> (self.failure_detail is None)` | killed | `tests/test_crash_models.py::test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 0 |
| 453 | `raise ValueError("completed attempt cannot have a failure detail") -> pass` | killed | `tests/test_crash_models.py::test_a_completed_attempt_cannot_carry_a_failure_detail` | 1 |
| 454 | `not ( self.checkpoint_reached and self.kill_signal == 9 and self.re… -> (self.ch` | killed | `tests/test_crash_models.py::test_completed_attempt_requires_exact_kill_replay_evidence[checkpoint_reached-False]` | 1 |
| 455 | `self.checkpoint_reached and self.kill_signal == 9 and self.replay_a… -> (self.ch` | killed | `tests/test_crash_models.py::test_completed_attempt_requires_exact_kill_replay_evidence[checkpoint_reached-False]` | 0 |
| 456 | `9 -> (-9)` | killed | `tests/test_crash_models.py::test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 0 |
| 456 | `9 -> (10)` | killed | `tests/test_crash_models.py::test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 0 |
| 456 | `9 -> (8)` | killed | `tests/test_crash_models.py::test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 0 |
| 456 | `self.kill_signal == 9 -> (self.kill_signal != 9)` | killed | `tests/test_crash_models.py::test_completed_attempt_requires_exact_kill_replay_evidence[kill_signal-15]` | 0 |
| 458 | `self.pre_crash_snapshot is not None -> (self.pre_crash_snapshot is None)` | killed | `tests/test_crash_models.py::test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 0 |
| 459 | `self.checkpoint_snapshot is not None -> (self.checkpoint_snapshot is None)` | killed | `tests/test_crash_models.py::test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 0 |
| 460 | `self.post_kill_snapshot is not None -> (self.post_kill_snapshot is None)` | killed | `tests/test_crash_models.py::test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 0 |
| 461 | `self.final_snapshot is not None -> (self.final_snapshot is None)` | killed | `tests/test_crash_models.py::test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 0 |
| 462 | `2 -> (-2)` | killed | `tests/test_crash_models.py::test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 1 |
| 462 | `2 -> (1)` | killed | `tests/test_crash_models.py::test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 1 |
| 462 | `2 -> (3)` | killed | `tests/test_crash_models.py::test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 0 |
| 462 | `len(self.spawns) == 2 -> (len(self.spawns) != 2)` | killed | `tests/test_crash_models.py::test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 0 |
| 463 | `0 -> (-1)` | killed | `tests/test_crash_models.py::test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 0 |
| 463 | `0 -> (1)` | killed | `tests/test_crash_models.py::test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 0 |
| 463 | `self.spawns[0].phase == "first" -> (self.spawns[0].phase != 'first')` | killed | `tests/test_crash_models.py::test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 1 |
| 464 | `-9 -> (9)` | killed | `tests/test_crash_models.py::test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 0 |
| 464 | `0 -> (-1)` | killed | `tests/test_crash_models.py::test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 0 |
| 464 | `0 -> (1)` | killed | `tests/test_crash_models.py::test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 0 |
| 464 | `9 -> (-9)` | killed | `tests/test_crash_models.py::test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 0 |
| 464 | `9 -> (10)` | killed | `tests/test_crash_models.py::test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 0 |
| 464 | `9 -> (8)` | killed | `tests/test_crash_models.py::test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 0 |
| 464 | `self.spawns[0].exit_code == -9 -> (self.spawns[0].exit_code != -9)` | killed | `tests/test_crash_models.py::test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 1 |
| 465 | `1 -> (-1)` | survived | **equivalent**: Reached only after `len(self.spawns) == 2` held in the same short-circuiting and-chain, so index -1 is index 1; pull request #27's argument, confirmed by a refuter. | 228 |
| 465 | `1 -> (0)` | killed | `tests/test_crash_models.py::test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 1 |
| 465 | `1 -> (2)` | killed | `tests/test_crash_models.py::test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 0 |
| 465 | `self.spawns[1].phase == "replay" -> (self.spawns[1].phase != 'replay')` | killed | `tests/test_crash_models.py::test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 0 |
| 466 | `0 -> (-1)` | killed | `tests/test_crash_models.py::test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 0 |
| 466 | `0 -> (1)` | killed | `tests/test_crash_models.py::test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 0 |
| 466 | `1 -> (-1)` | survived | **equivalent**: The same guard fixes the tuple at length two, so the negative index names the same spawn; confirmed by a refuter. | 186 |
| 466 | `1 -> (0)` | killed | `tests/test_crash_models.py::test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 1 |
| 466 | `1 -> (2)` | killed | `tests/test_crash_models.py::test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 0 |
| 466 | `self.spawns[1].exit_code == 0 -> (self.spawns[1].exit_code != 0)` | killed | `tests/test_crash_models.py::test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 0 |
| 468 | `raise ValueError("completed attempt lacks exact kill/replay evidenc… -> pass` | killed | `tests/test_crash_models.py::test_completed_attempt_requires_exact_kill_replay_evidence[checkpoint_reached-False]` | 0 |
| 469 | `self.post_execution_tree_digest != self.tree_digest -> (self.post_execution_tree` | killed | `tests/test_crash_models.py::test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 0 |
| 470 | `raise ValueError( "completed attempt post-execution tree differs fr… -> pass` | killed | `tests/test_crash_models.py::test_completed_attempt_binds_tree_and_observation_to_snapshots` | 0 |
| 477 | `checkpoint is not None -> (checkpoint is None)` | killed | `tests/test_crash_models.py::test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 0 |
| 477 | `post_kill is not None -> (post_kill is None)` | killed | `tests/test_crash_models.py::test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 1 |
| 477 | `pre is not None -> (pre is None)` | killed | `tests/test_crash_models.py::test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 0 |
| 477 | `pre is not None and checkpoint is not None and post_kill is not None -> (pre is ` | survived | **hole**: The assert is the last guard before `_seeded(pre)`; with `or` a receipt whose pre-crash snapshot is missing at that point dies with AttributeError inside `_seeded` instead of being refused at the narrowing: a crash where a refusal belongs. Owed: tests/test_crash_models.py::test_a_completed_attempt_without_a_pre_crash_snapshot_never_reaches_the_seed_check (written by a refuter tonight; calls the validator on a stand-in whose pre-crash snapshot is gone after the evidence gate) | 184 |
| 478 | `final is not None -> (final is None)` | killed | `tests/test_crash_models.py::test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 0 |
| 479 | `not _seeded(pre) -> (_seeded(pre))` | killed | `tests/test_crash_models.py::test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 0 |
| 480 | `raise ValueError("completed attempt pre-crash snapshot is not the s… -> pass` | killed | `tests/test_crash_models.py::test_a_completed_attempt_must_begin_from_the_seeded_state` | 1 |
| 481 | `post_kill.digest != checkpoint.digest -> (post_kill.digest == checkpoint.digest)` | killed | `tests/test_crash_models.py::test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 0 |
| 482 | `raise ValueError("completed attempt checkpoint changed after worker… -> pass` | killed | `tests/test_crash_models.py::test_completed_attempt_binds_tree_and_observation_to_snapshots` | 0 |
| 485 | `self.observation is not classify_final(final, self.effect_delta, pr… -> (self.ob` | killed | `tests/test_crash_models.py::test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 0 |
| 486 | `raise ValueError("completed attempt observation contradicts its fin… -> pass` | killed | `tests/test_crash_models.py::test_duplicate_observation_accepts_a_missing_marker` | 0 |
| 487 | `self.failure_detail is None -> (self.failure_detail is not None)` | killed | `tests/test_crash_models.py::test_completed_result_cannot_contain_an_incomplete_attempt` | 1 |
| 488 | `raise ValueError("incomplete attempt requires a failure detail") -> pass` | killed | `tests/test_crash_models.py::test_an_incomplete_attempt_requires_a_failure_detail` | 1 |
| 489 | `return self -> return None` | killed | `tests/test_crash_models.py::test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 0 |

### `src/nemisis/crashcheck.py::_schedule_split`

8 mutants: 8 killed, 0 survived, 0 timed out.

| line | mutation | status | killed by / why it survives | s |
| ---: | -------- | ------ | --------------------------- | --: |
| 1609 | `sweep is None -> (sweep is not None)` | killed | `tests/test_inventory_scenario.py::test_the_hero_story_holds_for_a_decrement` | 6 |
| 1609 | `sweep is None or sweep.census.execution_status is not ExecutionStat… -> (sweep i` | killed | `tests/test_inventory_scenario.py::test_the_hero_story_holds_for_a_decrement` | 6 |
| 1609 | `sweep.census.execution_status is not ExecutionStatus.COMPLETED -> (sweep.census.` | killed | `tests/test_verdict_paths.py::test_a_schedule_that_differs_between_worlds_is_named_not_swept` | 119 |
| 1614 | `attempt.execution_status is ExecutionStatus.COMPLETED -> (attempt.execution_stat` | killed | `tests/test_verdict_paths.py::test_a_schedule_that_differs_between_worlds_is_named_not_swept` | 117 |
| 1614 | `attempt.execution_status is ExecutionStatus.COMPLETED and own != ce… -> (attempt` | killed | `tests/test_inventory_scenario.py::test_the_hero_story_holds_for_a_decrement` | 8 |
| 1614 | `census[: len(own)] -> (census)` | killed | `tests/test_verdict_paths.py::test_guarded_leftover_credit_is_caught_by_the_census_and_blamed_on_no_crash` | 44 |
| 1614 | `own != census[: len(own)] -> (own == census[:len(own)])` | killed | `tests/test_inventory_scenario.py::test_the_hero_story_holds_for_a_decrement` | 7 |
| 1615 | `return ( f"a kill world committed {', '.join(own) or 'nothing'} whe… -> return N` | killed | `tests/test_verdict_paths.py::test_a_schedule_that_differs_between_worlds_is_named_not_swept` | 118 |

### `src/nemisis/crash_models.py::classify_final`

31 mutants: 31 killed, 0 survived, 0 timed out.

| line | mutation | status | killed by / why it survives | s |
| ---: | -------- | ------ | --------------------------- | --: |
| 339 | `(effect_delta * 2, 2, effect_delta * 2) -> ((2, effect_delta * 2))` | killed | `tests/test_crash_models.py::test_duplicate_observation_accepts_a_missing_marker` | 0 |
| 339 | `(effect_delta * 2, 2, effect_delta * 2) -> ((effect_delta * 2, 2))` | killed | `tests/test_crash_models.py::test_duplicate_observation_accepts_a_missing_marker` | 0 |
| 339 | `(effect_delta * 2, 2, effect_delta * 2) -> ((effect_delta * 2, effect_delta * 2)` | killed | `tests/test_crash_models.py::test_duplicate_observation_accepts_a_missing_marker` | 0 |
| 339 | `2 -> (-2)` | killed | `tests/test_crash_models.py::test_duplicate_observation_accepts_a_missing_marker` | 0 |
| 339 | `2 -> (-2)` | killed | `tests/test_crash_models.py::test_duplicate_observation_accepts_a_missing_marker` | 0 |
| 339 | `2 -> (-2)` | killed | `tests/test_crash_models.py::test_duplicate_observation_accepts_a_missing_marker` | 0 |
| 339 | `2 -> (1)` | killed | `tests/test_crash_models.py::test_duplicate_observation_accepts_a_missing_marker` | 0 |
| 339 | `2 -> (1)` | killed | `tests/test_crash_models.py::test_duplicate_observation_accepts_a_missing_marker` | 0 |
| 339 | `2 -> (1)` | killed | `tests/test_crash_models.py::test_duplicate_observation_accepts_a_missing_marker` | 0 |
| 339 | `2 -> (3)` | killed | `tests/test_crash_models.py::test_duplicate_observation_accepts_a_missing_marker` | 0 |
| 339 | `2 -> (3)` | killed | `tests/test_crash_models.py::test_duplicate_observation_accepts_a_missing_marker` | 0 |
| 339 | `2 -> (3)` | killed | `tests/test_crash_models.py::test_duplicate_observation_accepts_a_missing_marker` | 0 |
| 339 | `3 -> (-3)` | killed | `tests/test_crash_models.py::test_duplicate_observation_accepts_a_missing_marker` | 0 |
| 339 | `3 -> (2)` | killed | `tests/test_crash_models.py::test_duplicate_observation_accepts_a_missing_marker` | 0 |
| 339 | `3 -> (4)` | killed | `tests/test_crash_models.py::test_duplicate_observation_accepts_a_missing_marker` | 0 |
| 339 | `state[:3] -> (state)` | killed | `tests/test_crash_models.py::test_duplicate_observation_accepts_a_missing_marker` | 0 |
| 339 | `state[:3] == (effect_delta * 2, 2, effect_delta * 2) -> (state[:3] != (effect_de` | killed | `tests/test_crash_models.py::test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 1 |
| 340 | `return CrashObservation.DUPLICATE_EFFECT -> return None` | killed | `tests/test_crash_models.py::test_duplicate_observation_accepts_a_missing_marker` | 0 |
| 341 | `(effect_delta, 1, effect_delta, 1) -> ((1, effect_delta, 1))` | killed | `tests/test_crash_models.py::test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 0 |
| 341 | `(effect_delta, 1, effect_delta, 1) -> ((effect_delta, 1, 1))` | killed | `tests/test_crash_models.py::test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 0 |
| 341 | `(effect_delta, 1, effect_delta, 1) -> ((effect_delta, 1, effect_delta))` | killed | `tests/test_crash_models.py::test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 0 |
| 341 | `(effect_delta, 1, effect_delta, 1) -> ((effect_delta, effect_delta, 1))` | killed | `tests/test_crash_models.py::test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 0 |
| 341 | `1 -> (-1)` | killed | `tests/test_crash_models.py::test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 0 |
| 341 | `1 -> (-1)` | killed | `tests/test_crash_models.py::test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 0 |
| 341 | `1 -> (0)` | killed | `tests/test_crash_models.py::test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 0 |
| 341 | `1 -> (0)` | killed | `tests/test_crash_models.py::test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 0 |
| 341 | `1 -> (2)` | killed | `tests/test_crash_models.py::test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 0 |
| 341 | `1 -> (2)` | killed | `tests/test_crash_models.py::test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 0 |
| 341 | `state == (effect_delta, 1, effect_delta, 1) -> (state != (effect_delta, 1, effec` | killed | `tests/test_crash_models.py::test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 0 |
| 342 | `return CrashObservation.EXACTLY_ONCE -> return None` | killed | `tests/test_crash_models.py::test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 0 |
| 343 | `return CrashObservation.INVARIANT_FAILED -> return None` | killed | `tests/test_crash_models.py::test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 0 |

### `src/nemisis/sqlite_runner.py::_require_unchanged`

6 mutants: 6 killed, 0 survived, 0 timed out.

| line | mutation | status | killed by / why it survives | s |
| ---: | -------- | ------ | --------------------------- | --: |
| 1247 | `ledger.content -> (ledger.snapshot)` | killed | `tests/test_sqlite_runner.py::test_buggy_fixture_duplicates_at_effect_commit` | 1 |
| 1247 | `observed.content -> (observed.snapshot)` | killed | `tests/test_sqlite_runner.py::test_buggy_fixture_duplicates_at_effect_commit` | 1 |
| 1247 | `sha256_json(observed.content) != sha256_json(ledger.content) -> (sha256_json(obs` | killed | `tests/test_sqlite_runner.py::test_buggy_fixture_duplicates_at_effect_commit` | 1 |
| 1248 | `raise _AttemptFailure( ExecutionStatus.INTEGRITY_ERROR, f"{what}: {… -> pass` | killed | `tests/test_sqlite_runner.py::test_a_write_after_the_worker_died_forfeits_the_post_kill_checkpoint` | 3 |
| 1253 | `observed.snapshot -> (observed.content)` | killed | `tests/test_sqlite_runner.py::test_buggy_fixture_duplicates_at_effect_commit` | 1 |
| 1253 | `return observed.snapshot -> return None` | killed | `tests/test_sqlite_runner.py::test_buggy_fixture_duplicates_at_effect_commit` | 1 |

### `src/nemisis/crash_models.py::classify_delivery`

4 mutants: 4 killed, 0 survived, 0 timed out.

| line | mutation | status | killed by / why it survives | s |
| ---: | -------- | ------ | --------------------------- | --: |
| 318 | `after_redelivery is not CrashObservation.EXACTLY_ONCE -> (after_redelivery is Cr` | killed | `tests/test_verdict_paths.py::test_guarded_leftover_credit_is_caught_by_the_census_and_blamed_on_no_crash` | 45 |
| 319 | `return after_redelivery -> return None` | killed | `tests/test_verdict_paths.py::test_guarded_leftover_credit_is_caught_by_the_census_and_blamed_on_no_crash` | 45 |
| 321 | `return ( CrashObservation.EXACTLY_ONCE if after_one is CrashObserva… -> return N` | killed | `tests/test_crash_models.py::test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 0 |
| 323 | `after_one is CrashObservation.EXACTLY_ONCE -> (after_one is not CrashObservation` | killed | `tests/test_crash_models.py::test_proven_fix_requires_a_commit_sweep_that_ends_exactly_once` | 0 |

### `src/nemisis/sqlite_runner.py::_SEED_MODE`

3 mutants: 3 killed, 0 survived, 0 timed out.

| line | mutation | status | killed by / why it survives | s |
| ---: | -------- | ------ | --------------------------- | --: |
| 817 | `0o600 -> (-384)` | killed | `tests/test_scenario.py::test_seed_probe_and_checkpoint_predicate_describe_the_same_database` | 0 |
| 817 | `0o600 -> (383)` | killed | `tests/test_scenario.py::test_seed_probe_and_checkpoint_predicate_describe_the_same_database` | 0 |
| 817 | `0o600 -> (385)` | killed | `tests/test_verdict_paths.py::test_side_channels_from_the_second_hostile_review_forfeit_the_verdict[chmod-import` | 125 |

### `src/nemisis/sqlite_runner.py::_finish_replay`

30 mutants: 29 killed, 1 survived, 0 timed out.

| line | mutation | status | killed by / why it survives | s |
| ---: | -------- | ------ | --------------------------- | --: |
| 1538 | `kind == "commit" -> (kind != 'commit')` | killed | `tests/test_sqlite_runner.py::test_buggy_fixture_duplicates_at_effect_commit` | 2 |
| 1543 | `kind == "error" -> (kind != 'error')` | killed | `tests/test_sqlite_runner.py::test_buggy_fixture_duplicates_at_effect_commit` | 1 |
| 1544 | `message.get("error") == STORE_REFUSAL -> (message.get('error') != STORE_REFUSAL)` | killed | `tests/test_verdict_paths.py::test_handler_that_never_credits_is_reported_with_its_no_crash_money` | 63 |
| 1545 | `raise _store_refusal(scenario, database, event, ledger, spawn, firs… -> pass` | killed | `tests/test_verdict_paths.py::test_writes_to_other_accounts_or_events_are_an_integrity_failure` | 70 |
| 1546 | `raise _AttemptFailure( ExecutionStatus.REPLAY_ERROR, f"the handler … -> pass` | killed | `tests/test_verdict_paths.py::test_handler_that_never_credits_is_reported_with_its_no_crash_money` | 69 |
| 1551 | `{ "event_digest": capsule.event_digest, "execution_nonce": executio… -> ({'event` | killed | `tests/test_sqlite_runner.py::test_buggy_fixture_duplicates_at_effect_commit` | 1 |
| 1551 | `{ "event_digest": capsule.event_digest, "execution_nonce": executio… -> ({'event` | killed | `tests/test_sqlite_runner.py::test_buggy_fixture_duplicates_at_effect_commit` | 1 |
| 1551 | `{ "event_digest": capsule.event_digest, "execution_nonce": executio… -> ({'execu` | killed | `tests/test_sqlite_runner.py::test_buggy_fixture_duplicates_at_effect_commit` | 1 |
| 1556 | `message != expected -> (message == expected)` | killed | `tests/test_sqlite_runner.py::test_buggy_fixture_duplicates_at_effect_commit` | 1 |
| 1557 | `raise _AttemptFailure(ExecutionStatus.PROTOCOL_ERROR, "replay compl… -> pass` | killed | `tests/test_sqlite_runner.py::test_a_malformed_replay_completion_is_a_protocol_error` | 3 |
| 1568 | `ledger.content -> (ledger.snapshot)` | killed | `tests/test_sqlite_runner.py::test_buggy_fixture_duplicates_at_effect_commit` | 1 |
| 1568 | `observed.content -> (observed.snapshot)` | killed | `tests/test_sqlite_runner.py::test_buggy_fixture_duplicates_at_effect_commit` | 1 |
| 1568 | `refusal is None -> (refusal is not None)` | killed | `tests/test_verdict_paths.py::test_bytes_written_after_the_last_commit_forfeit_the_verdict[effect-then-tail]` | 171 |
| 1568 | `refusal is None and sha256_json(observed.content) != sha256_json(le… -> (refusal` | killed | `tests/test_sqlite_runner.py::test_buggy_fixture_duplicates_at_effect_commit` | 1 |
| 1568 | `sha256_json(observed.content) != sha256_json(ledger.content) -> (sha256_json(obs` | killed | `tests/test_sqlite_runner.py::test_buggy_fixture_duplicates_at_effect_commit` | 1 |
| 1585 | `raise _AttemptFailure( ExecutionStatus.TIMEOUT, f"the {spawn.phase}… -> pass` | killed | `tests/test_sqlite_runner.py::test_a_replay_worker_that_reports_done_and_does_not_exit_runs_out_of_time` | 10 |
| 1592 | `refusal is not None -> (refusal is None)` | killed | `tests/test_sqlite_runner.py::test_buggy_fixture_duplicates_at_effect_commit` | 1 |
| 1593 | `raise refusal -> pass` | killed | `tests/test_verdict_paths.py::test_bytes_written_after_the_last_commit_forfeit_the_verdict[effect-then-tail]` | 153 |
| 1594 | `0 -> (-1)` | killed | `tests/test_sqlite_runner.py::test_buggy_fixture_duplicates_at_effect_commit` | 1 |
| 1594 | `0 -> (1)` | killed | `tests/test_sqlite_runner.py::test_buggy_fixture_duplicates_at_effect_commit` | 1 |
| 1594 | `return_code != 0 -> (return_code == 0)` | killed | `tests/test_sqlite_runner.py::test_buggy_fixture_duplicates_at_effect_commit` | 1 |
| 1595 | `raise _AttemptFailure(ExecutionStatus.REPLAY_ERROR, "replay worker … -> pass` | killed | `tests/test_sqlite_runner.py::test_a_replay_worker_that_exits_nonzero_after_done_is_a_replay_error` | 4 |
| 1597 | `ledger.content -> (ledger.snapshot)` | killed | `tests/test_sqlite_runner.py::test_buggy_fixture_duplicates_at_effect_commit` | 1 |
| 1597 | `observed.content -> (observed.snapshot)` | killed | `tests/test_sqlite_runner.py::test_buggy_fixture_duplicates_at_effect_commit` | 1 |
| 1598 | `ledger.content -> (ledger.snapshot)` | killed | `tests/test_sqlite_runner.py::test_buggy_fixture_duplicates_at_effect_commit` | 1 |
| 1598 | `observed.content -> (observed.snapshot)` | killed | `tests/test_sqlite_runner.py::test_buggy_fixture_duplicates_at_effect_commit` | 1 |
| 1598 | `sha256_json(_after_exit(observed.content)) != sha256_json(_after_ex… -> (sha256_` | killed | `tests/test_sqlite_runner.py::test_buggy_fixture_duplicates_at_effect_commit` | 1 |
| 1599 | `raise _AttemptFailure( ExecutionStatus.INTEGRITY_ERROR, "the databa… -> pass` | survived | **equivalent**: Dominated by `_require_image` one line above: a file whose bytes equal the last read's logical image and whose log is empty holds exactly that image's rows, schema, and header, so the content comparison cannot disagree; a refuter reached the raise only by making `_ledger` report rows the file does not hold. | 182 |
| 1609 | `observed.snapshot -> (observed.content)` | killed | `tests/test_sqlite_runner.py::test_buggy_fixture_duplicates_at_effect_commit` | 1 |
| 1609 | `return observed.snapshot -> return None` | killed | `tests/test_sqlite_runner.py::test_buggy_fixture_duplicates_at_effect_commit` | 1 |

### `src/nemisis/sqlite_runner.py::_attributed_probe`

39 mutants: 28 killed, 11 survived, 0 timed out.

| line | mutation | status | killed by / why it survives | s |
| ---: | -------- | ------ | --------------------------- | --: |
| 1629 | `operation not in scenario.store_operations -> (operation in scenario.store_opera` | killed | `tests/test_sqlite_runner.py::test_attributed_probe_accepts_only_the_delta_its_operation_explains` | 1 |
| 1630 | `raise _AttemptFailure( ExecutionStatus.PROTOCOL_ERROR, f"worker rep… -> pass` | killed | `tests/test_sqlite_runner.py::test_attributed_probe_accepts_only_the_delta_its_operation_explains` | 1 |
| 1634 | `ledger.content -> (ledger.snapshot)` | killed | `tests/test_sqlite_runner.py::test_attributed_probe_accepts_only_the_delta_its_operation_explains` | 1 |
| 1639 | `ledger.content -> (ledger.snapshot)` | killed | `tests/test_sqlite_runner.py::test_attributed_probe_accepts_only_the_delta_its_operation_explains` | 1 |
| 1639 | `str, object -> ((object,))` | survived | **equivalent**: `typing.cast` returns its second argument untouched and the subscript is for the type checker alone; seven mutants on four lines, confirmed by a refuter. | 177 |
| 1639 | `str, object -> ((str,))` | survived | **equivalent**: `typing.cast` returns its second argument untouched and the subscript is for the type checker alone; seven mutants on four lines, confirmed by a refuter. | 179 |
| 1640 | `observed.content -> (observed.snapshot)` | killed | `tests/test_sqlite_runner.py::test_attributed_probe_accepts_only_the_delta_its_operation_explains` | 1 |
| 1640 | `str, object -> ((object,))` | survived | **equivalent**: `typing.cast` returns its second argument untouched and the subscript is for the type checker alone; see line 1639. | 178 |
| 1640 | `str, object -> ((str,))` | killed | `tests/test_verdict_paths.py::test_raw_sql_judge_handler_is_told_the_one_line_change` | 88 |
| 1641 | `str, object -> ((object,))` | survived | **equivalent**: `typing.cast` returns its second argument untouched and the subscript is for the type checker alone; see line 1639. | 177 |
| 1641 | `str, object -> ((str,))` | survived | **equivalent**: `typing.cast` returns its second argument untouched and the subscript is for the type checker alone; see line 1639. | 177 |
| 1642 | `str, object -> ((object,))` | survived | **equivalent**: `typing.cast` returns its second argument untouched and the subscript is for the type checker alone; see line 1639. | 179 |
| 1642 | `str, object -> ((str,))` | survived | **equivalent**: `typing.cast` returns its second argument untouched and the subscript is for the type checker alone; see line 1639. | 183 |
| 1643 | `0 -> (-1)` | killed | `tests/test_sqlite_runner.py::test_attributed_probe_accepts_only_the_delta_its_operation_explains` | 1 |
| 1643 | `0 -> (1)` | survived | **hole**: A one-byte log is recordable (a stray byte written to `-wal` before the first commit, with no wal-index, reads as one frame byte of one), and the next commit overwrites it with a real header; with `> 1` that rewrite is never examined and the candidate keeps a verdict. Owed: tests/test_verdict_paths.py::test_a_one_byte_write_ahead_log_is_a_log_the_probe_still_reads (written by a refuter tonight; seeds, writes one byte to `-wal`, removes `-shm`, commits, expects INTEGRITY_ERROR from the prefix rule) | 188 |
| 1643 | `cast(int, before["size"]) > 0 -> (cast(int, before['size']) >= 0)` | killed | `tests/test_sqlite_runner.py::test_attributed_probe_accepts_only_the_delta_its_operation_explains` | 1 |
| 1643 | `cast(int, before["size"]) > 0 and ( cast(int, after["size"]) < cast… -> (cast(in` | killed | `tests/test_sqlite_runner.py::test_attributed_probe_accepts_only_the_delta_its_operation_explains` | 1 |
| 1644 | `cast(int, after["size"]) < cast(int, before["size"]) -> (cast(int, after['size']` | survived | **equivalent**: Every store operation commits rows and appends at least one frame, and a log whose length is not its wal-index's frame end is refused at the read, so an observed log is never the recorded length; a refuter reached the flip only with a ledger no read produces. | 201 |
| 1644 | `cast(int, after["size"]) < cast(int, before["size"]) or _wal_prefix… -> (cast(in` | survived | **hole**: With `and`, a log rewritten in place at the same or a greater length is no longer refused, because a shorter file already fails the prefix digest; the shape is a handler that overwrites bytes inside the frame its own commit wrote before its next commit. Owed: tests/test_verdict_paths.py::test_a_log_rewritten_in_place_between_two_commits_costs_the_candidate_its_verdict (a handler that credits, overwrites sixteen bytes inside that commit's frame, then marks; expects INTEGRITY_ERROR naming the rewrite) | 174 |
| 1645 | `_wal_prefix_digest(database, cast(int, before["size"])) != before["… -> (_wal_pr` | killed | `tests/test_sqlite_runner.py::test_attributed_probe_accepts_only_the_delta_its_operation_explains` | 1 |
| 1647 | `raise _AttemptFailure( ExecutionStatus.INTEGRITY_ERROR, f"the write… -> pass` | survived | **hole**: The predicted content copies the observed log and image, so with this raise dropped a log rewritten around the store is the one change nothing else compares, and the candidate keeps a verdict. Owed: the same test as the `and` mutant above; the eleven pinned-whole shapes are refused earlier, at the read, which is why none reaches this line | 203 |
| 1654 | `{ "file": { **ledger_file, "wal": observed_file["wal"], "image_sha2… -> ({'file'` | killed | `tests/test_sqlite_runner.py::test_attributed_probe_accepts_only_the_delta_its_operation_explains` | 1 |
| 1654 | `{ "file": { **ledger_file, "wal": observed_file["wal"], "image_sha2… -> ({'file'` | killed | `tests/test_sqlite_runner.py::test_attributed_probe_accepts_only_the_delta_its_operation_explains` | 1 |
| 1654 | `{ "file": { **ledger_file, "wal": observed_file["wal"], "image_sha2… -> ({'file'` | killed | `tests/test_sqlite_runner.py::test_attributed_probe_accepts_only_the_delta_its_operation_explains` | 1 |
| 1654 | `{ "file": { **ledger_file, "wal": observed_file["wal"], "image_sha2… -> ({'heade` | killed | `tests/test_sqlite_runner.py::test_attributed_probe_accepts_only_the_delta_its_operation_explains` | 1 |
| 1661 | `ledger.content -> (ledger.snapshot)` | killed | `tests/test_sqlite_runner.py::test_attributed_probe_accepts_only_the_delta_its_operation_explains` | 1 |
| 1662 | `ledger.content -> (ledger.snapshot)` | killed | `tests/test_sqlite_runner.py::test_attributed_probe_accepts_only_the_delta_its_operation_explains` | 1 |
| 1665 | `observed.content -> (observed.snapshot)` | killed | `tests/test_sqlite_runner.py::test_attributed_probe_accepts_only_the_delta_its_operation_explains` | 1 |
| 1665 | `sha256_json(observed.content) == sha256_json(predicted) -> (sha256_json(observed` | killed | `tests/test_sqlite_runner.py::test_attributed_probe_accepts_only_the_delta_its_operation_explains` | 1 |
| 1666 | `return observed -> return None` | killed | `tests/test_sqlite_runner.py::test_attributed_probe_accepts_only_the_delta_its_operation_explains` | 1 |
| 1667 | `scenario.snapshot -> (scenario.content)` | killed | `tests/test_sqlite_runner.py::test_attributed_probe_accepts_only_the_delta_its_operation_explains` | 1 |
| 1668 | `ledger.snapshot -> (ledger.content)` | killed | `tests/test_sqlite_runner.py::test_attributed_probe_accepts_only_the_delta_its_operation_explains` | 1 |
| 1668 | `ledger.snapshot, observed.snapshot -> ((ledger.snapshot,))` | killed | `tests/test_sqlite_runner.py::test_attributed_probe_accepts_only_the_delta_its_operation_explains` | 1 |
| 1668 | `ledger.snapshot, observed.snapshot -> ((observed.snapshot,))` | killed | `tests/test_sqlite_runner.py::test_attributed_probe_accepts_only_the_delta_its_operation_explains` | 1 |
| 1668 | `observed.snapshot -> (observed.content)` | killed | `tests/test_sqlite_runner.py::test_attributed_probe_accepts_only_the_delta_its_operation_explains` | 1 |
| 1669 | `scenario.subject_noun, f"{scenario.effect_noun} rows" -> ((f'{scenario.effect_no` | killed | `tests/test_sqlite_runner.py::test_attributed_probe_accepts_only_the_delta_its_operation_explains` | 1 |
| 1669 | `scenario.subject_noun, f"{scenario.effect_noun} rows" -> ((scenario.subject_noun` | killed | `tests/test_sqlite_runner.py::test_attributed_probe_accepts_only_the_delta_its_operation_explains` | 1 |
| 1670 | `seen.digest != wanted.digest -> (seen.digest == wanted.digest)` | killed | `tests/test_sqlite_runner.py::test_attributed_probe_accepts_only_the_delta_its_operation_explains` | 1 |
| 1688 | `raise _AttemptFailure( ExecutionStatus.INTEGRITY_ERROR, detail, int… -> pass` | killed | `tests/test_sqlite_runner.py::test_attributed_probe_accepts_only_the_delta_its_operation_explains` | 1 |

### `src/nemisis/sqlite_runner.py::_HEADER_PRAGMAS`

9 mutants: 9 killed, 0 survived, 0 timed out.

| line | mutation | status | killed by / why it survives | s |
| ---: | -------- | ------ | --------------------------- | --: |
| 1155 | `( "application_id", "auto_vacuum", "default_cache_size", "encoding"… -> (('appli` | killed | `tests/test_sqlite_runner.py::test_every_named_header_pragma_is_read_into_the_content[freelist_count]` | 3 |
| 1155 | `( "application_id", "auto_vacuum", "default_cache_size", "encoding"… -> (('appli` | killed | `tests/test_sqlite_runner.py::test_every_named_header_pragma_is_read_into_the_content[journal_mode]` | 3 |
| 1155 | `( "application_id", "auto_vacuum", "default_cache_size", "encoding"… -> (('appli` | killed | `tests/test_sqlite_runner.py::test_every_named_header_pragma_is_read_into_the_content[page_size]` | 3 |
| 1155 | `( "application_id", "auto_vacuum", "default_cache_size", "encoding"… -> (('appli` | killed | `tests/test_sqlite_runner.py::test_every_named_header_pragma_is_read_into_the_content[schema_version]` | 3 |
| 1155 | `( "application_id", "auto_vacuum", "default_cache_size", "encoding"… -> (('appli` | killed | `tests/test_sqlite_runner.py::test_every_named_header_pragma_is_read_into_the_content[user_version]` | 3 |
| 1155 | `( "application_id", "auto_vacuum", "default_cache_size", "encoding"… -> (('appli` | killed | `tests/test_sqlite_runner.py::test_every_named_header_pragma_is_read_into_the_content[encoding]` | 3 |
| 1155 | `( "application_id", "auto_vacuum", "default_cache_size", "encoding"… -> (('appli` | killed | `tests/test_sqlite_runner.py::test_every_named_header_pragma_is_read_into_the_content[default_cache_size]` | 3 |
| 1155 | `( "application_id", "auto_vacuum", "default_cache_size", "encoding"… -> (('appli` | killed | `tests/test_sqlite_runner.py::test_every_named_header_pragma_is_read_into_the_content[auto_vacuum]` | 3 |
| 1155 | `( "application_id", "auto_vacuum", "default_cache_size", "encoding"… -> (('auto_` | killed | `tests/test_sqlite_runner.py::test_every_named_header_pragma_is_read_into_the_content[application_id]` | 3 |

### `src/nemisis/sqlite_runner.py::_read_content`

14 mutants: 11 killed, 3 survived, 0 timed out.

| line | mutation | status | killed by / why it survives | s |
| ---: | -------- | ------ | --------------------------- | --: |
| 1124 | `0 -> (-1)` | survived | **equivalent**: Every name in `_HEADER_PRAGMAS` is a scalar pragma whose row is a one-tuple, so index -1 is index 0; confirmed by a refuter. | 194 |
| 1124 | `0 -> (1)` | killed | `tests/test_scenario.py::test_seed_probe_and_checkpoint_predicate_describe_the_same_database` | 1 |
| 1132 | `(sqlite3.Error, OSError) -> ((OSError,))` | killed | `tests/test_sqlite_runner.py::test_a_probe_that_cannot_read_the_database_is_a_probe_error` | 4 |
| 1132 | `(sqlite3.Error, OSError) -> ((sqlite3.Error,))` | killed | `tests/test_sqlite_runner.py::test_a_probe_that_cannot_read_the_database_is_a_probe_error` | 4 |
| 1133 | `raise _AttemptFailure( ExecutionStatus.PROBE_ERROR, f"read-only sta… -> pass` | killed | `tests/test_sqlite_runner.py::test_a_probe_that_cannot_read_the_database_is_a_probe_error` | 4 |
| 1138 | `str, object -> ((object,))` | survived | **equivalent**: The subscript of the type argument to `cast`, invisible at runtime; the gate's mypy refuses both forms, which is where this mutant dies. | 177 |
| 1138 | `str, object -> ((str,))` | survived | **equivalent**: The subscript of the type argument to `cast`, invisible at runtime; the gate's mypy refuses both forms, which is where this mutant dies. | 194 |
| 1139 | `wal["size"] != wal["frames_size"] -> (wal['size'] == wal['frames_size'])` | killed | `tests/test_scenario.py::test_seed_probe_and_checkpoint_predicate_describe_the_same_database` | 1 |
| 1140 | `raise _AttemptFailure( ExecutionStatus.INTEGRITY_ERROR, f"the datab… -> pass` | killed | `tests/test_verdict_paths.py::test_the_file_and_its_log_are_pinned_whole_during_a_delivery[wal-tail-after-commit-def` | 233 |
| 1148 | `return {"file": identity, "header": header, "schema": schema, "tabl… -> return N` | killed | `tests/test_scenario.py::test_seed_probe_and_checkpoint_predicate_describe_the_same_database` | 1 |
| 1148 | `{"file": identity, "header": header, "schema": schema, "tables": ta… -> ({'file'` | killed | `tests/test_scenario.py::test_seed_probe_and_checkpoint_predicate_describe_the_same_database` | 1 |
| 1148 | `{"file": identity, "header": header, "schema": schema, "tables": ta… -> ({'file'` | killed | `tests/test_sqlite_runner.py::test_attributed_probe_accepts_only_the_delta_its_operation_explains` | 1 |
| 1148 | `{"file": identity, "header": header, "schema": schema, "tables": ta… -> ({'file'` | killed | `tests/test_sqlite_runner.py::test_attributed_probe_accepts_only_the_delta_its_operation_explains` | 1 |
| 1148 | `{"file": identity, "header": header, "schema": schema, "tables": ta… -> ({'heade` | killed | `tests/test_sqlite_runner.py::test_attributed_probe_accepts_only_the_delta_its_operation_explains` | 1 |

### `src/nemisis/sqlite_runner.py::_kill_and_wait`

5 mutants: 5 killed, 0 survived, 0 timed out.

| line | mutation | status | killed by / why it survives | s |
| ---: | -------- | ------ | --------------------------- | --: |
| 1503 | `raise _AttemptFailure(ExecutionStatus.KILL_ERROR, "process-group SI… -> pass` | killed | `tests/test_sqlite_runner.py::test_a_process_group_kill_that_fails_is_a_kill_error` | 8 |
| 1507 | `raise _AttemptFailure( ExecutionStatus.WAIT_ERROR, f"the killed wor… -> pass` | killed | `tests/test_sqlite_runner.py::test_a_killed_worker_that_is_not_reaped_names_its_budget` | 3 |
| 1511 | `-signal.SIGKILL -> (signal.SIGKILL)` | killed | `tests/test_sqlite_runner.py::test_buggy_fixture_duplicates_at_effect_commit` | 1 |
| 1511 | `return_code != -signal.SIGKILL -> (return_code == -signal.SIGKILL)` | killed | `tests/test_sqlite_runner.py::test_buggy_fixture_duplicates_at_effect_commit` | 1 |
| 1512 | `raise _AttemptFailure(ExecutionStatus.WAIT_ERROR, "worker did not e… -> pass` | killed | `tests/test_sqlite_runner.py::test_a_worker_that_exited_before_the_kill_landed_is_a_wait_error` | 3 |

### `src/nemisis/sqlite_runner.py::_xattrs`

24 mutants: 12 killed, 12 survived, 0 timed out.

| line | mutation | status | killed by / why it survives | s |
| ---: | -------- | ------ | --------------------------- | --: |
| 828 | `listxattr is not None -> (listxattr is None)` | killed | `tests/test_sqlite_runner.py::test_buggy_fixture_duplicates_at_effect_commit` | 1 |
| 829 | `return sorted(str(name) for name in listxattr(path, follow_symlinks… -> return N` | survived | **hole**: The `os.listxattr` door is dead on the macOS this run was made on but live on Linux and under a monkeypatched `os`; nothing asserts the names it returns or that it does not follow symlinks. Owed: tests/test_sqlite_runner.py::test_xattrs_answers_through_the_os_door_when_the_build_has_one (written by a refuter tonight; installs a fake `os.listxattr`, asserts sorted names and `follow_symlinks=False`) | 173 |
| 830 | `sys.platform != "darwin" -> (sys.platform == 'darwin')` | killed | `tests/test_sqlite_runner.py::test_xattrs_names_an_extended_attribute_that_was_set` | 3 |
| 831 | `return [] -> return None` | survived | **hole**: On a platform with neither door the fallback must be an empty listing; `None` makes `_stat_entry` crash with TypeError while pinning the world, a crash where a listing belongs. Owed: tests/test_sqlite_runner.py::test_a_world_entry_on_a_platform_with_neither_xattr_door_reads_as_having_none (written by a refuter tonight; clears `os.listxattr`, sets a third platform, expects an `_Entry` with no attributes) | 164 |
| 835 | `[ctypes.c_char_p, ctypes.c_char_p, ctypes.c_size_t, ctypes.c_int] -> ([ctypes.c_` | killed | `tests/test_sqlite_runner.py::test_buggy_fixture_duplicates_at_effect_commit` | 1 |
| 835 | `[ctypes.c_char_p, ctypes.c_char_p, ctypes.c_size_t, ctypes.c_int] -> ([ctypes.c_` | killed | `tests/test_sqlite_runner.py::test_buggy_fixture_duplicates_at_effect_commit` | 1 |
| 835 | `[ctypes.c_char_p, ctypes.c_char_p, ctypes.c_size_t, ctypes.c_int] -> ([ctypes.c_` | killed | `tests/test_sqlite_runner.py::test_buggy_fixture_duplicates_at_effect_commit` | 1 |
| 835 | `[ctypes.c_char_p, ctypes.c_char_p, ctypes.c_size_t, ctypes.c_int] -> ([ctypes.c_` | killed | `tests/test_sqlite_runner.py::test_buggy_fixture_duplicates_at_effect_commit` | 1 |
| 837 | `0 -> (-1)` | survived | **equivalent**: macOS `listxattr` ignores the buffer size when the name buffer is NULL and answers the byte count the names need, so 0, 1, and (size_t)-1 return the same size; measured on a file with one attribute and with none. | 159 |
| 837 | `0 -> (1)` | killed | `tests/test_verdict_paths.py::test_raw_sql_judge_handler_is_told_the_one_line_change` | 85 |
| 838 | `0 -> (-1)` | killed | `tests/test_sqlite_runner.py::test_xattrs_raises_instead_of_answering_for_a_path_it_cannot_read` | 3 |
| 838 | `0 -> (1)` | survived | **hole**: The same zero-size case raised as an error; see the row above. Owed: the same test as the row above | 155 |
| 838 | `size < 0 -> (size <= 0)` | survived | **hole**: A path with no extended attributes answers `OSError` with errno 0 instead of the empty list, and no caller catches it; every file a test stats carries none, yet none asserts the empty answer through the libc door. Owed: tests/test_sqlite_runner.py::test_xattrs_reads_a_file_with_no_attributes_through_the_libc_door_as_clean (a zero-attribute path through the libc door on any host, via a monkeypatched `ctypes`) | 165 |
| 839 | `raise OSError(ctypes.get_errno(), f"listxattr failed for {path}") -> pass` | killed | `tests/test_sqlite_runner.py::test_xattrs_raises_instead_of_answering_for_a_path_it_cannot_read` | 3 |
| 840 | `0 -> (-1)` | killed | `tests/test_verdict_paths.py::test_raw_sql_judge_handler_is_told_the_one_line_change` | 79 |
| 840 | `0 -> (1)` | survived | **hole**: `size == 1` never holds for a zero-attribute file, so the zero case falls through to a second `listxattr` syscall, and if the handler unlinked the path in between a clean file is reported as a failed read; on this macOS host every fresh file carries `com.apple.provenance`, so the zero-attribute path never ran under the suite; the owed test reaches it through a monkeypatched libc on any host. Owed: tests/test_sqlite_runner.py::test_xattrs_answers_a_zero_length_listing_without_reading_the_path_again | 163 |
| 840 | `size == 0 -> (size != 0)` | killed | `tests/test_sqlite_runner.py::test_xattrs_names_an_extended_attribute_that_was_set` | 3 |
| 841 | `return [] -> return None` | survived | **hole**: A zero-attribute file must answer the empty list; `None` makes `_stat_entry` crash with TypeError while pinning the world, a crash where a listing belongs; on this macOS host every fresh file carries `com.apple.provenance`, so the zero-attribute path never ran under the suite; the owed test reaches it through a monkeypatched libc on any host. Owed: tests/test_sqlite_runner.py::test_xattrs_reads_a_file_with_no_attributes_through_the_libc_door_as_clean | 168 |
| 844 | `0 -> (-1)` | survived | **hole**: `got < -1` lets a failed second call (it answers -1) fall through to decoding an unfilled buffer as attribute names instead of raising; no test makes the names call fail after the size call succeeded. Owed: tests/test_sqlite_runner.py::test_xattrs_tells_a_listing_that_shrank_apart_from_a_read_that_failed (a monkeypatched libc answers a positive size, then -1 with an errno; expects OSError) | 155 |
| 844 | `0 -> (1)` | survived | **hole**: `got < 1` raises for a second call that answers 0, the file whose attributes vanished between the two syscalls; a clean file reported as a failed read. Owed: the same unlink-between-calls test as line 840 | 155 |
| 844 | `got < 0 -> (got <= 0)` | survived | **hole**: The second syscall answers 0 only for a file whose attributes vanished between the two calls; the mutant raises for it instead of answering what was read, and on this macOS host every fresh file carries `com.apple.provenance`, so the zero-attribute path never ran under the suite; the owed test reaches it through a monkeypatched libc on any host. Owed: the same unlink-between-calls test as line 840 | 155 |
| 845 | `raise OSError(ctypes.get_errno(), f"listxattr failed for {path}") -> pass` | survived | **hole**: The names call's failure is swallowed and an unfilled buffer is decoded as attribute names; the same shape as the row above. Owed: the same test as the row above | 160 |
| 846 | `buffer.raw[:got] -> (buffer.raw)` | survived | **equivalent**: `create_string_buffer` hands back a zero-filled buffer and libc writes only the first `got` bytes, so decoding past `got` adds empty names that the `if name` filter already drops; a listing that shrank between the calls decodes the same. | 167 |
| 846 | `return sorted(name.decode("utf-8", "replace") for name in buffer.ra… -> return N` | killed | `tests/test_sqlite_runner.py::test_buggy_fixture_duplicates_at_effect_commit` | 1 |

