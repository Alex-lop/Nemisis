# Architecture

Nemisis has one authority path:

1. Strict Pydantic contracts bind the ticket, source tree, candidate patch, prompt, model,
   generated tests, runner, parser, worlds, executions, matrix, and artifact by SHA-256.
2. The model may emit claims and Python/pytest test files only. It cannot choose commands or mark
   an artifact accepted.
3. Patch and generated-file validators reject traversal, protected harness/config paths, binary
   or mode-changing patches, unsupported files, malformed tests, and exceeded count/size limits.
4. One canonical bundle contains base-owned regression tests, generated tests, the trusted pytest
   annotation plugin, runner argv/version, parser digest, and environment identity.
5. Local mode copies one prepared source into base and candidate directories. Live mode derives
   persistent base and candidate images from one common ConTree image.
6. Both worlds receive the same bundle. Pytest JUnit XML plus trusted per-test annotations
   distinguishes `PASS`, `ASSERTION_FAIL`, `ERROR`, `TIMEOUT`, and `NOT_RUN`.
7. Deterministic code builds the matrix and validates every receipt binding before writing an
   artifact receipt or report.

The CLI and generated HTML are projections of the same manifest. There is no database, queue,
repair loop, generic provider framework, or separate frontend.

## Important boundaries

- Local execution is restricted to the packaged fixture and is labelled `FIXTURE`.
- Live generated code executes only inside Token Factory Sandboxes with networking disabled.
- The live slice accepts only the immutable packaged fixture/candidate and AST-constrained
  generated tests. Arbitrary repositories require a provider-owned result channel that ConTree
  client 0.3.0 does not expose.
- Candidate repository tests and pytest configuration are never selected as acceptance evidence.
- ConTree image and operation UUIDs are provider evidence; mutable tags are rejected as root input.
- A finite bundle supports a claim only within its observed scope. Nemisis does not claim formal
  correctness, safety, or vulnerability freedom.
