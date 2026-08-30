from __future__ import annotations

from pathlib import Path

import pytest

from nemisis.hashing import sha256_tree
from nemisis.patches import PatchRejected, apply_patch, validate_patch
from nemisis.safety import safe_relative_path


@pytest.mark.parametrize(
    "path", ["/tmp/test.py", "../test.py", "generated/../../x.py", r"generated\x.py"]
)
def test_unsafe_generated_paths_are_rejected(path: str) -> None:
    with pytest.raises(ValueError):
        safe_relative_path(path, required_root="generated")


@pytest.mark.parametrize(
    "marker",
    [
        "GIT binary patch",
        "new file mode 120000",
        "new file mode 160000",
        "old mode 100644\nnew mode 100755",
    ],
)
def test_unsafe_patch_kinds_are_rejected(marker: str) -> None:
    patch = f"diff --git a/app.py b/app.py\n{marker}\n".encode()
    with pytest.raises(PatchRejected):
        validate_patch(patch, base_digest="0" * 64, allowed_files=frozenset({"app.py"}))


def test_patch_is_bound_to_base_and_resulting_tree(tmp_path: Path) -> None:
    source = tmp_path / "app.py"
    source.write_text("value = 1\n")
    base_digest = sha256_tree(tmp_path)
    raw = (
        b"diff --git a/app.py b/app.py\n"
        b"--- a/app.py\n"
        b"+++ b/app.py\n"
        b"@@ -1 +1 @@\n"
        b"-value = 1\n"
        b"+value = 2\n"
    )
    spec = validate_patch(raw, base_digest=base_digest, allowed_files=frozenset({"app.py"}))
    applied = apply_patch(spec, tmp_path)
    assert source.read_text() == "value = 2\n"
    assert applied.resulting_tree_digest == sha256_tree(tmp_path)


def test_patch_cannot_touch_harness_or_config() -> None:
    for path in ("pytest.ini", "conftest.py", "__nemisis_bundle__/test.py"):
        raw = f"diff --git a/{path} b/{path}\n--- a/{path}\n+++ b/{path}\n".encode()
        with pytest.raises(PatchRejected):
            validate_patch(raw, base_digest="0" * 64, allowed_files=frozenset({path}))
