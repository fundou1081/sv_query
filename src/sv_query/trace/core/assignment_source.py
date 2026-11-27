"""Semantic assignment source locations normalized to disk line numbers."""
from __future__ import annotations

from pathlib import Path

from .source_assignment import compiled_line_shift


def disk_line(adapter, filename: str, line: int) -> int:
    """Map a preprocessed semantic line back to the on-disk file line."""
    if not filename or not line:
        return line
    compiler = getattr(adapter, "_compiler", None)
    sources = getattr(compiler, "sources", {}) or {}
    name = Path(filename).name
    text = next((t for k, t in sources.items() if Path(k).name == name), "")
    shift = compiled_line_shift(filename, text) if text else 0
    if shift == 0 and text.lstrip().startswith("`timescale"):
        # Inline ``sources`` have no on-disk file to compare against, but the
        # compiler added one timescale line.
        if not Path(filename).is_file():
            shift = 1
    return max(1, line - shift)
