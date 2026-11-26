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


_RESET_CORE = r"(?:a?reset|s?rst|arst|nrst)n?"
_RESET_SUFFIX = r"(?:_(?:n|ni|no|b|l))?"
_RESET_EXACT = re.compile(rf"^{_RESET_CORE}{_RESET_SUFFIX}$")
_RESET_TAIL = re.compile(rf"_{_RESET_CORE}{_RESET_SUFFIX}$")


def _is_reset_token(token: str) -> bool:
    return bool(_RESET_EXACT.match(token) or _RESET_TAIL.search(token))


def _reset_identifiers(cond: str) -> list[str]:
    """Identifiers that are reset-like by whole token/tail, not substring."""
    return [m.group(0).lower()
            for m in re.finditer(r"[A-Za-z_$][A-Za-z0-9_$]*", cond or "")
            if _is_reset_token(m.group(0).lower())]


def is_reset_condition(cond: str) -> bool:
    c = (cond or "").strip().lower()
    if not c:
        return False
    # An assignment/declaration is not a condition. This prevents
    # `assign reset_counter = data;` from being classified as a reset branch.
    if re.search(r"(?<![=!<>])=(?!=)", c):
        return False
    # Whole reset tokens only: `check_reset_status` is not a reset.
    return bool(_reset_identifiers(c))


def source_expr_present(source_expr: str, text: str) -> bool:
    """RHS presence with identifier boundaries (no `data` in `metadata`)."""
    expr = " ".join((source_expr or "").split())
    if not expr or not text:
        return False
    if re.fullmatch(r"[A-Za-z_$][A-Za-z0-9_$]*(?:\.[A-Za-z_$][A-Za-z0-9_$]*)*", expr):
        return signal_token_present(expr, text)
    pattern = re.escape(expr).replace(r"\ ", r"\s+")
    return bool(re.search(rf"(?<![A-Za-z0-9_$]){pattern}(?![A-Za-z0-9_$])", text))


def signal_token_present(signal: str, text: str) -> bool:
    """Whole-identifier match of the signal leaf (no `data` in `metadata`)."""
    leaf = (signal or "").rsplit(".", 1)[-1].split("[", 1)[0]
    if not leaf or not text:
        return False
    return bool(re.search(rf"(?<![A-Za-z0-9_$]){re.escape(leaf)}(?![A-Za-z0-9_$])", text))


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
    tokens = _reset_identifiers(cond or "")
    return tokens[0] if tokens else ""


def _active_low_reset(cond: str) -> bool:
    token = _reset_token(cond)
    if not token:
        return False
    if token.startswith("n") or "_n" in token:
        return True
    return token.endswith(("n", "ni", "no", "b", "l"))


def _literal_value(token: str) -> int | None:
    token = token.replace("_", "").strip()
    if "'" not in token:
        try:
            return int(token)
        except ValueError:
            return None
    width, rest = token.split("'", 1)
    if not rest:
        return None
    base = rest[0].lower()
    digits = rest[1:]
    if not digits or re.search(r"[xz]", digits, re.I):
        return None
    try:
        return int(digits, {"b": 2, "d": 10, "h": 16, "o": 8}.get(base, 10))
    except ValueError:
        return None


def reset_literal_value(cond: str) -> int | None:
    """Value of a reset comparison literal, or None for non-literals."""
    m = re.search(
        r"(?:==|!=)\s*((?:\d+\s*)?'[bdhoBDHO][0-9a-fA-FxXzZ_]+|\d+)",
        cond or "", re.I)
    if not m:
        return None
    return _literal_value(m.group(1))


def _active_reset_branch(cond: str) -> bool:
    c = (cond or "").strip()
    if not is_reset_condition(c):
        return False
    assert_level = 0 if _active_low_reset(c) else 1
    value = reset_literal_value(c)
    if value is not None:
        return value == assert_level if "==" in c else value != assert_level
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


def signal_is_active_low(name: str) -> bool:
    """Active-low reset signal name (rst_n, rst_ni, resetn, ...)."""
    return _active_low_reset(name)
