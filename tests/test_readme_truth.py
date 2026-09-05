"""The README and docs may only point at things that exist, and the visual evidence must be real.

Every relative link and every embedded image in the README and under ``docs/`` must resolve. Every
image the README embeds must be a decodable PNG or GIF of sane dimensions and size, so a broken or
zero-byte capture can never ship as "evidence". Hand-written test counts must match the collected
count, so they cannot rot in silence.
"""

from __future__ import annotations

import re
import struct
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
SCREENSHOTS = ROOT / "docs/assets/screenshots"
LINK = re.compile(r"!?\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
IMAGE = re.compile(r"!\[[^\]]*\]\(([^)\s]+)")
DOC_TEST_COUNT = re.compile(r"(\d{2,})(?:\+)? (?:local )?tests?\b")
MAX_IMAGE_BYTES = 1_500_000
MAX_GIF_BYTES = 3_000_000


def _documents() -> list[Path]:
    return [README, *sorted(ROOT.glob("docs/*.md"))]


def _targets(document: Path) -> list[tuple[str, Path]]:
    text = document.read_text(encoding="utf-8")
    found: list[tuple[str, Path]] = []
    for target in LINK.findall(text):
        if target.startswith(("http://", "https://", "#", "mailto:")):
            continue
        path = target.split("#", 1)[0]
        if not path:
            continue
        found.append((target, (document.parent / path).resolve()))
    return found


def _png_size(data: bytes) -> tuple[int, int]:
    assert data[:8] == b"\x89PNG\r\n\x1a\n", "not a PNG"
    width, height = struct.unpack(">II", data[16:24])
    return width, height


def _gif_size(data: bytes) -> tuple[int, int]:
    assert data[:6] in (b"GIF87a", b"GIF89a"), "not a GIF"
    width, height = struct.unpack("<HH", data[6:10])
    return width, height


def test_every_relative_link_in_readme_and_docs_resolves() -> None:
    missing = [
        f"{document.relative_to(ROOT)} -> {target}"
        for document in _documents()
        for target, path in _targets(document)
        if not path.exists()
    ]
    assert not missing, f"links to missing paths: {missing}"


def test_readme_embeds_real_visual_evidence() -> None:
    images = IMAGE.findall(README.read_text(encoding="utf-8"))
    assert images, "the README front door must embed at least one screenshot"
    committed = set(SCREENSHOTS.glob("*.png")) | set(SCREENSHOTS.glob("*.gif"))
    assert committed, "no captures are committed under docs/assets/screenshots"
    for target in images:
        path = (ROOT / target).resolve()
        assert path.is_file(), f"README embeds a missing image: {target}"
        data = path.read_bytes()
        if path.suffix == ".gif":
            width, height = _gif_size(data)
            assert len(data) <= MAX_GIF_BYTES, f"{target} is {len(data)} bytes"
        else:
            width, height = _png_size(data)
            assert len(data) <= MAX_IMAGE_BYTES, f"{target} is {len(data)} bytes"
        assert 600 <= width <= 2000, f"{target} is {width}px wide"
        assert 200 <= height <= 2400, f"{target} is {height}px tall"
    for path in committed:
        data = path.read_bytes()
        assert data, f"{path.name} is empty"
        (_gif_size if path.suffix == ".gif" else _png_size)(data)


def test_screenshot_tapes_regenerate_the_committed_captures() -> None:
    tapes = sorted(SCREENSHOTS.glob("*.tape"))
    assert tapes, "the vhs tapes that regenerate the captures must be committed beside them"
    produced: set[str] = set()
    for tape in tapes:
        for line in tape.read_text(encoding="utf-8").splitlines():
            if line.startswith(("Output ", "Screenshot ")):
                produced.add(Path(line.split(None, 1)[1].strip()).name)
    for capture in sorted(SCREENSHOTS.glob("terminal-*.png")) + sorted(SCREENSHOTS.glob("*.gif")):
        assert capture.name in produced, f"{capture.name} has no tape that regenerates it"


def test_doc_test_counts_do_not_go_stale() -> None:
    collected = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider"],
        capture_output=True,
        text=True,
        cwd=ROOT,
        timeout=300,
        check=False,
    )
    match = re.search(r"(\d+) tests? collected", collected.stdout)
    assert match, collected.stdout
    total = match.group(1)
    stale = [
        f"{document.relative_to(ROOT)}: {found.group(0)}"
        for document in _documents()
        for found in DOC_TEST_COUNT.finditer(document.read_text(encoding="utf-8"))
        if found.group(1) != total
    ]
    assert not stale, f"docs claim a test count other than the collected {total}: {stale}"
