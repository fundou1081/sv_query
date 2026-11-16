"""Shared source-line assignment scanner.

P180: one implementation for CLI evidence/profile and resolver fallback.
The scanner is deliberately textual: it chooses a *functional* LHS assignment
inside a branch, skipping reset branches, comments, and comparison operators.
"""
from __future__ import annotations

import re


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
        rf"(?:(?:default|[A-Za-z0-9_'?]+)\s*:\s*)?(?:assign\s+)?"
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


def _branch_condition(lines: list[str], lo: int, idx: int) -> str | None:
    for j in range(idx, lo - 1, -1):
        code = lines[j].split("//")[0]
        if re.search(r"\bif\s*\(", code):
            return _collect_if_condition(lines, j)
        if re.search(r"\belse\b", code):
            return ""  # plain else branch is functional
    return None


def _nearest_if_is_reset(lines: list[str], lo: int, idx: int) -> bool:
    cond = _branch_condition(lines, lo, idx)
    return bool(cond and is_reset_condition(cond))


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
    if not candidates:
        return None
    idx = min(candidates, key=lambda i: abs((i + 1) - hint))
    return idx + 1, lines[idx].strip()
