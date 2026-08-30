from __future__ import annotations

from base64 import b64encode
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from types import EllipsisType

import pytest
from contree_client import (
    File,
    FileResponse,
    FileSpec,
    InstanceNetworking,
    InstanceResult,
    InstanceResultState,
    InstanceSpawnResponse,
    OperationInstanceMetadata,
    OperationResponse,
    OperationStatus,
    StreamRepr,
    WhoAmIResponse,
)

from nemisis.contree import (
    BUNDLE_ARCHIVE,
    ContreeBackend,
    ContreeConfigurationError,
    ContreeExecution,
    ContreeExecutionError,
    ContreeProtocolError,
)
from nemisis.hashing import sha256_bytes


@dataclass(frozen=True)
class SpawnCall:
    command: str
    image: str
    disposable: bool
    args: tuple[str, ...]
    shell: bool
    env: dict[str, str]
    cwd: str
    networking: InstanceNetworking
    timeout: int
    truncate_output_at: int
    files: dict[str, FileSpec]


class FakeClient:
    def __init__(self) -> None:
        self.calls: list[SpawnCall] = []
        self.status = OperationStatus.SUCCESS
        self.problem: str | None = None
        self.wait_error: Exception | None = None
        self.upload_mismatch = False
        self.upload_size_unknown = False
        self.permissions = {"spawn": True}

    def whoami(self) -> WhoAmIResponse:
        return WhoAmIResponse("token-id", None, self.permissions, {})

    def ensure_file(self, content: bytes, *, sha256: str | None = None) -> FileResponse | File:
        digest = "0" * 64 if self.upload_mismatch else sha256_bytes(content)
        return FileResponse("file-id", digest, -1 if self.upload_size_unknown else len(content))

    def spawn_instance(
        self,
        command: str,
        image: str,
        *,
        disposable: bool,
        args: list[str],
        shell: bool,
        env: dict[str, str],
        cwd: str,
        networking: InstanceNetworking,
        timeout: int,
        truncate_output_at: int,
        files: dict[str, FileSpec],
    ) -> InstanceSpawnResponse:
        self.calls.append(
            SpawnCall(
                command,
                image,
                disposable,
                tuple(args),
                shell,
                env,
                cwd,
                networking,
                timeout,
                truncate_output_at,
                files,
            )
        )
        return InstanceSpawnResponse(uuid=f"operation-{len(self.calls)}")

    def wait_operation(
        self, operation_id: str, *, timeout: float | None = None
    ) -> OperationResponse:
        if self.wait_error is not None:
            raise self.wait_error
        call = self.calls[-1]
        result = InstanceResult(
            state=InstanceResultState(exit_code=7, timed_out=self.problem == "timeout"),
            stdout=StreamRepr("NEBIUS_API_KEY=private output", "ascii", False),
            stderr=StreamRepr("ordinary error", "ascii", False),
        )
        metadata: OperationInstanceMetadata | EllipsisType = OperationInstanceMetadata(
            command=call.command,
            image=call.image,
            disposable=call.disposable,
            args=list(call.args),
            shell=call.shell,
            env=call.env,
            cwd=call.cwd,
            networking=call.networking,
            timeout=call.timeout,
            truncate_output_at=call.truncate_output_at,
            files=call.files,
            result=... if self.problem == "result" else result,
        )
        if self.problem == "metadata":
            metadata = ...
        result_image: str | None | EllipsisType = f"image-{len(self.calls)}"
        if self.problem == "image":
            result_image = None
        return OperationResponse(
            uuid=operation_id,
            kind="instance",
            status=self.status,
            created_at="2026-08-30T12:00:00Z",
            duration=1.25,
            image_size=100,
            consumed_cpu=0.5,
            consumed_memory=2048,
            image_uuid="wrong-image" if self.problem == "source" else call.image,
            result_image_uuid=result_image,
            metadata=metadata,
        )


def test_persistent_lineage_and_same_fixed_runner_accept_nonzero_exit() -> None:
    client = FakeClient()
    backend = ContreeBackend(client, timeout=9)
    backend.check_capability()
    source = backend.upload_file(b"source")
    patch = backend.upload_file(b"patch")
    bundle = backend.upload_file(b"bundle")

    common = backend.prepare_common("root-image", source)
    base = backend.derive_base(common.result_image_uuid)
    candidate = backend.derive_candidate(common.result_image_uuid, patch)
    base_run = backend.execute_bundle(base.result_image_uuid, bundle)
    candidate_run = backend.execute_bundle(candidate.result_image_uuid, bundle)

    assert client.calls[1].image == client.calls[2].image == common.result_image_uuid
    base_call, candidate_call = client.calls[-2:]
    assert base_call.command == candidate_call.command
    assert base_call.args == candidate_call.args
    assert (
        base_call.files
        == candidate_call.files
        == {BUNDLE_ARCHIVE: FileSpec(uuid=bundle.uuid, mode="0444")}
    )
    assert all(not call.disposable and not call.shell for call in client.calls)
    assert all(call.networking.enabled is False for call in client.calls)
    assert base_run.exit_code == candidate_run.exit_code == 7
    assert base_run.stdout == "NEBIUS_API_KEY=[REDACTED] output"
    assert base_run.ended_at is not None
    assert dict(base_run.metrics) == {
        "image_size": 100,
        "consumed_cpu": 0.5,
        "consumed_memory": 2048,
    }


@pytest.mark.parametrize("problem", ["metadata", "result", "image", "source", "timeout"])
def test_missing_operation_evidence_fails_closed(problem: str) -> None:
    client = FakeClient()
    client.problem = problem
    error = ContreeExecutionError if problem == "timeout" else ContreeProtocolError
    with pytest.raises(error):
        ContreeBackend(client).derive_base("common-image")


def test_infrastructure_failure_is_not_a_process_result() -> None:
    client = FakeClient()
    client.status = OperationStatus.FAILED
    with pytest.raises(ContreeExecutionError, match="infrastructure status FAILED"):
        ContreeBackend(client).derive_base("common-image")


def test_transport_timeout_is_sanitized() -> None:
    client = FakeClient()
    client.wait_error = TimeoutError("secret provider detail")
    with pytest.raises(
        ContreeExecutionError,
        match=r"operation operation-1 request failed \(TimeoutError\)$",
    ) as raised:
        ContreeBackend(client).derive_base("common-image")
    assert "secret provider detail" not in str(raised.value)


def test_upload_and_capability_receipts_fail_closed() -> None:
    client = FakeClient()
    client.upload_mismatch = True
    with pytest.raises(ContreeProtocolError, match="does not match"):
        ContreeBackend(client).upload_file(b"bundle")

    client.upload_mismatch = False
    client.upload_size_unknown = True
    assert ContreeBackend(client).upload_file(b"bundle").size == -1

    client.permissions = {"spawn": False}
    with pytest.raises(ContreeConfigurationError, match="persistent spawn"):
        ContreeBackend(client).check_capability()


def test_missing_profile_names_safe_setup_without_secrets(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("CONTREE_PROFILE", raising=False)
    monkeypatch.setenv("CONTREE_HOME", str(tmp_path))
    with pytest.raises(ContreeConfigurationError) as raised:
        ContreeBackend.from_profile()
    message = str(raised.value)
    assert "CONTREE_PROFILE" in message
    assert "~/.config/contree/auth.ini" in message


def test_extracts_bound_tree_and_junit_evidence() -> None:
    report = b"<testsuite />"
    execution = ContreeExecution(
        operation_id="operation",
        source_image_uuid="source",
        result_image_uuid="result",
        started_at=datetime.now(UTC),
        ended_at=datetime.now(UTC),
        duration_seconds=1,
        exit_code=0,
        stdout=(
            f"NEMISIS_TREE_SHA256={'a' * 64}\nNEMISIS_JUNIT_BASE64={b64encode(report).decode()}"
        ),
        stderr="",
        metrics=(),
    )
    assert ContreeBackend.tree_digest(execution) == "a" * 64
    assert ContreeBackend.junit_xml(execution) == report

    assert execution.stdout is not None
    forged = ContreeExecution(
        **{
            **execution.__dict__,
            "stdout": execution.stdout + f"\nNEMISIS_JUNIT_BASE64={b64encode(report).decode()}",
        }
    )
    with pytest.raises(ContreeProtocolError, match="one JUnit"):
        ContreeBackend.junit_xml(forged)

    malformed = ContreeExecution(**{**execution.__dict__, "stdout": "NEMISIS_JUNIT_BASE64=!"})
    with pytest.raises(ContreeProtocolError, match="malformed JUnit"):
        ContreeBackend.junit_xml(malformed)
