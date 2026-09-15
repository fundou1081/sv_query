#!/usr/bin/env python3
"""
scan_strict.py — `strict` 移除的**精确清单工具** (只读, 不改代码) [iter_219]

背景: `strict` 的移除用"正则批量删"已回退 4 次 (iter_216/217/218), 根因是**形态没穷举**:
  - 形参: 位置-only / 位置或关键字 / 关键字-only, 带默认值或不带
  - 实参: `strict=x` (关键字) / **位置传参** (第 N 个位置参数) ← 正则看不见, 但它会让
    删形参后**位置错位** → 静默行为错 (iter_218 的 116 failed 最可能就是这个)
  - 引用: 裸 `strict` / `self._strict`

本工具用 AST 输出**逐文件清单 + 数量**, 并与 `grep -c strict` 对账, 供"逐文件改 + 逐文件
验证"使用。**不做任何修改**。

用法:
    python3 tools/scan_strict.py            # 人类可读清单 + 汇总
    python3 tools/scan_strict.py --summary  # 只看汇总
"""
from __future__ import annotations

import argparse
import ast
import collections
import pathlib
import subprocess

REPO = pathlib.Path(__file__).resolve().parents[1]
ROOTS = ("src", "tools", "sim/tests", "run_cli.py")
SKIP = ("__pycache__", "_archived", "_archived_dot")


def iter_py():
    for root in ROOTS:
        p = REPO / root
        files = [p] if p.is_file() else sorted(p.rglob("*.py"))
        for f in files:
            if any(s in f.parts for s in SKIP):
                continue
            yield f


def scan_file(path: pathlib.Path) -> dict:
    """返回 {params, kwargs, positional, refs, self_attr} 五类清单。"""
    src = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        return {"syntax_error": e.lineno}
    out = {k: [] for k in ("params", "kwargs", "positional", "refs", "self_attr")}
    # 1) 形参
    strict_index: dict[str, int] = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = node.args
            allp = list(args.posonlyargs) + list(args.args) + list(args.kwonlyargs)
            for i, a in enumerate(allp):
                if a.arg == "strict":
                    kind = ("posonly" if i < len(args.posonlyargs)
                            else "pos_or_kw" if i < len(args.posonlyargs) + len(args.args)
                            else "kwonly")
                    default = "有默认值" if (a in args.defaults or a in args.kw_defaults
                                             or any(d is not None for d in args.kw_defaults)) else "无默认值"
                    out["params"].append((node.lineno, f"{node.name}(...) 第{i}个参数 [{kind}] {default}"))
                    if kind != "kwonly":
                        strict_index.setdefault(node.name, i)
    # 2) 实参 (关键字 + 位置)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fname = None
        f = node.func
        if isinstance(f, ast.Name):
            fname = f.id
        elif isinstance(f, ast.Attribute):
            fname = f.attr
        for kw in node.keywords:
            if kw.arg == "strict":
                out["kwargs"].append((kw.value.lineno, f"{fname or '?'}(..., strict=...)"))
        if fname in strict_index and len(node.args) > strict_index[fname]:
            idx = strict_index[fname]
            out["positional"].append(
                (node.args[idx].lineno, f"{fname}(...) 位置第{idx}个参数传了 strict ← 正则看不见")
            )
    # 3) 引用
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id == "strict" and isinstance(node.ctx, ast.Load):
            out["refs"].append((node.lineno, "裸 strict 引用"))
        if (isinstance(node, ast.Attribute) and node.attr == "_strict"):
            out["self_attr"].append((node.lineno, f"{ast.unparse(node)[:40]}"))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--summary", action="store_true")
    args = ap.parse_args()

    totals = collections.Counter()
    per_file: list[tuple[str, collections.Counter]] = []
    detail: list[tuple[str, dict]] = []
    for f in iter_py():
        src = f.read_text(encoding="utf-8")
        if "strict" not in src:
            continue
        r = scan_file(f)
        c = collections.Counter({k: len(v) for k, v in r.items() if isinstance(v, list)})
        if sum(c.values()) == 0:
            continue
        per_file.append((str(f.relative_to(REPO)), c))
        detail.append((str(f.relative_to(REPO)), r))
        totals.update(c)

    if not args.summary:
        for name, r in detail:
            print(f"\n=== {name}")
            for kind, label in (("params", "形参"), ("kwargs", "关键字实参"),
                                ("positional", "位置实参 ⚠️"), ("refs", "裸引用"),
                                ("self_attr", "self._strict")):
                for ln, desc in r.get(kind, []):
                    print(f"   {ln:>5} [{label}] {desc}")
            if "syntax_error" in r:
                print(f"   ❌ 语法错误 行 {r['syntax_error']}")

    print("\n===== 汇总 (按类别) =====")
    for k, label in (("params", "形参"), ("kwargs", "关键字实参"),
                     ("positional", "位置实参 ⚠️ (删形参会错位)"), ("refs", "裸引用"),
                     ("self_attr", "self._strict")):
        print(f"  {label}: {totals[k]}")
    print(f"  合计: {sum(totals.values())} 处, 涉及 {len(per_file)} 文件")

    print("\n===== 按文件 Top =====")
    for name, c in sorted(per_file, key=lambda x: -sum(x[1].values()))[:12]:
        print(f"  {sum(c.values()):>3}  {name}  ({dict(c)})")

    # 与 grep 对账 (行级, 含注释/字符串 → 应 >= AST 计数)
    g = subprocess.run(["grep", "-rc", "strict", "--include=*.py", "src", "tools", "sim/tests"],
                       cwd=REPO, capture_output=True, text=True)
    grep_lines = sum(int(l.rsplit(":", 1)[1]) for l in g.stdout.strip().splitlines() if ":" in l)
    print(f"\n===== 对账 =====\n  AST 命中: {sum(totals.values())} 处 | grep 行数: {grep_lines} "
          f"(grep 含注释/字符串/docstring, 应 >= AST)")
    print(f"  ⚠️ 位置实参 {totals['positional']} 处 —— 这是正则方法看不见、也是 iter_218 恶化的最可能根源")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
