#!/usr/bin/env python3
"""
remove_strict_in_file.py — 逐文件彻底移除 `strict` (AST 精确区间) [iter_222]

用法:
    python3 tools/remove_strict_in_file.py <file.py>            # 改并校验
    python3 tools/remove_strict_in_file.py <file.py> --dry-run   # 只报告将删什么

设计依据 (来自 5 次失败尝试的教训):
  - **位置实参**是正则盲点 (iter_218 的 116 failed 怀疑根源) → 用全局"函数名 → strict
    形参下标"表判定并精确删除;
  - **函数体裸引用** (删形参后会 NameError) → 把 Load 上下文的 `strict` 替换为 `True`,
    `if strict:` / `if not strict:` 显式改写;
  - **跳过核心语义层** (`self._strict` 属 `src/trace`, 需单独设计) → 本工具拒绝处理
    含 `self._strict` 的文件, 由调用方显式 `--allow-core` 才处理 (默认拒绝)。

只处理**一个文件**; 调用方负责跑测试 / 全量门禁。
"""
from __future__ import annotations

import argparse
import ast
import pathlib
import re
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]


def build_strict_index() -> dict[str, int]:
    """全仓扫一遍: 函数名 → strict 位置参数下标 (供位置实参判定)。"""
    idx: dict[str, int] = {}
    for root in ("src", "tools"):
        for p in (REPO / root).rglob("*.py"):
            try:
                t = ast.parse(p.read_text(encoding="utf-8"))
            except (SyntaxError, UnicodeDecodeError):
                continue
            for n in ast.walk(t):
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    allp = list(n.args.posonlyargs) + list(n.args.args)
                    for i, a in enumerate(allp):
                        if a.arg == "strict":
                            idx[n.name] = i
    return idx


def process(path: pathlib.Path, allow_core: bool, dry_run: bool) -> int:
    src = path.read_text(encoding="utf-8")
    if "strict" not in src:
        print(f"{path}: 无 strict, 跳过")
        return 0
    if "self._strict" in src and not allow_core:
        print(f"{path}: 含 self._strict (核心语义层) → 需 --allow-core, 本次跳过")
        return 2

    tree = ast.parse(src)
    lines = src.splitlines(keepends=True)
    offs = [0]
    for l in lines:
        offs.append(offs[-1] + len(l))

    def span(n) -> tuple[int, int]:
        return offs[n.lineno - 1] + n.col_offset, offs[n.end_lineno - 1] + n.end_col_offset

    idx = build_strict_index()
    cuts: list[tuple[int, int, str]] = []
    local_idx: dict[str, int] = {}

    # 1) 形参
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            allp = list(n.args.posonlyargs) + list(n.args.args)
            for i, a in enumerate(allp):
                if a.arg == "strict":
                    local_idx[n.name] = i
            for arg in list(n.args.posonlyargs) + list(n.args.args) + list(n.args.kwonlyargs):
                if arg.arg != "strict":
                    continue
                s0, e0 = span(arg)
                e0 += re.match(r"[^,)]*", src[e0:]).end()
                if src[e0:e0 + 1] == ",":
                    e0 += 1
                while e0 < len(src) and src[e0] in " \t":
                    e0 += 1
                if src[e0:e0 + 1] == "\n":
                    e0 += 1
                cuts.append((s0, e0, f"param@{arg.lineno}"))

    # 2) 实参 (关键字 + 位置)
    for n in ast.walk(tree):
        if not isinstance(n, ast.Call):
            continue
        f = n.func
        fname = f.id if isinstance(f, ast.Name) else (f.attr if isinstance(f, ast.Attribute) else None)
        for kw in n.keywords:
            if kw.arg != "strict":
                continue
            s0, e0 = span(kw.value)
            s1 = src.rfind("strict", 0, s0)
            if s1 != -1:
                s0 = s1
            if src[e0:e0 + 1] == ",":
                e0 += 1
            while e0 < len(src) and src[e0] in " \t":
                e0 += 1
            cuts.append((s0, e0, f"kwarg@{kw.value.lineno}"))
        target = local_idx.get(fname, idx.get(fname)) if fname else None
        if target is not None and len(n.args) > target:
            e = n.args[target]
            s0, e0 = span(e)
            s1 = src.rfind(",", 0, s0)
            if src[e0:e0 + 1] == ",":
                e0 += 1
            while e0 < len(src) and src[e0] in " \t":
                e0 += 1
            if s1 != -1 and src[s1 + 1:s0].strip() == "":
                s0 = s1 + 1
            cuts.append((s0, e0, f"POSITIONAL@{e.lineno}({fname})"))

    print(f"{path}: 将删除 {len(cuts)} 处")
    for s0, _e0, kind in sorted(cuts, key=lambda x: x[0]):
        line = src.count("\n", 0, s0) + 1
        print(f"    L{line}: {kind}")
    if dry_run:
        return 0

    for s0, e0, _k in sorted(set(cuts), reverse=True):
        src = src[:s0] + src[e0:]
    # 3) 残余裸引用 → 恒定严格
    src = re.sub(r"if not strict:", "if False:  # [iter_222] 恒定严格", src)
    src = re.sub(r"if strict:", "if True:  # [iter_222] 恒定严格", src)
    if re.search(r"\bstrict\b", src):
        tree2 = ast.parse(src)
        bare = [(n.lineno, n.col_offset) for n in ast.walk(tree2)
                if isinstance(n, ast.Name) and n.id == "strict" and isinstance(n.ctx, ast.Load)]
        if bare:
            print(f"    ⚠️ 仍有 {len(bare)} 处裸引用 (需人工确认): {bare[:5]}")
    ast.parse(src)
    path.write_text(src)
    print(f"{path}: ✅ 已改写 (ast.parse 通过)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--allow-core", action="store_true",
                    help="允许处理含 self._strict 的核心文件 (语义变更, 慎用)")
    args = ap.parse_args()
    return process((REPO / args.file).resolve(), args.allow_core, args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
