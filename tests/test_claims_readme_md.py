"""Two README promises that nothing else in the suite holds to account.

The first is the "What it never does" guarantee: no command the engine runs can write to the
user's repository or its history. Every ``git`` invocation in ``src/`` is read-only, and the only
mutating one (``git apply``) is always scoped to an isolated world by ``cwd``. The second is the
prerequisite line under "Try it": the Python floor the README quotes is the floor the package
actually enforces, with no upper bound to make the ``+`` a lie.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCES = sorted((ROOT / "src" / "nemisis").rglob("*.py"))
README = (ROOT / "README.md").read_text(encoding="utf-8")

# ["git", "-C", <path>, "status", ...], ['git','apply', ...], and the *args forwarder in _git.
GIT_ARGV = re.compile(
    r"""['"]git['"]\s*,\s*(?:['"]-C['"]\s*,\s*[^,\]]+,\s*)?"""
    r"""(?:['"](?P<subcommand>[a-z][a-z-]*)['"]|(?P<dynamic>\*args))"""
)
GIT_TOKEN = re.compile(r"""['"]git['"]\s*,""")
GIT_FORWARDED = re.compile(r"""_git\(\s*repository,\s*['"]([a-z][a-z-]*)['"]""")
READ_ONLY = frozenset({"status", "rev-parse", "archive", "cat-file"})


def test_no_git_command_the_engine_runs_can_write_to_your_repository() -> None:
    subcommands: set[str] = set()
    for source in SOURCES:
        text = source.read_text(encoding="utf-8")
        argvs = list(GIT_ARGV.finditer(text))
        assert len(argvs) == len(GIT_TOKEN.findall(text)), (
            f"{source.name} builds a git argv this test cannot read; extend the scan"
        )
        for match in argvs:
            subcommand = match.group("subcommand")
            if subcommand is None:  # the _git forwarder; its call sites are checked below
                subcommands.update(GIT_FORWARDED.findall(text))
                continue
            subcommands.add(subcommand)
            if subcommand == "apply":
                tail = text[match.end() : match.end() + 200]
                assert "cwd=" in tail, (
                    f"{source.name} applies a patch without scoping it to an isolated world"
                )
    assert subcommands, "the scan found no git invocations at all"
    unexpected = subcommands - READ_ONLY - {"apply"}
    assert not unexpected, f"the engine runs git subcommands that can write: {sorted(unexpected)}"


def test_the_readme_python_floor_is_the_floor_the_package_enforces() -> None:
    quoted = re.findall(r"[Pp]ython[ -](\d+\.\d+)%?2?[B+]", README)
    assert quoted, "the README no longer states a Python floor"
    assert len(set(quoted)) == 1, f"the README states two different Python floors: {set(quoted)}"
    required = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"][
        "requires-python"
    ]
    assert required == f">={quoted[0]}", f"the README says {quoted[0]}+, packaging says {required}"
