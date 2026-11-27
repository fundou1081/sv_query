"""Semantic assignment source locations normalized to disk line numbers."""
from __future__ import annotations

from pathlib import Path

from .source_assignment import compiled_line_shift


def disk_line(adapter, filename: str, line: int) -> int:
    """Map a preprocessed semantic line back to the on-disk file line."""
    if not filename or not line:
        return line
    compiler = getattr(adapter, "_compiler", None)
    injected = getattr(compiler, "timescale_injected", {}) or {}
    name = Path(filename).name
    was_injected = injected.get(filename)
    if was_injected is None:
        was_injected = next(
            (v for k, v in injected.items() if Path(k).name == name), False)
    if was_injected:
        return max(1, line - 1)
    sources = getattr(compiler, "sources", {}) or {}
    text = next((t for k, t in sources.items() if Path(k).name == name), "")
    # Direct compiler use (no tracer bookkeeping): compare with disk.
    shift = compiled_line_shift(filename, text) if text else 0
    return max(1, line - shift)
