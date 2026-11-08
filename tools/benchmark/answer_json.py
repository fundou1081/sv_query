"""Tolerant final-answer parser for benchmark agents.

Strict JSON is always tried first. Some models occasionally emit a JSON object
with single-quoted string literals (for example `{"task_id":'x'}`); this helper
repairs that one syntax-level defect and reports whether repair was needed.
It does not infer missing content or change answer values.
"""
from __future__ import annotations

import json
import re

import run_long_range as base


def _object_at(text: str, start: int) -> str | None:
    depth = 0
    in_str = False
    quote = ""
    escaped = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == quote:
                in_str = False
            continue
        if ch in "\"'":
            in_str = True
            quote = ch
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    return None


def parse_answer_json(text: str) -> tuple[dict | None, bool]:
    """Return (object, repaired). Strict JSON wins; repaired is best-effort."""
    strict = base._extract_json(text)
    if isinstance(strict, dict) and ("task_id" in strict or "answer" in strict):
        return strict, False
    for m in re.finditer(r"\{", text):
        raw = _object_at(text, m.start())
        if not raw:
            continue
        fixed = re.sub(r"(?<![A-Za-z0-9_])'([^'\\]*)'(?![A-Za-z0-9_])",
                       lambda x: json.dumps(x.group(1)), raw)
        try:
            obj = json.loads(fixed)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and ("task_id" in obj or "answer" in obj):
            return obj, True
    return None, False
