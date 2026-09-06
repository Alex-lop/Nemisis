"""Formatting shared by the CLI, the report, and scenario display labels."""

from __future__ import annotations


def money(cents: int) -> str:
    sign = "-" if cents < 0 else ""
    absolute = abs(cents)
    return f"{sign}${absolute // 100:,}.{absolute % 100:02d}"


__all__ = ["money"]
