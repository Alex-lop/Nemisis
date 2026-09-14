"""The MCP surface, exercised by an in-process client — the customer is an agent, so the tests
drive the tools the way an agent would. The scripted end-to-end test is the one the README H1
change hangs on: no model, list_scenarios -> port_template -> a buggy port that fails -> an atomic
port that proves -> the receipt read back as a resource."""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any, cast

import anyio
import pytest
from mcp import Client
from mcp.types import CallToolResult, TextResourceContents

from nemisis.mcp_server import build_server

CREDIT = "sqlite-credit-v1"
INVENTORY = "sqlite-inventory-v1"

BUGGY_PORT = '''"""A port of our real webhook credit handler to the CrashCheck store."""


def apply_credit(store, event):
    # Mirrors handlers/credit.py: guard, credit, then mark — the retry bug is between the last two.
    if store.processed(event["event_id"]):
        return
    store.credit(event["account_id"], event["event_id"], event["amount_cents"])
    store.mark_processed(event["event_id"])
'''

ATOMIC_PORT = '''"""Our real credit handler, fixed: credit and mark in one commit."""


def apply_credit(store, event):
    store.credit_and_mark(event["account_id"], event["event_id"], event["amount_cents"])
'''


@pytest.fixture(autouse=True)
def _artifact_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "artifacts"
    monkeypatch.setenv("NEMISIS_ARTIFACT_ROOT", str(root))
    monkeypatch.delenv("NEBIUS_API_KEY", raising=False)
    return root


def _run[T](body: Callable[[Client], Awaitable[T]]) -> T:
    async def main() -> T:
        async with Client(build_server()) as client:
            return await body(client)

    return anyio.run(main)


def _structured(result: CallToolResult) -> dict[str, Any]:
    assert result.structured_content is not None, result.content
    return cast(dict[str, Any], result.structured_content)


def _write_port(root: Path, handler: str) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "app").mkdir(parents=True, exist_ok=True)
    (root / "app" / "__init__.py").write_text('"""app"""\n', encoding="utf-8")
    (root / "app" / "credits.py").write_text(handler, encoding="utf-8")
    return root


def test_the_server_registers_exactly_the_seven_documented_tools() -> None:
    async def body(client: Client) -> list[str]:
        tools = await client.list_tools()
        return sorted(t.name for t in tools.tools)

    assert _run(body) == [
        "accept_contract",
        "check",
        "doctor",
        "draft_contract",
        "list_scenarios",
        "map",
        "port_template",
        "propose_patch",
    ]


def test_list_scenarios_names_every_scenario_its_store_and_its_variants() -> None:
    async def body(client: Client) -> dict[str, Any]:
        return _structured(await client.call_tool("list_scenarios", {}))

    result = _run(body)
    assert result["truth_label"] == "FIXTURE"
    ids = {s["id"] for s in result["scenarios"]}
    assert {CREDIT, INVENTORY} <= ids
    credit = next(s for s in result["scenarios"] if s["id"] == CREDIT)
    names = [m["name"] for m in credit["store_methods"]]
    assert "processed" in names and "credit_and_mark" in names
    assert "buggy" in credit["variants"]["hero"]
    assert "raw-sql" in credit["variants"]["zoo"]


def test_port_template_carries_the_skeleton_the_api_and_the_forfeits() -> None:
    async def body(client: Client) -> dict[str, Any]:
        return _structured(await client.call_tool("port_template", {"scenario": CREDIT}))

    result = _run(body)
    assert result["truth_label"] == "FIXTURE"
    assert "def apply_credit(store, event)" in result["skeleton"]
    assert "credit_and_mark" in result["store_api"]
    shapes = {f["shape"] for f in result["forfeits"]}
    assert any("raw SQL" in s for s in shapes)
    assert all(f["verdict"] == "EVIDENCE_INCOMPLETE" for f in result["forfeits"])


def test_check_proves_the_atomic_fix_and_carries_the_local_label(tmp_path: Path) -> None:
    port = _write_port(tmp_path / "atomic-port", ATOMIC_PORT)

    async def body(client: Client) -> dict[str, Any]:
        return _structured(
            await client.call_tool("check", {"candidate": str(port), "scenario": CREDIT})
        )

    result = _run(body)
    assert result["verdict"] == "FIX_PROVEN_FOR_THIS_CAPSULE"
    assert result["exit_code"] == 0
    assert result["truth_label"] == "LOCAL"
    assert result["run_id"]
    assert result["receipt_resource"].startswith("nemisis://run/")


def test_check_returns_a_clean_error_shape_for_a_same_tree_candidate() -> None:
    async def body(client: Client) -> dict[str, Any]:
        return _structured(
            await client.call_tool(
                "check", {"candidate": f"fixture:{CREDIT}/buggy", "scenario": CREDIT}
            )
        )

    result = _run(body)
    assert result["verdict"] == "EVIDENCE_INCOMPLETE"
    assert result["exit_code"] == 2
    assert "same tree" in result["error"]


def test_check_still_reproduces_on_a_misleading_green_candidate() -> None:
    async def body(client: Client) -> dict[str, Any]:
        return _structured(
            await client.call_tool(
                "check", {"candidate": f"fixture:{CREDIT}/misleading-green", "scenario": CREDIT}
            )
        )

    result = _run(body)
    assert result["verdict"] == "PATCH_FAILED_STILL_REPRODUCES"
    assert result["exit_code"] == 1


def test_map_refuses_tail_bytes_at_the_census() -> None:
    async def body(client: Client) -> dict[str, Any]:
        return _structured(
            await client.call_tool(
                "map", {"candidate": f"fixture:{CREDIT}/tail-bytes", "scenario": CREDIT}
            )
        )

    result = _run(body)
    assert result["census_status"] == "INTEGRITY_ERROR"
    assert result["refusal"] is not None
    assert result["windows"] == []


def test_doctor_reports_its_status_and_labels() -> None:
    async def body(client: Client) -> dict[str, Any]:
        return _structured(await client.call_tool("doctor", {}))

    result = _run(body)
    assert result["status"] in {"READY", "BLOCKED"}
    assert isinstance(result["checks"], list)


def test_the_nemotron_tools_are_blocked_without_a_key_not_mocked() -> None:
    async def body(client: Client) -> tuple[dict[str, Any], dict[str, Any]]:
        draft = _structured(
            await client.call_tool(
                "draft_contract",
                {
                    "issue": "double credit on retry",
                    "target": "app.credits:apply_credit",
                    "base": f"fixture:{CREDIT}/buggy",
                    "scenario": CREDIT,
                },
            )
        )
        patch = _structured(
            await client.call_tool(
                "propose_patch",
                {
                    "issue": "double credit on retry",
                    "base": f"fixture:{CREDIT}/buggy",
                    "scenario": CREDIT,
                },
            )
        )
        return draft, patch

    draft, patch = _run(body)
    assert draft["truth_label"] == "BLOCKED"
    assert "NEBIUS_API_KEY" in draft["blocked"]
    assert patch["truth_label"] == "BLOCKED"
    assert "NEBIUS_API_KEY" in patch["blocked"]


def test_a_blocked_model_tool_writes_nothing(_artifact_root: Path) -> None:
    async def body(client: Client) -> None:
        for name, args in (
            (
                "draft_contract",
                {
                    "issue": "double credit on retry",
                    "target": "app.credits:apply_credit",
                    "base": f"fixture:{CREDIT}/buggy",
                    "scenario": CREDIT,
                },
            ),
            (
                "propose_patch",
                {
                    "issue": "double credit on retry",
                    "base": f"fixture:{CREDIT}/buggy",
                    "scenario": CREDIT,
                },
            ),
        ):
            result = _structured(await client.call_tool(name, args))
            assert result["truth_label"] == "BLOCKED"

    _run(body)
    # The key is unset (the fixture deletes it), so both tools must touch the filesystem not at all:
    # no artifact root, no port/issue.md, no candidate tree.
    assert not _artifact_root.exists()


def test_the_scripted_agent_reaches_fix_proven_with_no_model(tmp_path: Path) -> None:
    """The whole loop, exactly as an agent would drive it, with no model in the room: list the
    scenarios, read the template, write a buggy port that still reproduces, write the atomic port
    that proves the fix, and read the receipt back as a resource."""

    async def body(client: Client) -> None:
        scenarios = _structured(await client.call_tool("list_scenarios", {}))
        assert any(s["id"] == CREDIT for s in scenarios["scenarios"])

        template = _structured(await client.call_tool("port_template", {"scenario": CREDIT}))
        assert "def apply_credit" in template["skeleton"]

        buggy = _write_port(tmp_path / "port-buggy", BUGGY_PORT)
        first = _structured(
            await client.call_tool("check", {"candidate": str(buggy), "scenario": CREDIT})
        )
        assert first["verdict"] != "FIX_PROVEN_FOR_THIS_CAPSULE"
        assert first["exit_code"] != 0

        atomic = _write_port(tmp_path / "port-atomic", ATOMIC_PORT)
        proven = _structured(
            await client.call_tool("check", {"candidate": str(atomic), "scenario": CREDIT})
        )
        assert proven["verdict"] == "FIX_PROVEN_FOR_THIS_CAPSULE"
        assert proven["exit_code"] == 0

        receipt = await client.read_resource(proven["receipt_resource"])
        receipt_body = receipt.contents[0]
        assert isinstance(receipt_body, TextResourceContents)
        capsule = json.loads(receipt_body.text)
        assert capsule["scenario_id"] == CREDIT

        report = await client.read_resource(proven["report_resource"])
        report_body = report.contents[0]
        assert isinstance(report_body, TextResourceContents)
        assert "<html" in report_body.text.lower()

    _run(body)
