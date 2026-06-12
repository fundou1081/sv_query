# -*- coding: utf-8 -*-
"""
fix_widths.py - 用 syntax tree + pyslang.clog2 解析 typedef 真实位宽

[ADD 2026-06-12] 回答用户问题 'macro 展开用语义 AST 不能直接拿到结果吗?'
的发现: 语义 AST 本身不能拿 macro 值 (macro 是 preprocessor 层),
但 pyslang 暴露了 clog2(SVInt) 跟 SVInt(bits, value, signed),
配合 syntax tree, 我们可以绕过 macro 展开, 直接拿 $clog2(\`MACRO) 的结果.

Workflow:
1. 走 compilation.getSyntaxTrees() 拿所有 syntax tree (164+ typedefs in NaplesPU)
2. 找含 $clog2(\`MACRO) 或 $clog2(LITERAL) 的 typedef
3. 对 literal 直接用 pyslang.clog2(SVInt) 算
4. 对 macro 从 source 文件 parse 宏值, 再用 pyslang.clog2
5. 输出: 'typedef foo_t 真实位宽 = N bits' 给 elaboration 失败的 typedef

不依赖:
- macro 展开 (slang 自己的 preprocessor)
- filelist 顺序
- elaboration 成功 (syntax tree 永远在 elaboration 之前可用)
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Optional

import typer

from cli._common import _build_tracer

# [ADD 2026-06-12] pyslang 暴露 clog2 + SVInt
import pyslang


# ----------------------------------------------------------------------------
# 核心算法
# ----------------------------------------------------------------------------

# 匹配 $clog2(...) 的参数 (字面常量 OR `MACRO)
CLOG2_PATTERN = re.compile(r'\$clog2\s*\(\s*(?:(\d+)|`(\w+))\s*\)')


def _get_syntax_trees_typedefs(tracer) -> list:
    """拿所有 syntax tree 的 TypedefDeclarationSyntax 节点"""
    if not tracer._compiler or not tracer._compiler._comp:
        return []
    comp = tracer._compiler._comp
    all_typedefs = []
    try:
        for st in comp.getSyntaxTrees():
            try:
                def walk(node):
                    if 'TypedefDeclaration' in type(node).__name__:
                        all_typedefs.append(node)
                    if hasattr(node, 'members') and node.members:
                        for m in node.members:
                            walk(m)
                walk(st.root)
            except Exception:
                pass
    except Exception:
        pass
    return all_typedefs


def _parse_clog2_from_text(text: str) -> Optional[tuple[str, int | str]]:
    """从 typedef 节点文本里找 $clog2(X), 返回 (match_str, value or macro_name)"""
    m = CLOG2_PATTERN.search(text)
    if not m:
        return None
    literal, macro_name = m.group(1), m.group(2)
    if literal:
        return (m.group(0), int(literal))
    elif macro_name:
        return (m.group(0), macro_name)
    return None


def _resolve_macro_value(macro_name: str, sources: dict[str, str]) -> Optional[int]:
    """从 sources dict 里 grep `\`<macro_name>` 定义, 解析成 int

    支持:
    - `define FOO 4            → 4
    - `define FOO `OTHER_MACRO  → 递归解析
    - `define FOO 4+1          → 解析表达式 (e.g. 4+1=5)
    """
    visited = set()

    def _resolve(name: str) -> Optional[int]:
        if name in visited:
            return None  # 循环引用
        visited.add(name)
        # [FIX 2026-06-12] 每次 build pattern 用当前 name, 支持嵌套宏递归
        define_pattern = re.compile(r"`define\s+" + re.escape(name) + r"\s+(.+?)(?:\n|$)")
        for content in sources.values():
            m = define_pattern.search(content)
            if m:
                value_str = m.group(1).strip()
                # 处理 backtick 引用
                inner_macro = re.match(r"^`(\w+)$", value_str)
                if inner_macro:
                    return _resolve(inner_macro.group(1))
                # 处理字面数字
                if re.match(r"^\d+$", value_str):
                    return int(value_str)
                # 处理算术表达式 (简化: 只取第一个数字)
                digit_m = re.search(r"\b(\d+)\b", value_str)
                if digit_m:
                    return int(digit_m.group(1))
                return None
        return None

    return _resolve(macro_name)


def _evaluate_clog2(value_or_macro: int | str, sources: dict[str, str]) -> Optional[int]:
    """对 int 直接用 pyslang.clog2, 对 str (macro name) 先解析值"""
    if isinstance(value_or_macro, int):
        v = value_or_macro
    else:
        v = _resolve_macro_value(value_or_macro, sources)
        if v is None:
            return None
    # 用 pyslang.clog2 + SVInt 算
    try:
        sv = pyslang.SVInt(32, v, False)  # SVInt(bits, value, isSigned)
        return pyslang.clog2(sv)
    except Exception:
        return None


# ----------------------------------------------------------------------------
# CLI 命令
# ----------------------------------------------------------------------------

def fix_widths_cmd(
    filelist: str = typer.Option(..., "--filelist", help="Path to filelist (.f/.fl)"),
    project_root: str = typer.Option(
        None, "--project-root", help="要扫描的目录 (默认: filelist 同级 src/)"
    ),
    log_level: str = typer.Option("ERROR", "--log-level", help="Compiler log level"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
    pretty: bool = typer.Option(False, "--pretty", "-p", help="[JSON] Pretty-print"),
    top: int = typer.Option(30, "--top", "-n", help="最多显示 N 个 typedef (默认 30)"),
):
    """[ADD 2026-06-12] 用 syntax tree + pyslang.clog2 解析 typedef 真实位宽

    跟 macro 展开 / filelist 顺序 / elaboration 成功与否都无关 —
    syntax tree 永远在 elaboration 之前可用, pyslang.clog2 给我们 SV 标准求值.

    Examples:
        python run_cli.py fix widths --filelist project.f
        python run_cli.py fix widths --filelist project.f --json --pretty

    典型输出:
      [coherence:49] dcache_way_idx_t
        $clog2(`DCACHE_WAY) where DCACHE_WAY=`USER_DCACHE_WAY=4 → clog2=2
        → typedef 真实位宽 = 2 bits
    """
    fl_path = Path(filelist)
    if not fl_path.exists():
        typer.echo(f"Error: filelist not found: {filelist}", err=True)
        raise typer.Exit(code=1)

    # project_root default: filelist 同级 src/ 或向上找
    if project_root is None:
        fl_dir = fl_path.parent
        candidate = fl_dir / "src"
        if candidate.exists():
            project_root = str(candidate)
        else:
            project_root = str(fl_dir)
    project_root = Path(project_root).resolve()
    if not project_root.exists():
        typer.echo(f"Error: project_root not found: {project_root}", err=True)
        raise typer.Exit(code=1)

    # 读所有 source 给 macro 解析用
    sources: dict[str, str] = {}
    for line in fl_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith(("//", "#", "+", "-")):
            continue
        path = Path(line)
        if path.is_file():
            try:
                sources[line] = path.read_text(encoding="utf-8", errors="replace")
            except Exception:
                pass

    # 跑 UnifiedTracer 拿 syntax trees
    try:
        tracer = _build_tracer(filelist=filelist, strict=False, log_level=log_level)
        _ = tracer.build_graph()
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1) from None

    typedefs = _get_syntax_trees_typedefs(tracer)
    if not typedefs:
        typer.echo("❌ No syntax trees available (compile failed too early)")
        raise typer.Exit(code=1)

    # 走每个 typedef 找 $clog2
    results = []
    for td in typedefs:
        if not hasattr(td, "type") or not td.type:
            continue
        type_str = str(td.type)
        if "$clog2" not in type_str:
            continue
        m = CLOG2_PATTERN.search(type_str)
        if not m:
            continue
        literal, macro_name = m.group(1), m.group(2)
        value_or_macro: int | str = int(literal) if literal else macro_name
        # 算 clog2
        result = _evaluate_clog2(value_or_macro, sources)
        # 拿 source range
        sr = td.sourceRange if hasattr(td, "sourceRange") else None
        loc = ""
        if sr and hasattr(sr.start, "file"):
            f = str(sr.start.file).split("/")[-1]
            line = sr.start.line
            loc = f"{f}:{line}"
        results.append({
            "location": loc,
            "call": m.group(0),
            "value_or_macro": value_or_macro,
            "clog2": result,
            "type_str": type_str.strip()[:100],
        })

    if json_output:
        out = {
            "project_root": str(project_root),
            "filelist": filelist,
            "total_typedefs": len(typedefs),
            "with_clog2": len(results),
            "resolved": sum(1 for r in results if r["clog2"] is not None),
            "results": results[:top],
        }
        indent = 2 if pretty else None
        typer.echo(json.dumps(out, indent=indent, ensure_ascii=False))
        return

    # 文本输出
    typer.echo(f"=== Fix Widths Report ===\n")
    typer.echo(f"Project root: {project_root}")
    typer.echo(f"Total typedefs in syntax trees: {len(typedefs)}")
    typer.echo(f"Typedefs using $clog2: {len(results)}\n")

    if not results:
        typer.echo("✅ No $clog2 usage found in any typedef.")
        return

    resolved_count = sum(1 for r in results if r["clog2"] is not None)
    typer.echo(f"=== Resolved {resolved_count}/{len(results)} typedefs ===\n")
    for r in results[:top]:
        loc = r["location"] or "?"
        call = r["call"]
        if r["clog2"] is not None:
            icon = "🟢"
            width = r["clog2"]
            v = r["value_or_macro"]
            typer.echo(f"{icon} [{loc}] {call}")
            typer.echo(f"    value = {v}  →  clog2 = {width}  →  typedef real width = {width} bits")
        else:
            icon = "🔴"
            typer.echo(f"{icon} [{loc}] {call}  (macro 解析失败)")

    unresolved = [r for r in results if r["clog2"] is None]
    if unresolved:
        typer.echo(f"\n⚠️  {len(unresolved)} typedef(s) 没法解析 (macro 没找到):")
        for r in unresolved[:5]:
            typer.echo(f"    - {r['location']}: {r['call']}")
        if len(unresolved) > 5:
            typer.echo(f"    ... ({len(unresolved) - 5} more)")

    if len(results) > top:
        typer.echo(f"\n... ({len(results) - top} more not shown, use --top to increase)")
