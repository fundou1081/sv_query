# -*- coding: utf-8 -*-
"""
randomize.py - Randomize 分析 CLI 命令

[Phase 1 Day 1-2 2026-07-07] 新增 randomize 命令组

提供:
- list: 列出 SV source 里所有 rand/randc 变量 + randomize() 调用点 + pre/post_randomize 函数
- extract: 列出 randomize() 的 inline constraint 表达式

用法:
    sv_query randomize list -f packet.sv
    sv_query randomize extract -f packet.sv --class my_seq
"""
from __future__ import annotations

import sys
from pathlib import Path

_current_file = Path(__file__).resolve()
_src_dir = _current_file.parent
_project_root = _src_dir.parent.parent

if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import warnings

import typer
from cli._common import _build_tracer, handle_compilation_error
from trace.core.compiler import CompilationError

warnings.filterwarnings("ignore")

randomize_app = typer.Typer(
    help="[Phase 1 2026-07-07] Randomize 分析: list 变量 + 提取 inline constraint"
)


# =============================================================================
# Helpers
# =============================================================================

def _walk_subroutines(root):
    """Walk root tree, return list of (class_name, name, syntax)."""
    results = []

    def walk(node, class_name=""):
        kind = str(getattr(node, "kind", ""))
        if "ClassType" in kind:
            class_name = str(getattr(node, "name", "")).strip()
            # Also recursively process members
            try:
                for child in node:
                    walk(child, class_name)
            except TypeError:
                pass
            return
        if "Subroutine" in kind:
            name = str(getattr(node, "name", "")).strip()
            if name:
                syntax = getattr(node, "syntax", None)
                results.append((class_name, name, syntax, node))
            return
        try:
            for child in node:
                walk(child, class_name)
        except TypeError:
            pass

    walk(root)
    return results


def _find_classes(root):
    """Find all class nodes (semantic AST)."""
    classes = []

    def walk(node):
        kind = str(getattr(node, "kind", ""))
        if "ClassType" in kind:
            cls_name = str(getattr(node, "name", "")).strip()
            if cls_name:
                classes.append((cls_name, node))
            return
        if "Token" in kind:
            return
        try:
            for child in node:
                walk(child)
        except TypeError:
            pass

    walk(root)
    return classes


def _get_rand_variables(class_node):
    """Get list of (name, kind) from a ClassType's properties.

    kind: 'rand' | 'randc' | 'none'
    """
    results = []
    props = getattr(class_node, "properties", None) or []
    for p in props:
        pname = str(getattr(p, "name", "")).strip()
        rand_mode = getattr(p, "randMode", None)
        kind = "none"
        # RandMode is an enum: RandMode.None_ / RandMode.Rand / RandMode.RandC
        # str() returns "RandMode.Rand" / "RandMode.RandC" / "RandMode.None_"
        if rand_mode is not None:
            rand_str = str(rand_mode)
            if rand_str == "RandMode.RandC":
                kind = "randc"
            elif rand_str == "RandMode.Rand":
                kind = "rand"
        if kind in ("rand", "randc"):
            results.append((pname, kind))
    return results


def _find_randomize_calls(task_syntax, class_name, task_name):
    """Find all randomize() calls in a task/function syntax tree.

    Returns list of (kind, target, inline_constraint_str, line).
    kind: 'randomize_no_with' | 'randomize_with_constraint'
    target: e.g. 'req' (the receiver)
    inline_constraint_str: constraint expression text, or ''
    line: source line number
    """
    results = []

    def get_line(node):
        sr = getattr(node, "sourceRange", None)
        if sr:
            try:
                return sr.start.line
            except Exception:
                pass
        return 0

    def get_text(node):
        # 尝试 str(node) 拿 constraint text
        try:
            s = str(node).strip()
            return s if s else ""
        except Exception:
            return ""

    def get_target_name(node):
        # node.method 可能是 InvocationExpressionSyntax, 拿 method 字段前面的 receiver
        # 也可能直接是 .randomize() 调用
        method = getattr(node, "method", None)
        if method:
            # method is InvocationExpressionSyntax
            # receiver 通常在 method 里 — 简化: 看 method.sourceText 前面
            text = get_text(method)
            if "." in text:
                return text.split(".")[0].strip()
        return ""

    def walk_expr(node):
        kind = str(getattr(node, "kind", ""))
        if "ArrayOrRandomizeMethodExpression" in kind:
            target = get_target_name(node)
            constraints = getattr(node, "constraints", None)
            inline_str = get_text(constraints) if constraints else ""
            line = get_line(node)
            if inline_str:
                results.append(("randomize_with_constraint", target, inline_str, line))
            else:
                results.append(("randomize_no_with", target, "", line))
            # 不递归 — 整个 expr 已经是 unit
            return
        # 递归子节点
        if "Token" in kind:
            return
        try:
            for child in node:
                walk_expr(child)
        except TypeError:
            pass

    # 走 task syntax.items 找 ExpressionStatement
    items = getattr(task_syntax, "items", [])
    for stmt in items:
        if hasattr(stmt, "expr"):
            walk_expr(stmt.expr)

    return results


# =============================================================================
# Commands
# =============================================================================

@randomize_app.command(name="list")
def list_cmd(
    file: str = typer.Option(None, "--file", "-f", help="SystemVerilog source file"),
    filelist: str = typer.Option(None, "--filelist", help="Path to filelist (.f/.fl) for multi-file projects"),
    cls_filter: str = typer.Option(None, "--class", help="Filter to specific class"),
    strict: bool = typer.Option(True, "--strict/--no-strict", help="Strict mode"),
    json_output: bool = typer.Option(False, "--json", help="JSON output"),
):
    """[Phase 1 2026-07-07] 列出 rand/randc 变量 + randomize() 调用点 + pre/post_randomize 函数

    Examples:
        sv_query randomize list -f packet.sv
        sv_query randomize list -f packet.sv --class my_seq
        sv_query randomize list --filelist project.f --json
    """
    try:
        tracer = _build_tracer(
            file=Path(file) if file else None,
            filelist=filelist,
            strict=strict,
        )
    except CompilationError as e:
        handle_compilation_error(e, strict=strict)
        raise typer.Exit(code=1) from e

    if not tracer.compilation:
        print("ERROR: Compilation failed", file=sys.stderr)
        raise typer.Exit(code=1)

    # 拿 semantic root
    try:
        root = tracer.compilation.getRoot()
    except Exception as e:
        print(f"ERROR: cannot get root: {e}", file=sys.stderr)
        raise typer.Exit(code=1) from e

    # 收集所有 class
    classes = _find_classes(root)
    if cls_filter:
        classes = [(n, c) for n, c in classes if n == cls_filter]

    # 收集所有 subroutine (task/function)
    all_subs = _walk_subroutines(root)
    if cls_filter:
        all_subs = [(cn, n, s, node) for cn, n, s, node in all_subs if cn == cls_filter]

    if json_output:
        import json
        out = {
            "rand_variables": [],
            "randomize_calls": [],
            "pre_randomize": [],
            "post_randomize": [],
        }
        for cls_name, cls_node in classes:
            for vname, vkind in _get_rand_variables(cls_node):
                out["rand_variables"].append({
                    "class": cls_name,
                    "name": vname,
                    "kind": vkind,
                })
        for cls_name, name, syntax, _ in all_subs:
            if name == "pre_randomize":
                out["pre_randomize"].append({"class": cls_name, "name": name})
            elif name == "post_randomize":
                out["post_randomize"].append({"class": cls_name, "name": name})
            elif name == "randomize":
                # user-defined override of randomize() (rare)
                out["randomize_calls"].append({
                    "class": cls_name,
                    "method": name,
                    "kind": "user_defined_override",
                    "target": "",
                    "inline_constraint": "",
                    "line": 0,
                })
        # 加 task body 里的 randomize() 调用
        for cls_name, name, syntax, _ in all_subs:
            if syntax and name not in ("randomize", "pre_randomize", "post_randomize"):
                calls = _find_randomize_calls(syntax, cls_name, name)
                for kind, target, inline_str, line in calls:
                    out["randomize_calls"].append({
                        "class": cls_name,
                        "method": name,
                        "kind": kind,
                        "target": target,
                        "inline_constraint": inline_str,
                        "line": line,
                    })
        print(json.dumps(out, indent=2, ensure_ascii=False))
        return

    # Human-readable output
    print("=" * 70)
    print("Randomize Analysis Report")
    print("=" * 70)

    # Section 1: rand variables
    print("\n[1] Rand Variables")
    print("-" * 70)
    rand_count = 0
    for cls_name, cls_node in classes:
        rand_vars = _get_rand_variables(cls_node)
        if rand_vars:
            print(f"\n  class {cls_name}:")
            for vname, vkind in rand_vars:
                print(f"    {vkind:8s} {vname}")
                rand_count += 1
    if rand_count == 0:
        print("  (none found)")

    # Section 2: pre/post_randomize functions
    print("\n[2] Pre/Post Randomize Hooks")
    print("-" * 70)
    hook_count = 0
    for cls_name, name, _, _ in all_subs:
        if name == "pre_randomize":
            print(f"  pre_randomize()  →  {cls_name}")
            hook_count += 1
        elif name == "post_randomize":
            print(f"  post_randomize() →  {cls_name}")
            hook_count += 1
    if hook_count == 0:
        print("  (no user-defined pre_randomize / post_randomize)")

    # Section 3: randomize() calls in task/function bodies
    print("\n[3] Randomize() Calls")
    print("-" * 70)
    call_count = 0
    for cls_name, name, syntax, _ in all_subs:
        if syntax and name not in ("randomize", "pre_randomize", "post_randomize"):
            calls = _find_randomize_calls(syntax, cls_name, name)
            for kind, target, inline_str, line in calls:
                if kind == "randomize_with_constraint":
                    print(f"  {cls_name}.{name}:{line}  {target}.randomize() with {inline_str}")
                else:
                    print(f"  {cls_name}.{name}:{line}  {target}.randomize()")
                call_count += 1
    if call_count == 0:
        print("  (no randomize() calls in task/function bodies)")

    # Summary
    print("\n" + "=" * 70)
    print(f"Summary: {rand_count} rand vars, {hook_count} hooks, {call_count} calls")
    print("=" * 70)


@randomize_app.command(name="extract")
def extract_cmd(
    file: str = typer.Option(None, "--file", "-f", help="SystemVerilog source file"),
    filelist: str = typer.Option(None, "--filelist", help="Path to filelist (.f/.fl) for multi-file projects"),
    cls_filter: str = typer.Option(None, "--class", help="Filter to specific class"),
    strict: bool = typer.Option(True, "--strict/--no-strict", help="Strict mode"),
    json_output: bool = typer.Option(False, "--json", help="JSON output"),
):
    """[Phase 1 2026-07-07] 提取 randomize() 的 inline constraint 表达式 + 影响的 rand 变量

    Examples:
        sv_query randomize extract -f packet.sv
        sv_query randomize extract -f packet.sv --class my_seq
    """
    try:
        tracer = _build_tracer(
            file=Path(file) if file else None,
            filelist=filelist,
            strict=strict,
        )
    except CompilationError as e:
        handle_compilation_error(e, strict=strict)
        raise typer.Exit(code=1) from e

    if not tracer.compilation:
        print("ERROR: Compilation failed", file=sys.stderr)
        raise typer.Exit(code=1)

    try:
        root = tracer.compilation.getRoot()
    except Exception as e:
        print(f"ERROR: cannot get root: {e}", file=sys.stderr)
        raise typer.Exit(code=1) from e

    classes = _find_classes(root)
    if cls_filter:
        classes = [(n, c) for n, c in classes if n == cls_filter]

    all_subs = _walk_subroutines(root)
    if cls_filter:
        all_subs = [(cn, n, s, node) for cn, n, s, node in all_subs if cn == cls_filter]

    if json_output:
        import json
        out = []
        for cls_name, name, syntax, _ in all_subs:
            if syntax and name not in ("randomize", "pre_randomize", "post_randomize"):
                calls = _find_randomize_calls(syntax, cls_name, name)
                for kind, target, inline_str, line in calls:
                    out.append({
                        "class": cls_name,
                        "method": name,
                        "target": target,
                        "line": line,
                        "has_inline_constraint": bool(inline_str),
                        "inline_constraint": inline_str,
                    })
        print(json.dumps(out, indent=2, ensure_ascii=False))
        return

    print("=" * 70)
    print("Randomize Inline Constraint Extraction")
    print("=" * 70)

    count = 0
    for cls_name, name, syntax, _ in all_subs:
        if syntax and name not in ("randomize", "pre_randomize", "post_randomize"):
            calls = _find_randomize_calls(syntax, cls_name, name)
            for kind, target, inline_str, line in calls:
                if not inline_str:
                    continue
                count += 1
                print(f"\n  [{count}] {cls_name}.{name}:{line}")
                print(f"      target:        {target}")
                print(f"      constraint:")
                for line_str in inline_str.split("\n"):
                    print(f"        {line_str}")

    if count == 0:
        print("\n  (no randomize() with inline constraint found)")

    print("\n" + "=" * 70)
    print(f"Total: {count} inline constraint(s)")
    print("=" * 70)


if __name__ == "__main__":
    typer.run(randomize_app)