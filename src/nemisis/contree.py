"""Narrow live adapter for persistent Token Factory Sandbox worlds."""

from __future__ import annotations

import configparser
import os
import re
from base64 import b64decode
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from types import EllipsisType
from typing import Protocol, Self

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
    ProfileError,
    StreamRepr,
    WhoAmIResponse,
    parse_datetime,
)
from contree_client.exceptions import ContreeError
from contree_client.httpx import ContreeClient

from nemisis.bundle import RUNNER_ARGV
from nemisis.hashing import sha256_bytes
from nemisis.junit import MAX_JUNIT_BYTES

DEFAULT_TIMEOUT_SECONDS = 300.0
INSTANCE_TIMEOUT_SECONDS = 240
MAX_STREAM_BYTES = 1_000_000
EXECUTION_NONCE_ENV = "NEMISIS_EXECUTION_NONCE"
WORKSPACE = "/workspace"
SOURCE_ARCHIVE = "/opt/nemisis/source.tar.gz"
CANDIDATE_PATCH = "/opt/nemisis/candidate.patch"
BUNDLE_ARCHIVE = "/opt/nemisis/verification-bundle.tar.gz"
_PATH = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
_ENV = {"PATH": _PATH, "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"}
_PREPARE_COMMAND = "/bin/tar"
_PREPARE_ARGS = (
    "--extract",
    "--gzip",
    "--file",
    SOURCE_ARCHIVE,
    "--directory",
    WORKSPACE,
    "--no-same-owner",
    "--no-same-permissions",
)
_TREE_CODE = (
    "import hashlib,json,pathlib,sys;"
    "root=pathlib.Path(sys.argv[1]);"
    "ignored=set(sys.argv[2:]);"
    "paths=sorted((p for p in root.rglob('*') if p.is_file() and "
    "p.relative_to(root).parts[0] not in ignored),"
    "key=lambda p:p.relative_to(root).as_posix());"
    "assert all(not p.is_symlink() for p in paths);"
    "entries=[{'path':p.relative_to(root).as_posix(),'sha256':"
    "hashlib.sha256(p.read_bytes()).hexdigest()} for p in paths];"
    "data=json.dumps(entries,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode();"
    "print('NEMISIS_TREE_SHA256='+hashlib.sha256(data).hexdigest())"
)
_BASE_COMMAND = "/usr/bin/env"
_BASE_ARGS = ("python", "-I", "-c", _TREE_CODE, WORKSPACE)
_CANDIDATE_COMMAND = "/usr/bin/env"
_CANDIDATE_CODE = (
    "import subprocess;"
    f"subprocess.run(['git','apply','--whitespace=nowarn',{CANDIDATE_PATCH!r}],"
    f"cwd={WORKSPACE!r},check=True);" + _TREE_CODE
)
_CANDIDATE_ARGS = ("python", "-I", "-c", _CANDIDATE_CODE, WORKSPACE)
_RUNNER_COMMAND = "/bin/sh"
_JUNIT_CODE = (
    "import base64,pathlib;"
    "p=pathlib.Path('/workspace/__nemisis_results__/junit.xml');"
    "print('NEMISIS_JUNIT_BASE64='+base64.b64encode(p.read_bytes()).decode())"
)
_RUNNER_SHELL = """\
rm -rf /workspace/__nemisis_bundle__ /workspace/__nemisis_results__
mkdir -p /workspace/__nemisis_bundle__ /workspace/__nemisis_results__
archive_sha=$(
  python -I -c \
    'import hashlib,sys;print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())' \
    /opt/nemisis/verification-bundle.tar.gz
)
[ "$archive_sha" = "$1" ] || { echo NEMISIS_BUNDLE_ERROR=archive-digest; exit 4; }
tar --extract --gzip --file /opt/nemisis/verification-bundle.tar.gz \
  --directory /workspace/__nemisis_bundle__ --no-same-owner --no-same-permissions
before=$(python -I -c "$3" /workspace/__nemisis_bundle__)
source_before=$(python -I -c "$3" /workspace __nemisis_bundle__ __nemisis_results__)
cd /workspace
python -I -c "$2"
status=$?
after=$(python -I -c "$3" /workspace/__nemisis_bundle__)
source_after=$(python -I -c "$3" /workspace __nemisis_bundle__ __nemisis_results__)
[ "$before" = "$after" ] || { echo NEMISIS_BUNDLE_ERROR=mutated; exit 4; }
[ "$source_before" = "$source_after" ] || { echo NEMISIS_BUNDLE_ERROR=source-mutated; exit 4; }
if [ -f /workspace/__nemisis_results__/junit.xml ]; then
  python -I -c "$4"
fi
exit "$status"
"""
if RUNNER_ARGV[:3] != ("python", "-m", "pytest"):
    raise RuntimeError("unsupported trusted runner")
_RUNNER_CODE = (
    "import sys;sys.dont_write_bytecode=True;"
    f"sys.path[:0]=[{WORKSPACE + '/__nemisis_bundle__/harness'!r},{WORKSPACE!r}];"
    "import pytest;"
    f"raise SystemExit(pytest.main({list(RUNNER_ARGV[3:])!r}))"
)
_JUNIT_PREFIX = "NEMISIS_JUNIT_BASE64="
_TREE_PREFIX = "NEMISIS_TREE_SHA256="
_NETWORKING = InstanceNetworking(enabled=False)
_SECRET = re.compile(
    r"(?i)((?:[A-Z0-9_-]*(?:authorization|api[_-]?key|password|secret|token)"
    r"[A-Z0-9_-]*)\s*[:=]\s*|bearer\s+)\S+"
)
_EXECUTION_NONCE = re.compile(r"[0-9a-f]{32}")


class ContreeBackendError(RuntimeError):
    """A sanitized live-backend failure."""


class ContreeConfigurationError(ContreeBackendError):
    """The local ConTree profile is unavailable or invalid."""


class ContreeProtocolError(ContreeBackendError):
    """ConTree returned incomplete or contradictory operation evidence."""


class ContreeExecutionError(ContreeBackendError):
    """ConTree infrastructure failed before a valid process result existed."""


class ContreeBatchError(ContreeExecutionError):
    """A batch failed after zero or more provider operations were started."""

    def __init__(self, message: str, *, operation_ids: tuple[str, ...]) -> None:
        super().__init__(message)
        self.operation_ids = operation_ids
        self.started_operation_ids = operation_ids


@dataclass(frozen=True)
class UploadedFile:
    uuid: str
    sha256: str
    size: int


@dataclass(frozen=True)
class ContreeExecution:
    operation_id: str
    source_image_uuid: str
    result_image_uuid: str
    started_at: datetime
    ended_at: datetime | None
    duration_seconds: float | None
    exit_code: int
    stdout: str | None
    stderr: str | None
    metrics: tuple[tuple[str, int | float], ...]
    execution_nonce: str | None = None


@dataclass(frozen=True)
class ContreeInvocation:
    """One fixed, nonce-bound ConTree process invocation."""

    image_uuid: str
    command: str
    args: tuple[str, ...]
    files: Mapping[str, FileSpec]
    execution_nonce: str

    def __post_init__(self) -> None:
        _prepare_invocation(self)


@dataclass(frozen=True)
class _PreparedInvocation:
    image_uuid: str
    command: str
    args: tuple[str, ...]
    files: dict[str, FileSpec]
    execution_nonce: str
    env: dict[str, str]


class _Client(Protocol):
    def whoami(self) -> WhoAmIResponse: ...

    def ensure_file(self, content: bytes, *, sha256: str | None = None) -> FileResponse | File: ...

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
    ) -> InstanceSpawnResponse: ...

    def wait_operation(
        self, operation_id: str, *, timeout: float | None = None
    ) -> OperationResponse: ...


class ContreeBackend:
    """Execute only Nemisis-owned commands in persistent ConTree images."""

    def __init__(self, client: _Client, *, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> None:
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        self._client = client
        self._timeout = timeout

    @classmethod
    def from_profile(cls, *, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> Self:
        auth_file = _auth_file()
        if not os.environ.get("CONTREE_PROFILE") and not auth_file.is_file():
            raise ContreeConfigurationError(
                "ConTree authentication is not configured: CONTREE_PROFILE is unset "
                "and ~/.config/contree/auth.ini is missing"
            )
        try:
            client = ContreeClient.from_profile(timeout=timeout)
            backend = cls(client, timeout=timeout)
            backend.check_capability()
            return backend
        except (ProfileError, configparser.Error, ValueError):
            raise ContreeConfigurationError(
                "ConTree profile could not be loaded; set CONTREE_PROFILE to a profile "
                "configured in ~/.config/contree/auth.ini"
            ) from None
        except (ContreeError, TimeoutError) as exc:
            raise _request_error(exc) from None

    def check_capability(self) -> None:
        try:
            identity = self._client.whoami()
        except (ContreeError, TimeoutError) as exc:
            raise _request_error(exc) from None
        if (
            not isinstance(identity.token_uuid, str)
            or not identity.token_uuid.strip()
            or not isinstance(identity.permissions, dict)
            or not identity.permissions.get("spawn", False)
        ):
            raise ContreeConfigurationError(
                "ConTree profile is authenticated but lacks persistent spawn permission"
            )

    def upload_file(self, content: bytes) -> UploadedFile:
        digest = sha256_bytes(content)
        try:
            uploaded = self._client.ensure_file(content, sha256=digest)
        except (ContreeError, TimeoutError) as exc:
            raise _request_error(exc) from None
        uuid = _required_text(uploaded.uuid, "uploaded file UUID")
        if uploaded.sha256 != digest or uploaded.size not in {-1, len(content)}:
            raise ContreeProtocolError("ConTree file receipt does not match uploaded bytes")
        return UploadedFile(uuid=uuid, sha256=uploaded.sha256, size=uploaded.size)

    def prepare_common(self, root_image_uuid: str, source: UploadedFile) -> ContreeExecution:
        return self._run(
            image_uuid=root_image_uuid,
            command=_PREPARE_COMMAND,
            args=_PREPARE_ARGS,
            files={SOURCE_ARCHIVE: FileSpec(uuid=source.uuid, mode="0444")},
        )

    def derive_base(self, common_image_uuid: str) -> ContreeExecution:
        return self._run(
            image_uuid=common_image_uuid,
            command=_BASE_COMMAND,
            args=_BASE_ARGS,
            files={},
        )

    def derive_candidate(self, common_image_uuid: str, patch: UploadedFile) -> ContreeExecution:
        return self._run(
            image_uuid=common_image_uuid,
            command=_CANDIDATE_COMMAND,
            args=_CANDIDATE_ARGS,
            files={CANDIDATE_PATCH: FileSpec(uuid=patch.uuid, mode="0444")},
        )

    def execute_bundle(self, world_image_uuid: str, bundle: UploadedFile) -> ContreeExecution:
        return self._run(
            image_uuid=world_image_uuid,
            command=_RUNNER_COMMAND,
            args=(
                "-cu",
                _RUNNER_SHELL,
                "nemisis-runner",
                bundle.sha256,
                _RUNNER_CODE,
                _TREE_CODE,
                _JUNIT_CODE,
            ),
            files={BUNDLE_ARCHIVE: FileSpec(uuid=bundle.uuid, mode="0444")},
        )

    def execute_many(
        self, invocations: Sequence[ContreeInvocation]
    ) -> tuple[ContreeExecution, ...]:
        """Submit the whole validated batch before awaiting every started operation."""
        prepared = tuple(_prepare_invocation(invocation) for invocation in invocations)
        nonces = [invocation.execution_nonce for invocation in prepared]
        if len(nonces) != len(set(nonces)):
            raise ValueError("execution nonces must be unique within a batch")

        started: list[tuple[_PreparedInvocation, str]] = []
        submit_failure: ContreeBackendError | None = None
        for invocation in prepared:
            try:
                operation_id = self._submit(
                    image_uuid=invocation.image_uuid,
                    command=invocation.command,
                    args=invocation.args,
                    files=invocation.files,
                    env=invocation.env,
                )
            except ContreeBackendError as exc:
                submit_failure = exc
                break
            started.append((invocation, operation_id))

        executions: list[ContreeExecution] = []
        completion_failures: list[ContreeBackendError] = []
        for invocation, operation_id in started:
            try:
                executions.append(
                    self._await_operation(
                        operation_id=operation_id,
                        image_uuid=invocation.image_uuid,
                        command=invocation.command,
                        args=invocation.args,
                        files=invocation.files,
                        env=invocation.env,
                        execution_nonce=invocation.execution_nonce,
                    )
                )
            except ContreeBackendError as exc:
                completion_failures.append(exc)

        operation_ids = tuple(operation_id for _, operation_id in started)
        if submit_failure is not None or completion_failures:
            phase = "submission" if submit_failure is not None else "completion"
            raise ContreeBatchError(
                f"ConTree batch {phase} failed; all started operations were awaited",
                operation_ids=operation_ids,
            ) from None
        return tuple(executions)

    @staticmethod
    def tree_digest(execution: ContreeExecution) -> str:
        values = _sentinels(execution.stdout, _TREE_PREFIX)
        if len(values) != 1 or not re.fullmatch(r"[0-9a-f]{64}", values[0]):
            raise ContreeProtocolError("ConTree world did not return one valid tree digest")
        return values[0]

    @staticmethod
    def junit_xml(execution: ContreeExecution) -> bytes:
        values = _sentinels(execution.stdout, _JUNIT_PREFIX)
        if len(values) != 1:
            raise ContreeProtocolError("ConTree runner did not return one JUnit report")
        try:
            report = b64decode(values[0], validate=True)
        except ValueError as exc:
            raise ContreeProtocolError("ConTree runner returned malformed JUnit data") from exc
        if not report or len(report) > MAX_JUNIT_BYTES:
            raise ContreeProtocolError("ConTree JUnit report is empty or oversized")
        return report

    def _run(
        self,
        *,
        image_uuid: str,
        command: str,
        args: tuple[str, ...],
        files: dict[str, FileSpec],
    ) -> ContreeExecution:
        _required_text(image_uuid, "source image UUID")
        operation_id = self._submit(
            image_uuid=image_uuid,
            command=command,
            args=args,
            files=files,
            env=dict(_ENV),
        )
        return self._await_operation(
            operation_id=operation_id,
            image_uuid=image_uuid,
            command=command,
            args=args,
            files=files,
            env=dict(_ENV),
            execution_nonce=None,
        )

    def _submit(
        self,
        *,
        image_uuid: str,
        command: str,
        args: tuple[str, ...],
        files: dict[str, FileSpec],
        env: dict[str, str],
    ) -> str:
        try:
            started = self._client.spawn_instance(
                command,
                image_uuid,
                disposable=False,
                args=list(args),
                shell=False,
                env=env,
                cwd=WORKSPACE,
                networking=_NETWORKING,
                timeout=INSTANCE_TIMEOUT_SECONDS,
                truncate_output_at=MAX_STREAM_BYTES,
                files=files,
            )
            operation_id = _required_text(started.uuid, "spawn operation UUID")
        except (ContreeError, TimeoutError) as exc:
            raise _request_error(exc) from None
        return operation_id

    def _await_operation(
        self,
        *,
        operation_id: str,
        image_uuid: str,
        command: str,
        args: tuple[str, ...],
        files: dict[str, FileSpec],
        env: dict[str, str],
        execution_nonce: str | None,
    ) -> ContreeExecution:
        try:
            completed = self._client.wait_operation(operation_id, timeout=self._timeout)
        except (ContreeError, TimeoutError) as exc:
            raise _request_error(exc, operation_id=operation_id) from None
        return _execution(
            completed,
            operation_id=operation_id,
            image_uuid=image_uuid,
            command=command,
            args=args,
            files=files,
            env=env,
            execution_nonce=execution_nonce,
        )


def _auth_file() -> Path:
    if home := os.environ.get("CONTREE_HOME"):
        return Path(home).expanduser() / "auth.ini"
    config = Path(os.environ.get("XDG_CONFIG_HOME", "~/.config")).expanduser()
    return config / "contree" / "auth.ini"


def _request_error(exc: BaseException, *, operation_id: str | None = None) -> ContreeExecutionError:
    operation = f" operation {operation_id}" if operation_id is not None else ""
    return ContreeExecutionError(f"ConTree{operation} request failed ({type(exc).__name__})")


def _prepare_invocation(invocation: ContreeInvocation) -> _PreparedInvocation:
    if not isinstance(invocation, ContreeInvocation):
        raise TypeError("invocations must be ContreeInvocation instances")
    image_uuid = _input_text(invocation.image_uuid, "source image UUID")
    command = _input_text(invocation.command, "command")
    if not _EXECUTION_NONCE.fullmatch(invocation.execution_nonce):
        raise ValueError("execution nonce must be 32 lowercase hexadecimal characters")
    if not isinstance(invocation.args, tuple) or any(
        not isinstance(argument, str) or "\x00" in argument for argument in invocation.args
    ):
        raise ValueError("invocation args must be a tuple of NUL-free strings")
    if not isinstance(invocation.files, Mapping):
        raise ValueError("invocation files must be a mapping")
    files: dict[str, FileSpec] = {}
    for path, file in invocation.files.items():
        if not isinstance(path, str) or not path.startswith("/") or "\x00" in path:
            raise ValueError("invocation file paths must be absolute NUL-free strings")
        if (
            not isinstance(file, FileSpec)
            or not isinstance(file.uuid, str)
            or not file.uuid.strip()
        ):
            raise ValueError("invocation files must have valid provider UUIDs")
        files[path] = file
    return _PreparedInvocation(
        image_uuid=image_uuid,
        command=command,
        args=invocation.args,
        files=files,
        execution_nonce=invocation.execution_nonce,
        env={**_ENV, EXECUTION_NONCE_ENV: invocation.execution_nonce},
    )


def _input_text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        raise ValueError(f"invocation {field} must be a non-empty NUL-free string")
    return value


def _required_text(value: str | EllipsisType | None, field: str) -> str:
    if not isinstance(value, str) or not value.strip() or any(ord(char) < 32 for char in value):
        raise ContreeProtocolError(f"ConTree response is missing valid {field}")
    return value


def _number(value: int | float | EllipsisType | None) -> int | float | None:
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _stream(value: StreamRepr | EllipsisType | None, field: str) -> str | None:
    if value is ... or value is None:
        return None
    if not isinstance(value, StreamRepr):
        raise ContreeProtocolError(f"ConTree returned malformed {field}")
    if value.encoding not in {"ascii", "base64"}:
        raise ContreeProtocolError(f"ConTree returned malformed {field} encoding")
    if value.truncated is True:
        raise ContreeProtocolError(f"ConTree truncated {field}")
    return "\n".join(
        line
        if line.startswith((_JUNIT_PREFIX, _TREE_PREFIX))
        else _SECRET.sub(r"\1[REDACTED]", line)
        for line in value.as_text().splitlines()
    )


def _sentinels(output: str | None, prefix: str) -> list[str]:
    return [
        line.removeprefix(prefix) for line in (output or "").splitlines() if line.startswith(prefix)
    ]


def _files_match(actual: dict[str, FileSpec] | EllipsisType, expected: dict[str, FileSpec]) -> bool:
    return (
        isinstance(actual, dict)
        and actual.keys() == expected.keys()
        and all(
            actual[path].uuid == file.uuid
            and actual[path].mode == file.mode
            and (file.uid is ... or actual[path].uid == file.uid)
            and (file.gid is ... or actual[path].gid == file.gid)
            for path, file in expected.items()
        )
    )


def _execution(
    completed: OperationResponse,
    *,
    operation_id: str,
    image_uuid: str,
    command: str,
    args: tuple[str, ...],
    files: dict[str, FileSpec],
    env: dict[str, str],
    execution_nonce: str | None,
) -> ContreeExecution:
    if completed.status is not OperationStatus.SUCCESS:
        status = str(completed.status) if completed.status is not ... else "MISSING"
        raise ContreeExecutionError(f"ConTree operation ended with infrastructure status {status}")
    if completed.kind != "instance":
        raise ContreeProtocolError("ConTree completed operation is not an instance")
    if _required_text(completed.uuid, "completed operation UUID") != operation_id:
        raise ContreeProtocolError("ConTree completed operation UUID changed")
    source_image = _required_text(completed.image_uuid, "source image UUID")
    if source_image != image_uuid:
        raise ContreeProtocolError("ConTree operation source image UUID changed")
    result_image = _required_text(completed.result_image_uuid, "result image UUID")
    metadata = completed.metadata
    if not isinstance(metadata, OperationInstanceMetadata):
        raise ContreeProtocolError("ConTree operation is missing instance metadata")
    if (
        metadata.command != command
        or metadata.image != image_uuid
        or metadata.args != list(args)
        or metadata.shell is not False
        or metadata.disposable is not False
        or metadata.env != env
        or metadata.cwd != WORKSPACE
        or metadata.networking != _NETWORKING
        or metadata.timeout != INSTANCE_TIMEOUT_SECONDS
        or metadata.truncate_output_at != MAX_STREAM_BYTES
        or not _files_match(metadata.files, files)
    ):
        raise ContreeProtocolError("ConTree operation metadata differs from fixed request")
    result = metadata.result
    if not isinstance(result, InstanceResult) or not isinstance(result.state, InstanceResultState):
        raise ContreeProtocolError("ConTree operation is missing process result")
    if result.state.timed_out is True:
        raise ContreeExecutionError("ConTree process exceeded its server timeout")
    exit_code = result.state.exit_code
    if not isinstance(exit_code, int) or isinstance(exit_code, bool):
        raise ContreeProtocolError("ConTree process result is missing exit code")
    created_at = _required_text(completed.created_at, "creation timestamp")
    try:
        started_at = parse_datetime(created_at)
    except ValueError as exc:
        raise ContreeProtocolError("ConTree returned malformed creation timestamp") from exc
    duration_value = _number(completed.duration)
    duration = float(duration_value) if duration_value is not None else None
    if duration is not None and duration < 0:
        raise ContreeProtocolError("ConTree returned negative operation duration")
    metrics = tuple(
        (name, value)
        for name, raw in (
            ("image_size", completed.image_size),
            ("consumed_cpu", completed.consumed_cpu),
            ("consumed_memory", completed.consumed_memory),
        )
        if (value := _number(raw)) is not None
    )
    return ContreeExecution(
        operation_id=operation_id,
        source_image_uuid=source_image,
        result_image_uuid=result_image,
        started_at=started_at,
        ended_at=started_at + timedelta(seconds=duration) if duration is not None else None,
        duration_seconds=duration,
        exit_code=exit_code,
        stdout=_stream(result.stdout, "stdout"),
        stderr=_stream(result.stderr, "stderr"),
        metrics=metrics,
        execution_nonce=execution_nonce,
    )
