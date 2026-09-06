"""Two claims in the live runbook must keep matching the tree they describe.

The runbook quotes locked dependency versions and hands the operator a copy-paste catalog probe
that hard-codes the adapter's constants. Nothing else reads that file, so both rot in silence:
a ``uv lock`` bump or a new default model would leave the operator probing the wrong thing.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

from contree_client import DEFAULT_BASE_URL as SANDBOX_BASE_URL

from nemisis.nemotron import (
    _STRUCTURED_FEATURES,
    API_KEY_ENV,
    BASE_URL_ENV,
    DEFAULT_BASE_URL,
    DEFAULT_MODEL_ID,
    MODEL_ID_ENV,
)

RUNBOOK = Path(__file__).parents[1] / "docs/LIVE_RUNBOOK.md"
LOCK = Path(__file__).parents[1] / "uv.lock"


def _locked_version(package: str) -> str:
    match = re.search(
        rf'^name = "{re.escape(package)}"\nversion = "([^"]+)"$',
        LOCK.read_text(encoding="utf-8"),
        re.MULTILINE,
    )
    assert match is not None, f"uv.lock no longer locks {package}"
    return match.group(1)


def test_live_runbook_quotes_the_locked_dependency_versions() -> None:
    text = RUNBOOK.read_text(encoding="utf-8")
    openai = _locked_version("openai")
    contree = _locked_version("contree-client")
    for quoted in (
        f"openai=={openai}",
        f"contree-client[httpx]=={contree}",
        f"contree-client=={contree}",
    ):
        assert quoted in text, f"docs/LIVE_RUNBOOK.md no longer quotes the installed {quoted}"
    assert importlib.util.find_spec("contree_sdk") is None, (
        "contree_sdk is installed; the runbook still says it is not"
    )


def test_live_runbook_probe_matches_the_adapter_defaults() -> None:
    text = RUNBOOK.read_text(encoding="utf-8")
    expected = {
        DEFAULT_MODEL_ID,
        DEFAULT_BASE_URL,
        API_KEY_ENV,
        BASE_URL_ENV,
        MODEL_ID_ENV,
        SANDBOX_BASE_URL,
        *_STRUCTURED_FEATURES,
    }
    missing = sorted(value for value in expected if value not in text)
    assert not missing, f"the runbook probe no longer matches the installed adapter: {missing}"
