"""Small, deterministic hashing helpers used by evidence bindings."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel


def _jsonable(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_jsonable(item) for item in value]
    return value


def canonical_json(value: Any) -> bytes:
    """Return UTF-8 JSON with stable key ordering and no insignificant whitespace."""
    return json.dumps(
        _jsonable(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode())


def sha256_json(value: Any) -> str:
    return sha256_bytes(canonical_json(value))


def sha256_files(root: Path, paths: Sequence[Path]) -> str:
    """Bind relative path names and bytes, rejecting anything except regular files."""
    entries: list[dict[str, str]] = []
    for relative in sorted(paths, key=lambda item: item.as_posix()):
        path = root / relative
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"not a regular file: {relative.as_posix()}")
        entries.append({"path": relative.as_posix(), "sha256": sha256_bytes(path.read_bytes())})
    return sha256_json(entries)


def sha256_tree(root: Path, *, ignored_names: frozenset[str] = frozenset()) -> str:
    paths = [
        path.relative_to(root)
        for path in root.rglob("*")
        if path.is_file()
        and not any(part in ignored_names for part in path.relative_to(root).parts)
    ]
    return sha256_files(root, paths)
