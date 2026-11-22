#!/usr/bin/env python3
"""P193.4: core query/library paths must not swallow exceptions.

Scans core CLI query modules plus the tracer/cache/session library. A broad ``except Exception`` (or bare
``except``) is acceptable only when its body makes failure explicit:
unknown/partial/error/errors/raise/logger/fail/make_error/violations.
"""
from __future__ import annotations

import argparse
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CORE_FILES = (
    "src/sv_query/cli/core/semantic/trace.py",
    "src/sv_query/cli/core/semantic/paths.py",
    "src/sv_query/cli/core/semantic/verify.py",
    "src/sv_query/cli/core/semantic/dataflow.py",
    "src/sv_query/cli/core/semantic/trace_evidence.py",
    "src/sv_query/trace/unified_tracer.py",
    "src/sv_query/graph_session.py",
    "src/sv_query/session.py",
    "src/sv_query/cli/core/locate/session_cmd.py",
    "src/sv_query/trace/core/cache/ast_cache.py",
    "src/sv_query/trace/core/cache/build_identity.py",
)
MARKERS = (
    "unknown", "partial", "error", "errors", "raise", "logger",
    "make_error", "fail(", "warning", "violations", "status",
)


def _body_text(lines: list[str], handler: ast.ExceptHandler) -> str:
    start = handler.body[0].lineno - 1
    end = handler.body[-1].end_lineno or start + 1
    return "\n".join(lines[start:end])


def scan_source(path: Path) -> list[tuple[int, str]]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    tree = ast.parse(text)
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ExceptHandler):
            continue
        is_broad = node.type is None or (
            isinstance(node.type, ast.Name) and node.type.id == "Exception")
        if not is_broad:
            continue
        body = _body_text(lines, node)
        if not any(marker in body.lower() for marker in MARKERS):
            found.append((node.lineno, body.strip().splitlines()[0][:120]))
    return found


def scan(root: Path = ROOT) -> list[str]:
    issues = []
    for rel in CORE_FILES:
        path = root / rel
        if not path.is_file():
            issues.append(f"missing core file: {rel}")
            continue
        for line, first in scan_source(path):
            issues.append(f"{rel}:{line}: silent broad except: {first}")
    return issues


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(ROOT))
    args = parser.parse_args(argv)
    issues = scan(Path(args.root))
    if issues:
        for issue in issues:
            print(f"FAIL\t{issue}")
        print(f"core-except: FAIL ({len(issues)} silent handlers)")
        return 1
    print(f"core-except: PASS ({len(CORE_FILES)} core files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
