"""Map a conditional driver edge to its assignment line.

The edge keeps the condition AST line; for evidence we need the assignment
statement. A file-wide "last assignment" is wrong across generate/preprocessor
branches, so score candidate LHS lines by RHS expression and condition tokens.
Filelist sources often carry a bare basename; fall back to the compiler's
source map instead of silently failing.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

from .source_assignment import compiled_line_shift, line_is_lhs

logger = logging.getLogger(__name__)

_IDENT = re.compile(r"[A-Za-z_$][A-Za-z0-9_$]*")
_KEYWORDS = frozenset({
    "if", "else", "case", "begin", "end", "always", "assign", "and", "or",
    "not", "posedge", "negedge", "true", "false",
})


def _source_text(adapter, filename: str) -> tuple[str, int] | None:
    path = Path(filename)
    if path.is_file():
        return path.read_text(errors="ignore"), 0
    compiler = getattr(adapter, "_compiler", None)
    sources = getattr(compiler, "sources", {}) or {}
    name = path.name
    matches = [text for key, text in sources.items() if Path(key).name == name]
    if len(matches) != 1:
        return None
    text = matches[0]
    return text, compiled_line_shift(filename, text)


def _rhs(line: str) -> str:
    code = line.split("//", 1)[0].strip()
    m = re.search(r"(?:<=|=(?!=))\s*(.*?);?\s*$", code)
    return re.sub(r"\s+", "", m.group(1)) if m else ""


def _tokens(text: str) -> set[str]:
    return {t for t in _IDENT.findall(text or "") if t not in _KEYWORDS}


def _score_candidate(raw: str, context: list[str], cond_tokens: set[str],
                     want_expr: str) -> int:
    score = len(cond_tokens & _tokens("\n".join(context))) * 10
    rhs = _rhs(raw)
    if want_expr and (rhs == want_expr or want_expr in rhs):
        score += 50
    if cond_tokens and any(token in raw for token in cond_tokens):
        score += 20
    return score


def find_assignment_line(adapter, filename: str, signal: str,
                         expression: str, condition: str,
                         hint: int) -> int | None:
    resolved = _source_text(adapter, filename)
    if resolved is None:
        return None
    text, shift = resolved
    lines = text.splitlines()
    leaf = signal.rsplit(".", 1)[-1].split("[", 1)[0]
    want_expr = re.sub(r"\s+", "", expression or "")
    cond_tokens = _tokens(condition)
    best: tuple[int, int] | None = None
    for idx, raw in enumerate(lines):
        if not line_is_lhs(raw, leaf):
            continue
        context = lines[max(0, idx - 6):idx + 1]
        score = _score_candidate(raw, context, cond_tokens, want_expr)
        distance = abs((idx + 1) - hint)
        rank = (score, -distance)
        if best is None or rank > best[0]:
            best = (rank, idx + 1)
    if best is None:
        return None
    return max(1, best[1] - shift)
