# Nemotron + Nebius live runbook

Verified against official documentation and the installed source on 2026-08-30. This runbook does
not claim that a provider call or Sandbox run occurred.

## Current provider facts

| Surface | Current fact | Nemisis binding |
| --- | --- | --- |
| Token Factory API | OpenAI-compatible API; the official quickstart uses `https://api.tokenfactory.nebius.com/v1/` and `NEBIUS_API_KEY`. [Quickstart](https://docs.tokenfactory.nebius.com/quickstart) | Default endpoint and credential in [`nemotron.py`](../src/nemisis/nemotron.py). Only official global or regional Nebius HTTPS `/v1` URLs are accepted. |
| Nemotron | The official cookbook currently documents `nvidia/nemotron-3-super-120b-a12b` at the regional `https://api.tokenfactory.us-central1.nebius.com/v1/` endpoint and says it supports structured output. [Nemotron guide](https://github.com/nebius/token-factory-cookbook/blob/main/models/nemotron/nemotron3-super-120B.md) | Exact default model ID. A live run first requires that exact ID to be active, `text->text`, and JSON-schema capable in the authenticated catalog. |
| Model availability | `GET /v1/models` is authenticated and returns the models currently available to the caller. [List models API](https://docs.tokenfactory.nebius.com/api-reference/models/list-models) | The adapter requests the verbose catalog before generation and fails closed if the configured model or capabilities are absent. The 2026-08-31 deprecation notice recommends this Nemotron ID as a replacement; it does not list it for removal. [August 2026 notice](https://docs.tokenfactory.nebius.com/august-2026-deprecation-notice) |
| Structured output | Token Factory supports `response_format.type=json_schema`; support remains model-specific and should be checked in the model card/catalog. [Structured output](https://docs.tokenfactory.nebius.com/ai-models-inference/json) | Both Nemisis model calls send a strict Pydantic JSON schema, then validate the returned bytes again locally. |
| Sandbox auth | The documented SDK takes an already authenticated `contree_client`; profile resolution is explicit profile, `CONTREE_PROFILE`, then the active profile in `$CONTREE_HOME/auth.ini` (normally `~/.config/contree/auth.ini`). [SDK getting started](https://docs.tokenfactory.nebius.com/sandboxes/sdk/python_sdk/getting-started) | Token Factory and Sandbox credentials are separate. Candidate input cannot select either credential or endpoint. |
| Sandbox state | Images are immutable UUID-addressed filesystem states; tags can move. A non-disposable run can create a new image, and several children can branch from one parent state. [Core concepts](https://docs.tokenfactory.nebius.com/sandboxes/mcp/concepts/core), [branching](https://docs.tokenfactory.nebius.com/sandboxes/sdk/python_sdk/branching) | Nemisis requires an input UUID, preserves the common/base/candidate lineage, and rejects changed source/result image identities. |
| Concurrent operations | The documented async pattern launches independent operations, retains every operation ID, then waits for all of them. [Parallel tasks](https://docs.tokenfactory.nebius.com/sandboxes/mcp/prompts/parallel-tasks) | `ContreeBackend.execute_many` submits the complete validated batch before waiting for every started operation. No account concurrency limit has been measured here. |
| Operation evidence | Operation status can include operation UUID/status, timestamps/duration, source/result image UUIDs, request metadata, process result, and resource measurements. [Operation status](https://docs.tokenfactory.nebius.com/api-reference/sandboxes/operations/get-an-operation-status) | The adapter verifies the fixed request metadata and records bounded, redacted stdout/stderr, exit code, operation/image identities, duration, and available CPU/memory/image-size metrics. |
| Crash primitives | The Sandbox API documents spawning another process in a running instance, reading its terminal process result, and sending a signal to its process group; omitted signal means `SIGKILL`. [Subprocess result](https://docs.tokenfactory.nebius.com/api-reference/sandboxes/operation/result-of-one-subprocess-reconstructed-from-its-events), [kill subprocess](https://docs.tokenfactory.nebius.com/api-reference/sandboxes/operation/kill-one-subprocess) | Installed `contree-client==0.3.0` exposes these low-level methods, but CrashCheck has not wired them into a live transport. Provider capability is not product integration. |

The repository currently installs `openai==2.54.0` and `contree-client[httpx]==0.3.0`; the
high-level `contree_sdk` shown in current provider documentation is not installed. The live
differential adapter uses the synchronous low-level client directly. That installed client defaults
to `https://api.tokenfactory.nebius.com/sandboxes`, while a saved profile can select its authenticated
service configuration. Revalidate request/receipt compatibility against a real account before
changing that seam; do not infer it from mocked tests. See [`pyproject.toml`](../pyproject.toml),
[`uv.lock`](../uv.lock), and [`contree.py`](../src/nemisis/contree.py).

## What Nemisis can run live today

CrashCheck has two live model calls, and both need only `NEBIUS_API_KEY`. The load-bearing one has
Nemotron write the patch that CrashCheck then crash-tests (the receipt lands inside the candidate
tree and in the check report as its author):

```bash
uv run nemisis propose-patch --issue src/nemisis/fixtures/sqlite_credit_v1/issue.md \
  --base fixture:sqlite-credit-v1/buggy --out ./nemotron-candidate
uv run nemisis check --base fixture:sqlite-credit-v1/buggy --candidate ./nemotron-candidate
```

The other is the candidate-blind contract proposal; its receipt is labelled `LIVE`, stored beside
the contract, and carried into the next `check` manifest and report:

```bash
uv run nemisis init --issue src/nemisis/fixtures/sqlite_credit_v1/issue.md \
  --target app.credits:apply_credit --base fixture:sqlite-credit-v1/buggy \
  --scenario sqlite-credit-v1 --nemotron
```

Without the key it exits `2` and drafts nothing. A proposal that omits the audited fault intent or
proposes a different `amount_cents` also exits `2` and prints the model's values.

The original packaged `idempotency-retry` differential verifier is the only path connected to
ConTree end to end:

```bash
uv run nemisis verify --fixture idempotency-retry --mode live
```

That path performs one Nemotron structured-output call, uploads the exact source/patch/bundle,
creates persistent common, base, and candidate image states, runs the same bounded test bundle in
both worlds with networking disabled, and validates returned operation metadata and JUnit coverage.
The JUnit file is produced inside the guest and transported through bounded stdout; it is not a
provider-owned test attestation. See [`live.py`](../src/nemisis/live.py) and
[`contree.py`](../src/nemisis/contree.py).

The Nemotron receipt stores the truth label, timestamp, endpoint region, model ID, prompt/input and
response digests, latency, outcome, and schema-valid flag. It does not publish the API key or raw
provider response. ConTree errors are sanitized and stream text is bounded and secret-redacted.

## Immutable root-image contract

Set `NEMISIS_CONTREE_ROOT_IMAGE` to an accessible image **UUID**, never a tag. The image must provide:

- `/bin/sh`, `/bin/tar`, and `/usr/bin/env`;
- `python` on the fixed system `PATH` with importable `pytest`;
- `git` on that path; and
- a filesystem on which `/workspace` can be created.

UUIDs identify immutable images while tags may be reassigned. [Core concepts](https://docs.tokenfactory.nebius.com/sandboxes/mcp/concepts/core) Nemisis also sends fixed command/argument arrays, disables networking, bounds output and time, uploads content-addressed files, and requires the completed operation to report the requested source image and a result image UUID. The provider documents that spawning an instance returns an operation ID and that non-disposable execution saves state. [Spawn instance](https://docs.tokenfactory.nebius.com/api-reference/sandboxes/instances/spawn-a-new-container-instance)

## Probes

### 1. Secret-free local readiness

```bash
uv run nemisis doctor --mode live --json
```

`doctor` checks only local prerequisites, credential presence, profile-file presence, UUID syntax,
and whether CrashCheck has a provider transport. It does not authenticate, inspect the image, list
the live model catalog, or spend provider resources.

### 2. Authenticated model/catalog probe

This prints only public catalog metadata. It must find the exact configured model with active text
and structured-output capabilities before any live claim is allowed.

```bash
uv run python - <<'PY'
import os
from openai import OpenAI

base_url = os.getenv(
    "NEMISIS_TOKEN_FACTORY_BASE_URL",
    "https://api.tokenfactory.nebius.com/v1/",
)
model_id = os.getenv("NEMISIS_MODEL_ID", "nvidia/nemotron-3-super-120b-a12b")
client = OpenAI(base_url=base_url, api_key=os.environ["NEBIUS_API_KEY"], timeout=30)
catalog = client.models.list(extra_query={"verbose": True}, timeout=30)
model = next((item for item in catalog.data if item.id == model_id), None)
assert model is not None, f"missing model: {model_id}"
document = model.model_dump()
features = {
    str(value).strip().lower().replace("-", "_").replace(" ", "_")
    for value in document.get("supported_features", ())
}
assert document.get("status") == "active"
assert document.get("architecture", {}).get("modality") == "text->text"
assert features & {"json_schema", "structured_output", "structured_outputs"}
print({key: document.get(key) for key in ("id", "status", "supported_features")})
PY
```

Billable schema smoke, using the same bounded adapter and the real product path:

```bash
uv run nemisis init --issue src/nemisis/fixtures/sqlite_credit_v1/issue.md \
  --target app.credits:apply_credit --base fixture:sqlite-credit-v1/buggy \
  --scenario sqlite-credit-v1 --nemotron --json
```

This proves a current structured-output call and a receipted, accepted proposal. It does not prove a
Sandbox run or a CrashCheck live transport.

### 3. Authenticated profile and immutable-image probe

This starts one disposable, network-disabled Sandbox operation and may consume provider resources.
It prints identities and status, never the profile token.

```bash
uv run python - <<'PY'
import os
import uuid
from contree_client import (
    InstanceNetworking,
    InstanceResult,
    InstanceResultState,
    OperationInstanceMetadata,
    OperationStatus,
)
from contree_client.httpx import ContreeClient

root = os.environ["NEMISIS_CONTREE_ROOT_IMAGE"]
uuid.UUID(root)
with ContreeClient.from_profile(timeout=90) as client:
    identity = client.whoami()
    assert identity.permissions.get("spawn") is True
    image = client.inspect_image(root)
    assert image.uuid == root
    probe = client.spawn_instance(
        "/bin/sh",
        root,
        disposable=True,
        args=[
            "-cu",
            "test -x /bin/tar; test -x /usr/bin/env; "
            "command -v python; command -v git; "
            "python -I -c 'import pytest, sqlite3'",
        ],
        shell=False,
        env={"PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"},
        cwd="/workspace",
        networking=InstanceNetworking(enabled=False),
        timeout=60,
        truncate_output_at=20_000,
        files={},
    )
    assert isinstance(probe.uuid, str) and probe.uuid
    completed = client.wait_operation(probe.uuid, timeout=90)
    assert completed.status is OperationStatus.SUCCESS
    assert completed.image_uuid == root
    assert isinstance(completed.uuid, str) and completed.uuid
    assert isinstance(completed.metadata, OperationInstanceMetadata)
    assert isinstance(completed.metadata.result, InstanceResult)
    assert isinstance(completed.metadata.result.state, InstanceResultState)
    assert completed.metadata.result.state.exit_code == 0
    print({
        "operation_id": completed.uuid,
        "source_image_uuid": completed.image_uuid,
        "status": completed.status.value,
    })
PY
```

After all probes pass, run the supported live verifier and retain its sanitized `manifest.json` and
`report.html`. A failed probe must remain `BLOCKED`; never substitute local output or relabel a mock.

## Current blockers

The command `uv run nemisis doctor --mode live --json` returned `BLOCKED` on 2026-08-30:

- local Python 3.12, POSIX process groups/`SIGKILL`, and SQLite WAL/`FULL` probes passed;
- `NEBIUS_API_KEY` was absent (rechecked 2026-09-03), so the authenticated model catalog, the
  structured call, and therefore the `init --nemotron` proposal receipt were not run;
- no ConTree profile was found, so authentication, `whoami`, uploads, spawns, and operation receipts
  were not run;
- `NEMISIS_CONTREE_ROOT_IMAGE` was absent, so no immutable image or required binaries were inspected;
  and
- CrashCheck's provider transport is unimplemented and therefore remains blocked even if all three
  external prerequisites are supplied.

Consequently there is no current-tree Nemotron receipt, Sandbox operation/image identity, provider
latency or cost measurement, or `LIVE`/`RECORDED_LIVE` CrashCheck evidence. CrashCheck's exact next
provider slice is to connect its existing capsule and receipt rules to the documented subprocess
spawn/result/process-group-kill operations, then prove the flow against one accessible immutable
image. Until that code and a genuine run exist, `nemisis check --mode live` must stay incomplete.
