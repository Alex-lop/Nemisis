"""Numbers in `docs/DEMO.md` that drifted once and nothing else pins."""

from __future__ import annotations

import re
import struct
from pathlib import Path

DEMO = Path(__file__).resolve().parents[1] / "docs" / "DEMO.md"
GIF = (
    Path(__file__).resolve().parents[1] / "docs" / "assets" / "screenshots" / "crashcheck-demo.gif"
)
WORDS = {"Four": 4, "Five": 5, "Six": 6, "Seven": 7, "Eight": 8}


def _script_rows() -> list[tuple[str, str]]:
    """The (clock, typed command) cells of the script table, stop row excluded."""
    rows: list[tuple[str, str]] = []
    for line in DEMO.read_text().splitlines():
        if not line.startswith("| "):
            continue
        cells = [cell.strip() for cell in line.replace(r"\|", "\x00").strip("| ").split("|")]
        clock, typed = cells[0], cells[1].replace("\x00", "|")
        if re.fullmatch(r"\d:\d\d", clock) and typed and typed != "stop":
            rows.append((clock, typed))
    return rows


def _gif_seconds(path: Path) -> float:
    """Sum the frame delays of a GIF, in seconds."""
    data = path.read_bytes()
    i = 13
    if data[10] & 0x80:  # global color table
        i += 3 * 2 ** ((data[10] & 7) + 1)

    def skip_sub_blocks(at: int) -> int:
        while data[at]:
            at += 1 + data[at]
        return at + 1

    centiseconds = 0
    while i < len(data) and data[i] != 0x3B:
        if data[i] == 0x21:  # extension
            if data[i + 1] == 0xF9:  # graphic control
                centiseconds += struct.unpack("<H", data[i + 4 : i + 6])[0]
            i = skip_sub_blocks(i + 2)
        elif data[i] == 0x2C:  # image descriptor
            flags = data[i + 9]
            i += 10
            if flags & 0x80:  # local color table
                i += 3 * 2 ** ((flags & 7) + 1)
            i = skip_sub_blocks(i + 1)
        else:
            raise AssertionError(f"unexpected GIF block 0x{data[i]:02x} at {i}")
    return centiseconds / 100


def test_the_opening_line_counts_the_commands_the_presenter_types() -> None:
    """A beat was added to the table once and the opening count was left behind."""
    stated = re.search(r"^(\w+) commands, one story", DEMO.read_text(), re.MULTILINE)
    assert stated is not None
    assert WORDS[stated.group(1)] == len(_script_rows())


def test_the_no_browser_fallback_skips_the_row_that_opens_a_browser() -> None:
    """The fallback names a clock, so re-timing the script can point it at a terminal beat."""
    browser = [clock for clock, typed in _script_rows() if "report.html" in typed]
    assert len(browser) == 1
    assert f"- **No browser.** Skip the {browser[0]} report beat;" in DEMO.read_text()


def test_the_stated_length_of_the_demo_gif_matches_the_committed_gif() -> None:
    """`30 s` outlived two re-recordings; the file itself is the only honest source."""
    stated = re.search(r"crashcheck-demo\.gif\)\s+\((\d+) s,", DEMO.read_text())
    assert stated is not None
    assert round(_gif_seconds(GIF)) == int(stated.group(1))
