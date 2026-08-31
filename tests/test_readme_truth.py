"""The README may only claim what this tree actually does.

The four commands in the README's "Reproduce the checks yourself" block are deliberately not run
here: CI runs all four, plus the console script from the built wheel, on every push.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = (ROOT / "README.md").read_text()
BLOCK = re.compile(r"```(bash|text)\n(.*?)```", re.DOTALL)
MATRIX_ROW = re.compile(r"(?m)^\S+ / \S+ ")
DOC_TEST_COUNT = re.compile(r"(\d+)[- ]tests? (?:suite|passed)")


def _blocks(language: str) -> list[str]:
    return [body for kind, body in BLOCK.findall(README) if kind == language]


def test_readme_console_block_reproduces_its_pasted_output(tmp_path: Path) -> None:
    command = next(
        line.split()
        for block in _blocks("bash")
        for line in block.splitlines()
        if line.startswith("uv run nemisis ")
    )
    assert command[:3] == ["uv", "run", "nemisis"]
    scripts = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["scripts"]
    assert command[2] in scripts, f"README runs `{command[2]}`, not a declared console script"
    installed = shutil.which(command[2])
    argv = (
        [installed, *command[3:]]
        if installed
        else [sys.executable, "-c", "from nemisis.cli import main; main()", *command[3:]]
    )
    process = subprocess.run(argv, capture_output=True, text=True, cwd=tmp_path, timeout=300)
    assert process.returncode == 0, process.stderr
    expected = next(block for block in _blocks("text") if "VERDICT" in block)
    for line in expected.splitlines():
        if line.strip():
            assert line in process.stdout, f"README claims a line the run did not print: {line}"
    assert len(MATRIX_ROW.findall(process.stdout)) == len(MATRIX_ROW.findall(expected)), (
        "the run printed a different number of matrix rows than the README pastes"
    )


def test_doc_test_counts_do_not_go_stale() -> None:
    collected = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q"],
        capture_output=True,
        text=True,
        cwd=ROOT,
        timeout=300,
    )
    match = re.search(r"(\d+) tests? collected", collected.stdout)
    assert match, collected.stdout
    total = match.group(1)
    stale = [
        f"{path.relative_to(ROOT)}: {found.group(0)}"
        for path in sorted((ROOT / "docs").rglob("*.md")) + [ROOT / "README.md"]
        for found in DOC_TEST_COUNT.finditer(path.read_text())
        if found.group(1) != total
    ]
    assert not stale, f"docs claim a test count other than the collected {total}: {stale}"


def test_every_relative_readme_link_resolves() -> None:
    targets = [
        target
        for target in re.findall(r"\]\(([^)]+)\)", README)
        if not target.startswith(("http://", "https://", "#", "mailto:"))
    ]
    assert targets
    missing = [target for target in targets if not (ROOT / target).exists()]
    assert not missing, f"README links to missing paths: {missing}"
