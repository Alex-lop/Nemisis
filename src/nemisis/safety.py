"""Validation shared by untrusted generated files and candidate patches."""

from __future__ import annotations

from pathlib import Path, PurePosixPath


def safe_relative_path(value: str, *, required_root: str | None = None) -> PurePosixPath:
    if not value or "\\" in value or "\x00" in value:
        raise ValueError(f"unsafe path: {value!r}")
    path = PurePosixPath(value)
    invalid_part = any(part in {"", ".", ".."} for part in path.parts)
    if path.is_absolute() or path.as_posix() != value or invalid_part:
        raise ValueError(f"unsafe path: {value!r}")
    if required_root is not None and (not path.parts or path.parts[0] != required_root):
        raise ValueError(f"path must be under {required_root}/: {value!r}")
    return path


def safe_destination(root: Path, relative: PurePosixPath) -> Path:
    root = root.resolve()
    destination = root.joinpath(*relative.parts)
    current = root
    for part in relative.parts[:-1]:
        current /= part
        if current.is_symlink():
            raise ValueError(f"symlink escape blocked: {relative.as_posix()}")
    if destination.exists() and destination.is_symlink():
        raise ValueError(f"symlink overwrite blocked: {relative.as_posix()}")
    if not destination.resolve().is_relative_to(root):
        raise ValueError(f"path escapes root: {relative.as_posix()}")
    return destination
