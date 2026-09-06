"""The contract digest printed in the Stage A2 transcript must be the one `init` still drafts."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from nemisis.crash_fixture import BUGGY_REF, load_issue
from nemisis.crashcheck import initialize

LIVE_SETUP = Path(__file__).parents[1] / "docs/LIVE_SETUP.md"


def test_live_setup_quotes_the_contract_digest_init_still_drafts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    quoted = re.search(r"^contract: ([0-9a-f]{64})$", LIVE_SETUP.read_text("utf-8"), re.MULTILINE)
    assert quoted is not None, "the Stage A2 transcript no longer prints a contract digest"

    issue = tmp_path / "issue.md"
    issue.write_text(load_issue(), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    config = json.loads(
        initialize(issue, "app.credits:apply_credit", BUGGY_REF, "sqlite-credit-v1").read_text(
            encoding="utf-8"
        )
    )

    assert config["contract"]["accepted"] is True
    assert config["contract"]["digest"] == quoted.group(1)
