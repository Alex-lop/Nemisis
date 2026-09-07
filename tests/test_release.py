"""What `uv build` publishes: the package, its paperwork, and one honest version number.

Nothing else in the suite looks at the artifact. Without these two tests the sdist quietly
carried the whole repository — docs, tests, the site, the workflows, and every stray Markdown
directive left in the working tree — and `__version__` could drift from the metadata the
installed distribution reports.
"""

from __future__ import annotations

import importlib.metadata
import subprocess
import tarfile
from pathlib import Path

import pytest

import nemisis

_ROOT = Path(__file__).resolve().parents[1]
# PKG-INFO and the VCS ignore file are force-included by hatchling itself and cannot be
# configured away; everything else here is what pyproject.toml asks for.
_ALLOWED_FILES = frozenset({"README.md", "LICENSE", "pyproject.toml", "PKG-INFO", ".gitignore"})


def test_version_matches_the_installed_distribution_metadata() -> None:
    assert nemisis.__version__ == importlib.metadata.version("nemisis")


def _is_publishable(relative: str) -> bool:
    return (
        relative in _ALLOWED_FILES
        or relative == "src"
        or relative == "src/nemisis"
        or relative.startswith("src/nemisis/")
    )


def test_sdist_publishes_only_the_package_and_its_paperwork(tmp_path: Path) -> None:
    build = subprocess.run(
        ["uv", "build", "--sdist", "--out-dir", str(tmp_path)],
        cwd=_ROOT,
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )
    if build.returncode != 0:
        pytest.fail(f"uv build --sdist failed:\n{build.stdout}\n{build.stderr}")

    archives = sorted(tmp_path.glob("*.tar.gz"))
    assert len(archives) == 1, archives

    with tarfile.open(archives[0]) as archive:
        names = archive.getnames()

    prefix = f"nemisis-{nemisis.__version__}"
    assert names, "the sdist is empty"
    outside = sorted(name for name in names if name != prefix and not name.startswith(f"{prefix}/"))
    assert outside == [], outside

    published = [name[len(prefix) + 1 :] for name in names if name != prefix]
    stray = sorted(name for name in published if not _is_publishable(name))
    assert stray == [], stray
    assert "src/nemisis/cli.py" in published
    assert "PKG-INFO" in published
