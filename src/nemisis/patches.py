"""Conservative validation and fixed-argv application for candidate patches."""

from __future__ import annotations

import re
import shlex
import subprocess
from pathlib import Path

from nemisis.hashing import sha256_bytes, sha256_tree
from nemisis.models import CandidatePatchSpec, PatchValidationStatus
from nemisis.safety import safe_relative_path

MAX_PATCH_BYTES = 100_000
MAX_FILE_BYTES = 100_000
MAX_PATCH_FILES = 20
ALLOWED_SUFFIXES = frozenset({".py", ".md", ".txt", ".toml", ".json"})
PROTECTED_NAMES = frozenset({"conftest.py", "pytest.ini", "pyproject.toml", "setup.cfg", "tox.ini"})
PROTECTED_ROOTS = frozenset({"__nemisis_bundle__", ".nemisis", ".git"})


class PatchRejected(ValueError):
    pass


def _declared_files(text: str) -> tuple[str, ...]:
    files: list[str] = []
    for line in text.splitlines():
        if not line.startswith("diff --git "):
            continue
        try:
            fields = shlex.split(line)
        except ValueError as error:
            raise PatchRejected("malformed diff header") from error
        if len(fields) != 4 or not fields[2].startswith("a/") or not fields[3].startswith("b/"):
            raise PatchRejected("unsupported diff header")
        old, new = fields[2][2:], fields[3][2:]
        if old != new:
            raise PatchRejected("renames are not supported")
        try:
            path = safe_relative_path(new)
        except ValueError as error:
            raise PatchRejected(str(error)) from error
        if any(character.isspace() for character in new):
            raise PatchRejected("patch paths containing whitespace are not supported")
        if path.parts[0] in PROTECTED_ROOTS or path.name in PROTECTED_NAMES:
            raise PatchRejected(f"protected path: {new}")
        if path.suffix not in ALLOWED_SUFFIXES:
            raise PatchRejected(f"unsupported file type: {new}")
        files.append(path.as_posix())
    if not files:
        raise PatchRejected("patch contains no file diffs")
    if len(files) != len(set(files)):
        raise PatchRejected("patch repeats a file")
    if len(files) > MAX_PATCH_FILES:
        raise PatchRejected(f"patch exceeds {MAX_PATCH_FILES} files")
    sections = re.split(r"(?m)^diff --git ", text)[1:]
    for expected, section in zip(files, sections, strict=True):
        header = section.split("@@", 1)[0].splitlines()
        if f"--- a/{expected}" not in header or f"+++ b/{expected}" not in header:
            raise PatchRejected(f"file headers do not match diff header: {expected}")
    return tuple(files)


def validate_patch(
    raw: bytes, *, base_digest: str, allowed_files: frozenset[str]
) -> CandidatePatchSpec:
    if not raw or len(raw) > MAX_PATCH_BYTES or b"\x00" in raw:
        raise PatchRejected(f"patch must be 1..{MAX_PATCH_BYTES} UTF-8 bytes")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise PatchRejected("binary or non-UTF-8 patch") from error
    forbidden_markers = (
        "GIT binary patch",
        "Binary files ",
        "new file mode 120000",
        "deleted file mode 120000",
        "new file mode 160000",
        "deleted file mode 160000",
        "old mode ",
        "new mode ",
        "Subproject commit ",
    )
    if any(marker in text for marker in forbidden_markers):
        raise PatchRejected("binary, symlink, submodule, or mode-changing patch")
    files = _declared_files(text)
    unexpected = set(files) - allowed_files
    if unexpected:
        raise PatchRejected(f"file is not allowed: {sorted(unexpected)[0]}")
    return CandidatePatchSpec(
        canonical_patch=raw,
        digest=sha256_bytes(raw),
        declared_files=files,
        total_bytes=len(raw),
        resolved_base_identity=base_digest,
        allowed_text_modifications=files,
        validation_status=PatchValidationStatus.VALID,
    )


def apply_patch(spec: CandidatePatchSpec, world: Path) -> CandidatePatchSpec:
    if spec.validation_status is not PatchValidationStatus.VALID:
        raise PatchRejected("cannot apply a rejected patch")
    if sha256_tree(world) != spec.resolved_base_identity:
        raise PatchRejected("base tree digest does not match patch binding")
    if sha256_bytes(spec.canonical_patch) != spec.digest:
        raise PatchRejected("patch bytes do not match patch digest")
    if set(spec.declared_files) != set(spec.allowed_text_modifications):
        raise PatchRejected("declared and allowed patch files differ")
    before = _file_digests(world)
    check = subprocess.run(
        ["git", "apply", "--check", "--whitespace=nowarn", "-"],
        cwd=world,
        input=spec.canonical_patch,
        capture_output=True,
        timeout=15,
        check=False,
    )
    if check.returncode:
        raise PatchRejected(f"patch does not apply: {check.stderr.decode(errors='replace')[:300]}")
    applied = subprocess.run(
        ["git", "apply", "--whitespace=nowarn", "-"],
        cwd=world,
        input=spec.canonical_patch,
        capture_output=True,
        timeout=15,
        check=False,
    )
    if applied.returncode:
        detail = applied.stderr.decode(errors="replace")[:300]
        raise PatchRejected(f"patch application failed: {detail}")
    after = _file_digests(world)
    changed = {path for path in before.keys() | after.keys() if before.get(path) != after.get(path)}
    if changed != set(spec.declared_files):
        raise PatchRejected("applied file set differs from validated patch")
    if any((world / path).stat().st_size > MAX_FILE_BYTES for path in spec.declared_files):
        raise PatchRejected(f"modified file exceeds {MAX_FILE_BYTES} bytes")
    return spec.model_copy(update={"resulting_tree_digest": sha256_tree(world)})


def _file_digests(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): sha256_bytes(path.read_bytes())
        for path in root.rglob("*")
        if path.is_file() and not path.is_symlink()
    }
