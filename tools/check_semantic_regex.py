#!/usr/bin/env python3
"""check_semantic_regex.py — 语义提取 regex 纪律检查。

规则：class/constraint/covergroup/UVM 的**语义提取**必须走 pyslang
semantic AST；源码文本 regex 仅允许 UVM 宏/调用部分（预处理会去掉宏）。

允许：src/sv_query/trace/core/query/uvm.py
其他列出的语义模块出现 `import re` / `re.*xx` 即违规。
"""
from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ALLOWED = {"src/sv_query/trace/core/query/uvm.py"}
TARGETS = [
    "src/sv_query/trace/core/class_graph_builder.py",
    "src/sv_query/trace/core/covergroup_extractor.py",
    "src/sv_query/trace/core/query/constraint.py",
    "src/sv_query/trace/core/query/covergroup.py",
    "src/sv_query/trace/core/query/uvm.py",
    "src/sv_query/trace/core/semantic/classes.py",
    "src/cli/core/semantic/classes.py",
    "src/cli/core/semantic/constraints.py",
    "src/cli/core/semantic/covergroups.py",
]


def scan_text(text: str, rel: str) -> list[dict]:
    """返回 [{file,line,kind}]；允许文件返回空。"""
    if rel in ALLOWED:
        return []
    try:
        tree = ast.parse(text)
    except SyntaxError as e:
        return [{"file": rel, "line": e.lineno or 0, "kind": "syntax_error"}]
    bad = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.name == "re":
                    bad.append({"file": rel, "line": node.lineno, "kind": "import_re"})
        elif isinstance(node, ast.ImportFrom):
            if node.module == "re":
                bad.append({"file": rel, "line": node.lineno, "kind": "from_re"})
        elif isinstance(node, ast.Attribute):
            if isinstance(node.value, ast.Name) and node.value.id == "re":
                bad.append({"file": rel, "line": getattr(node, "lineno", 0),
                            "kind": f"re.{node.attr}"})
    return bad


def run() -> list[dict]:
    out = []
    for rel in TARGETS:
        path = ROOT / rel
        if not path.exists():
            out.append({"file": rel, "line": 0, "kind": "missing_file"})
            continue
        out.extend(scan_text(path.read_text(encoding="utf-8"), rel))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    violations = run()
    data = {"ok": not violations, "allowed": sorted(ALLOWED),
            "targets": TARGETS, "violations": violations}
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        if violations:
            print("⛔ 语义提取 regex 违规:")
            for v in violations:
                print(f"  {v['file']}:{v['line']} {v['kind']}")
        else:
            print(f"✅ 语义 regex 检查通过 ({len(TARGETS)} files)")
    return 0 if not violations else 1


if __name__ == "__main__":
    sys.exit(main())
