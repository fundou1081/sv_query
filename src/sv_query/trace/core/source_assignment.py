"""Shared source-line assignment scanner.

P180: one implementation for CLI evidence/profile and resolver fallback.
The scanner is deliberately textual: it chooses a *functional* LHS assignment
inside a branch, skipping reset branches, comments, and comparison operators.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)


def is_reset_condition(cond: str) -> bool:
    c = (cond or "").strip().lower()
    return bool(re.search(r"(?:^|[^a-z0-9])(?:a?reset|s?rst|arst|nrst)\w*", c)) \
        and "&&" not in c and "||" not in c


def strip_block_comments(text: str) -> str:
    def _blank(match):
        return "".join("\n" if ch == "\n" else " " for ch in match.group(0))
    return re.sub(r"/\*.*?\*/", _blank, text, flags=re.S)


def line_is_lhs(text: str, signal: str) -> bool:
    leaf = signal.rsplit(".", 1)[-1]
    code = strip_block_comments(text or "").split("//")[0].strip()
    pat = re.compile(
        rf"^(?:else\s+)?(?:if\s*\([^)]*\)\s*)?"
        rf"(?:always(?:_comb|_ff|_latch)?\s+)?(?:begin\s+)?"
        rf"(?:[^:;]+:\s*)?(?:begin\s+)?(?:assign\s+)?"
        rf"{re.escape(leaf)}\b\s*(?:\[[^\]]+\])?\s*(?:<=|=(?!=))")
    return bool(pat.search(code))


def _collect_if_condition(lines: list[str], idx: int) -> str | None:
    text = "\n".join(lines[idx:idx + 8])
    m = re.search(r"\bif\s*\(", text)
    if not m:
        return None
    depth, start = 1, m.end()
    for pos in range(start, len(text)):
        if text[pos] == "(":
            depth += 1
        elif text[pos] == ")":
            depth -= 1
            if depth == 0:
                return text[start:pos]
    return text[start:]


def _reset_token(cond: str) -> str:
    m = re.search(r"(?:a?reset|s?rst|arst|nrst)\w*", cond or "", re.I)
    return m.group(0).lower() if m else ""


def _active_low_reset(cond: str) -> bool:
    token = _reset_token(cond)
    if not token:
        return False
    if token.startswith("n") or "_n" in token:
        return True
    return token.endswith(("n", "ni", "no", "b", "l"))


def _active_reset_branch(cond: str) -> bool:
    c = (cond or "").strip()
    if not is_reset_condition(c):
        return False
    assert_level = 0 if _active_low_reset(c) else 1
    m = re.search(r"(==|!=)\s*(?:\d+\s*'([bdho]))?([0-9a-fA-F]+)", c)
    if m:
        base = {"b": 2, "d": 10, "h": 16, "o": 8}.get((m.group(2) or "d").lower(), 10)
        value = int(m.group(3), base)
        return value == assert_level if m.group(1) == "==" else value != assert_level
    if "!" in c:
        return True
    return not _active_low_reset(c)


def _nearest_if_is_reset(lines: list[str], lo: int, idx: int) -> bool:
    for j in range(idx, lo - 1, -1):
        code = lines[j].split("//")[0]
        if re.search(r"\bif\s*\(", code):
            cond = _collect_if_condition(lines, j) or ""
            return _active_reset_branch(cond)
        if re.search(r"\belse\b", code):
            for k in range(j - 1, lo - 1, -1):
                prev = lines[k].split("//")[0]
                if re.search(r"\bif\s*\(", prev):
                    cond = _collect_if_condition(lines, k) or ""
                    return is_reset_condition(cond) and not _active_reset_branch(cond)
            return False
    return False


def find_functional_assignment(signal: str, file_text: str,
                               start: int, end: int) -> tuple[int, str] | None:
    """Find the non-reset LHS assignment line for a signal in a source range."""
    lines = strip_block_comments(file_text).splitlines()
    lo = max(0, start - 1)
    hi = min(len(lines), end if end else len(lines))
    candidates = [i for i in range(lo, hi) if line_is_lhs(lines[i], signal)]
    for idx in reversed(candidates):
        if _nearest_if_is_reset(lines, lo, idx):
            continue
        return idx + 1, lines[idx].strip()
    return None


def find_assignment_near(signal: str, file_text: str,
                         hint: int, window: int = 16) -> tuple[int, str] | None:
    """Find a functional assignment near a hint line, then any nearest LHS."""
    lines = strip_block_comments(file_text).splitlines()
    hint = int(hint or 1)
    lo = max(0, hint - window - 1)
    hi = min(len(lines), hint + window)
    candidates = [i for i in range(lo, hi)
                  if line_is_lhs(lines[i], signal)
                  and not _nearest_if_is_reset(lines, lo, i)]
    if candidates:
        idx = min(candidates, key=lambda i: abs((i + 1) - hint))
        return idx + 1, lines[idx].strip()
    any_lhs = [i for i in range(lo, hi) if line_is_lhs(lines[i], signal)]
    if not any_lhs:
        return None
    idx = min(any_lhs, key=lambda i: abs((i + 1) - hint))
    return idx + 1, lines[idx].strip()


def compiled_line_shift(filename: str, full_text: str) -> int:
    """Return 1 when preprocessing prepended a timescale line."""
    if not full_text or not full_text.lstrip().startswith("`timescale"):
        return 0
    try:
        disk = Path(filename).read_text(errors="ignore")
    except OSError as exc:
        logger.debug("compiled_line_shift read failed for %s: %s", filename, exc)
        return 0
    return 0 if disk.lstrip().startswith("`timescale") else 1
