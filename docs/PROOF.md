# Proof ledger

| Capability | Status | Evidence |
| --- | --- | --- |
| Strict domain and digest bindings | `VERIFIED_LOCAL` | The full test suite and manifest validation |
| Safe patch/generated-file boundaries | `VERIFIED_LOCAL` | Safety and adapter contract tests |
| Differential fixture worlds | `VERIFIED_LOCAL` | Real temporary filesystems and subprocesses |
| Immutable full-bundle equality | `VERIFIED_LOCAL` | Matching bundle digest on both world/execution receipts |
| Expected incomplete-candidate matrix | `VERIFIED_LOCAL` | `2 PASS/PASS`, `ASSERTION_FAIL/PASS`, `ASSERTION_FAIL/ASSERTION_FAIL` |
| Token Factory Nemotron adapter | `MOCKED_TEST_ONLY` | Structured-output/error contract tests |
| Genuine current-tree Nemotron call | `BLOCKED` | `NEBIUS_API_KEY` missing |
| ConTree persistent-world adapter | `MOCKED_TEST_ONLY` | Official-client operation contract tests |
| Genuine current-tree ConTree run | `BLOCKED` | Profile and immutable root image not configured |
| Provider-owned result channel for arbitrary repositories | `NOT_PROVEN` | ConTree 0.3.0 exposes guest-written files/stdout; first slice is packaged-fixture-only |
| Bounded repair | `NOT_PROVEN` | Conditional milestone intentionally not started |
| FastAPI judge surface | `NOT_PROVEN` | Static HTML report covers the first-run surface |
| Hosted demo and video | `NOT_PROVEN` | Requires a genuine live run first |

No fixture, mock, or historical result is represented as live evidence.

Latest verified source: `03b58607add660c9da470488eacd74189c34c6c3`. Latest local bundle:
`70e10c52e50c143b526af020c37aee2ee4bce0da85453bb1470d42736895b725`.
