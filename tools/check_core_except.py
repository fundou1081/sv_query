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
EXPLICIT_NAMES = (
    "unknown", "partial", "error", "errors", "status", "truncated",
    "unresolved", "violations",
)


def _body_text(lines: list[str], handler: ast.ExceptHandler) -> str:
    start = handler.body[0].lineno - 1
    end = handler.body[-1].end_lineno or start + 1
    return "\n".join(lines[start:end])


def _name_has_marker(name: str) -> bool:
    lowered = name.lower()
    return any(
        lowered == marker or lowered.startswith(marker + "_")
        or lowered.endswith("_" + marker)
        for marker in EXPLICIT_NAMES)


def _is_explicit_handler(handler: ast.ExceptHandler) -> bool:
    """AST action check: comments/strings alone do not make a handler explicit."""
    for stmt in handler.body:
        for node in ast.walk(stmt):
            if isinstance(node, ast.Raise):
                return True
            if isinstance(node, ast.Return) and node.value is not None:
                if isinstance(node.value, ast.Dict):
                    for key in node.value.keys:
                        if isinstance(key, ast.Constant) and _name_has_marker(str(key.value)):
                            return True
                if isinstance(node.value, (ast.Name, ast.Attribute)):
                    label = getattr(node.value, "id", getattr(node.value, "attr", ""))
                    if _name_has_marker(str(label)):
                        return True
            if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                for target in targets:
                    label = getattr(target, "id", getattr(target, "attr", ""))
                    if _name_has_marker(str(label)):
                        return True
            if isinstance(node, ast.Call):
                func = node.func
                label = getattr(func, "id", getattr(func, "attr", ""))
                owner = getattr(func, "value", None)
                owner_name = getattr(owner, "id", getattr(owner, "attr", ""))
                if any(token in (str(label) + str(owner_name)).lower() for token in (
                        "logger", "fail", "make_error", "emit_error", "warning",
                        "violation", "error_response", "echo")):
                    return True
                if isinstance(func, ast.Attribute) and _name_has_marker(
                        getattr(func.value, "id", "")):
                    return True
    return False


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
        if not _is_explicit_handler(node):
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
