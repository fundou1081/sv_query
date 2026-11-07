"""[P91 / A] Top-aware filelist pruning (conservative, opt-in).

Goal: when a huge filelist contains modules that cannot be reached from the
requested top, drop them *before* pyslang elaboration. This is a candidate
reduction, never a semantic replacement: any uncertainty keeps the file.

The scan is textual (comments/strings stripped), and deliberately over-approximates:
a file is kept if it declares the top, declares a referenced module, declares a
package/interface/program, has no module declaration (headers), or cannot be read.
If the top is missing/ambiguous, all files are returned.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

_DECL_RE = re.compile(
    r"\b(module|macromodule|interface|package|program)\s+"
    r"(?:(?:automatic|static)\s+)?([A-Za-z_]\w*)"
)
_TOKEN_RE = re.compile(r"\b[A-Za-z_]\w*\b")


def _strip_comments_and_strings(text: str) -> str:
    """Remove //, /* */, and quoted strings without changing token separation."""
    out: list[str] = []
    i, n = 0, len(text)
    while i < n:
        if text.startswith("//", i):
            j = text.find("\n", i)
            i = n if j < 0 else j
            out.append(" ")
        elif text.startswith("/*", i):
            j = text.find("*/", i + 2)
            i = n if j < 0 else j + 2
            out.append(" ")
        elif text[i] == '"':
            i += 1
            while i < n and text[i] != '"':
                i += 2 if text[i] == "\\" else 1
            i = min(i + 1, n)
            out.append(" ")
        else:
            out.append(text[i])
            i += 1
    return "".join(out)


@dataclass
class PruneResult:
    selected: list[str]
    total: int
    reason: str
    top: str | None = None
    declarations: dict[str, list[str]] = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "top": self.top,
            "total_files": self.total,
            "selected_files": self.selected,
            "selected_count": len(self.selected),
            "dropped": max(0, self.total - len(self.selected)),
            "reason": self.reason,
            "declarations": self.declarations,
        }


def _scan(sources: dict[str, str]) -> tuple[dict[str, str], dict[str, list[str]], set[str], str]:
    """Strip comments/strings and collect declarations. Never raises to caller."""
    clean: dict[str, str] = {}
    decls: dict[str, list[str]] = {}
    special: set[str] = set()
    for path, text in sources.items():
        try:
            stripped = _strip_comments_and_strings(text)
        except Exception:
            return {}, {}, set(), "scan_error"
        clean[path] = stripped
        found = _DECL_RE.findall(stripped)
        if not found:
            special.add(path)  # headers / include-only files: keep
            continue
        for kind, name in found:
            decls.setdefault(name, []).append(path)
            if kind in ("package", "interface", "program", "macromodule"):
                special.add(path)
    return clean, decls, special, ""


def _reachable(
    clean: dict[str, str], decls: dict[str, list[str]], special: set[str],
    top_files: list[str],
) -> set[str]:
    """Over-approximate file references; extra edges only keep files."""
    names = set(decls)
    edges: dict[str, set[str]] = {p: set() for p in clean}
    for path, text in clean.items():
        for tok in set(_TOKEN_RE.findall(text)) & names:
            edges[path].update(decls[tok])

    selected: set[str] = set(special)
    queue = list(top_files)
    while queue:
        path = queue.pop(0)
        if path in selected:
            continue
        selected.add(path)
        queue.extend(edges.get(path, ()))
    return selected


def prune_sources(sources: dict[str, str], top: str | None) -> PruneResult:
    """Return a conservative subset of *sources* reachable from *top*."""
    files = list(sources)
    if not top:
        return PruneResult(files, len(files), "no_top", None)

    clean, decls, special, reason = _scan(sources)
    if reason:
        return PruneResult(files, len(files), reason, top)

    top_files = sorted(set(decls.get(top, [])))
    if not top_files:
        return PruneResult(files, len(files), "top_not_found", top, decls)

    selected = _reachable(clean, decls, special, top_files)
    ordered = [p for p in files if p in selected]
    reason = "reachable" if len(ordered) < len(files) else "nothing_to_prune"
    return PruneResult(ordered, len(files), reason, top, decls)
