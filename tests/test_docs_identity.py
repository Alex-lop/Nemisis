"""Exact identities quoted as current in the ledgers must equal the installed engine."""

from __future__ import annotations

import re
from pathlib import Path

from nemisis.crashcheck import engine_code_digest

ROOT = Path(__file__).parents[1]


def _quoted_current_digest(document: Path, marker: str) -> str:
    text = document.read_text(encoding="utf-8")
    match = re.search(marker + r"[^\n]*?`([0-9a-f]{64})`", text)
    assert match is not None, f"{document.name} no longer quotes a current engine digest"
    return match.group(1)


def test_status_and_proof_quote_the_installed_engine_digest() -> None:
    current = engine_code_digest()
    assert (
        _quoted_current_digest(ROOT / "docs/STATUS.md", r"Current tree:\n\n- engine code digest: ")
        == current
    )
    assert (
        _quoted_current_digest(ROOT / "docs/PROOF.md", r"the current engine\ncode digest is ")
        == current
    )
