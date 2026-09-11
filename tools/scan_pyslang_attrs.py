#!/usr/bin/env python3
# scan_pyslang_attrs.py — 扫描未受保护的 pyslang 属性读取 (iter_182)
#
# 背景: pyslang 的 **属性 getter** 在非 UTF-8 identifier 下会抛
# UnicodeDecodeError (不是 str() 转换阶段) — 必须用 `safe_attr(obj, "name", d)`
# 防护; `safe_str(x.name)` 无效 (实参求值即炸)。见 docs/BENCH_BASELINE.md。
#
# 用法: python3 tools/scan_pyslang_attrs.py [--hot-only]
# 输出: file:line  接收者.属性  (启发式: 接收者名含 pyslang 常见词 + 不在
#       try/except (UnicodeDecodeError|Exception) 内)
import argparse
import ast
from pathlib import Path

RISKY = {"name", "type", "symbol", "baseClass", "body", "members",
         "elementType", "arrayElementType"}
PYSLANG_ISH = ("sym", "node", "inst", "top", "cls", "class", "module", "defn",
               "member", "port", "decl", "expr", "rhs", "lhs", "target", "sel",
               "item", "entry")
HOT = ("core/semantic/", "core/connection_extractor", "core/graph_builder",
       "core/driver_extractor", "core/load_extractor", "core/native_adapter",
       "core/module_instance_graph", "core/class_graph_builder")

REPO = Path(__file__).resolve().parents[1]


class Scanner(ast.NodeVisitor):
    def __init__(self, path):
        self.path = path
        self.trys = []
        self.rows = []

    def visit_Try(self, node):
        guards = []
        for h in node.handlers:
            t = h.type
            if isinstance(t, ast.Name):
                guards.append(t.id)
            elif isinstance(t, ast.Tuple):
                guards += [e.id for e in t.elts if isinstance(e, ast.Name)]
        self.trys.append(guards)
        self.generic_visit(node)
        self.trys.pop()

    def visit_Attribute(self, node):
        if node.attr in RISKY:
            protected = any(("UnicodeDecodeError" in g or "Exception" in g) for g in self.trys)
            val = node.value
            recv = val.id if isinstance(val, ast.Name) else (
                val.attr if isinstance(val, ast.Attribute) else None)
            if not protected and recv and any(k in recv.lower() for k in PYSLANG_ISH):
                self.rows.append((node.lineno, f"{recv}.{node.attr}"))
        self.generic_visit(node)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hot-only", action="store_true",
                    help="只看抽取热路径文件 (semantic/ extractors/ 等)")
    args = ap.parse_args()

    total, by_file = 0, []
    for p in sorted((REPO / "src").rglob("*.py")):
        if "__pycache__" in str(p):
            continue
        rel = str(p.relative_to(REPO))
        if args.hot_only and not any(k in rel for k in HOT):
            continue
        try:
            sc = Scanner(p)
            sc.visit(ast.parse(p.read_text(encoding="utf-8")))
        except SyntaxError as e:
            print(f"[skip] {rel}: {e}")
            continue
        if sc.rows:
            by_file.append((rel, sc.rows))
            total += len(sc.rows)

    print(f"未受保护的高风险 pyslang 属性读取: {total} 处")
    for rel, rows in sorted(by_file, key=lambda kv: -len(kv[1])):
        print(f"\n## {rel} ({len(rows)})")
        for ln, expr in rows[:40]:
            print(f"   {rel}:{ln}  {expr}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
