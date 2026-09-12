#!/usr/bin/env python3
"""
check_except_pass.py — 强制 AGENTS 核心纪律 2.5: 禁止 `except ...: pass`

背景 (2026-09-08 iter_190): AGENTS.md v1.4 声称 "2026-08-29 已全仓清理, 全仓
`except: pass` 计数 = 0", 但实测 src/ 里有 **52 处** (其中 25 处是
`except Exception: pass`) —— 声明没有机械保障, 于是又长回来了。本工具把它变成
**可执行检查**, 让"计数 = 0"不再靠人记。

规则:
  1. ⛔ 禁止: `except <宽类型|bare>: pass` (宽类型 = Exception / BaseException / bare)
  2. ⛔ 禁止: 任何 `except ...: pass` —— 失败必须可见 (log / 返回 sentinel / raise)
  3. ⚠️ 允许 (警告级): 收窄类型的 handler 体内是**只有注释**的空操作 (`...`)
     —— 但必须带注释说明为什么跳过合理

用法:
    python3 tools/check_except_pass.py            # 人类可读报告 (非 0 = 违规)
    python3 tools/check_except_pass.py --strict   # 警告也视为失败
"""
from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "src"
SKIP_DIRS = {"__pycache__", "_archived", "_archived_dot", ".git"}
BROAD = {"Exception", "BaseException", "bare"}


def iter_py():
    for p in sorted(SRC.rglob("*.py")):
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        yield p


def scan() -> tuple[list[tuple], list[tuple]]:
    """返回 (violations, warnings)。

    violations: (file, line, 描述) — `pass` 出现在 except 体内 (任意类型)
    warnings:   (file, line, 描述) — 收窄类型的空 handler (`...` 或仅注释), 无注释
    """
    violations: list[tuple] = []
    warnings: list[tuple] = []
    for p in iter_py():
        text = p.read_text(encoding="utf-8")
        try:
            tree = ast.parse(text)
        except SyntaxError as e:
            violations.append((p, e.lineno or 0, f"语法错误: {e.msg}"))
            continue
        lines = text.splitlines()
        for node in ast.walk(tree):
            if not isinstance(node, ast.ExceptHandler):
                continue
            etype = ast.unparse(node.type) if node.type else "bare"
            for st in node.body:
                if isinstance(st, ast.Pass):
                    kind = "宽类型" if etype in BROAD else "收窄类型"
                    violations.append(
                        (p, st.lineno, f"except {etype}: pass ({kind}) — 失败被静默吞掉")
                    )
            # 允许形态: 收窄类型 + body 只有 Ellipsis, 且带注释
            if (
                etype not in BROAD
                and len(node.body) == 1
                and isinstance(node.body[0], ast.Expr)
                and isinstance(node.body[0].value, ast.Constant)
                and node.body[0].value.value is Ellipsis
            ):
                ln = node.body[0].lineno
                has_comment = "#" in lines[ln - 1] or (
                    ln - 2 >= 0 and "#" in lines[ln - 2]
                )
                if not has_comment:
                    warnings.append(
                        (p, ln, f"except {etype}: ... 缺注释说明为何跳过合理")
                    )
    return violations, warnings


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--strict", action="store_true", help="警告也视为失败")
    args = ap.parse_args()

    violations, warnings = scan()
    print(f"检查目录: {SRC.relative_to(REPO)} (跳过 {sorted(SKIP_DIRS)})")
    if violations:
        print(f"\n⛔ 违规 {len(violations)} 处 (AGENTS 纪律 2.5: 禁止 except ...: pass):")
        for p, ln, desc in violations:
            print(f"   {p.relative_to(REPO)}:{ln}  {desc}")
    else:
        print("\n✅ except ...: pass 计数 = 0")
    if warnings:
        print(f"\n⚠️  警告 {len(warnings)} 处:")
        for p, ln, desc in warnings:
            print(f"   {p.relative_to(REPO)}:{ln}  {desc}")

    if violations:
        return 1
    if args.strict and warnings:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
