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


@randomize_app.command(name="trace")
def trace_cmd(
    file: str = typer.Option(None, "--file", "-f", help="SystemVerilog source file"),
    filelist: str = typer.Option(None, "--filelist", help="Path to filelist (.f/.fl) for multi-file projects"),
    cls_filter: str = typer.Option(..., "--class", help="Entry class name (e.g. my_seq)"),
    method: str = typer.Option(..., "--method", help="Entry method name (e.g. body)"),
    strict: bool = typer.Option(True, "--strict/--no-strict", help="Strict mode"),
    json_output: bool = typer.Option(False, "--json", help="JSON output"),
):
    """[Phase 2 Day 3 2026-07-07] 追踪 randomize() 调用图 + 影响的 rand 变量

    从指定 class.method 入口出发, 构建 call graph, 追踪所有 randomize() 调用,
    配对 pre_randomize / post_randomize hooks.

    Examples:
        sv_query randomize trace -f my_pkg.sv --class my_seq --method body
        sv_query randomize trace -f my_pkg.sv --class my_seq --method body --json
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

    sources = tracer.sources

    # Build call graph
    from trace.core.call_graph_builder import CallGraphBuilder
    builder = CallGraphBuilder(sources=sources)
    call_graph = builder.build(entry_class=cls_filter, entry_method=method)

    if call_graph.errors:
        for err in call_graph.errors:
            print(f"WARN: {err}", file=sys.stderr)

    # [Phase 2 Day 3 2026-07-07] 如果 entry 不存在, exit 1
    if call_graph.entry_point and not call_graph.root:
        if json_output:
            print(json.dumps({"error": f"entry {cls_filter}.{method} not found", "randomize_calls": [], "fork_points": []}, indent=2))
        else:
            print(f"ERROR: entry {cls_filter}.{method} not found", file=sys.stderr)
        raise typer.Exit(code=1)

    if json_output:
        import json
        out = {
            "entry": call_graph.entry_point,
            "pattern": call_graph.root.pattern if call_graph.root else "generic",
            "randomize_calls": [
                {
                    "caller": r.caller,
                    "callee": r.callee,
                    "line": r.line,
                    "kind": r.kind,
                    "randomize_vars": r.randomize_vars,
                    "inline_constraint": r.inline_constraint,
                }
                for r in call_graph.randomize_calls
            ],
            "fork_points": [
                {"caller": f.caller, "join_type": f.join_type, "line": f.line}
                for f in call_graph.fork_points
            ],
            "errors": call_graph.errors,
        }
        print(json.dumps(out, indent=2, ensure_ascii=False))
        return

    # Human-readable output
    print("=" * 70)
    print(f"Randomize Trace: {call_graph.entry_point}")
    print("=" * 70)
    print(f"  Pattern: {call_graph.root.pattern if call_graph.root else 'generic'}")

    # 配对 pre_randomize / post_randomize
    # 走 root semantic tree, 找 SubroutineDeclarations (包括 user-defined + auto-derived)
    pre_hooks = []
    post_hooks = []
    root = tracer.compilation.getRoot()
    all_subs = _walk_subroutines(root)
    seen_pre = set()
    seen_post = set()
    for cls_name, name, _, _ in all_subs:
        if name == "pre_randomize" and cls_name not in seen_pre:
            pre_hooks.append(cls_name)
            seen_pre.add(cls_name)
        elif name == "post_randomize" and cls_name not in seen_post:
            post_hooks.append(cls_name)
            seen_post.add(cls_name)

    print(f"  Pre-randomize hooks:  {len(pre_hooks)} ({', '.join(pre_hooks) if pre_hooks else 'none'})")
    print(f"  Post-randomize hooks: {len(post_hooks)} ({', '.join(post_hooks) if post_hooks else 'none'})")

    # Randomize calls
    print(f"\n[1] Randomize() Calls ({len(call_graph.randomize_calls)})")
    print("-" * 70)
    if not call_graph.randomize_calls:
        print("  (no randomize() calls in this call graph)")
    else:
        for i, r in enumerate(call_graph.randomize_calls, 1):
            print(f"\n  [{i}] {r.caller}:{r.line}  {r.callee}")
            if r.randomize_vars:
                print(f"      rand vars: {', '.join(r.randomize_vars)}")
            if r.inline_constraint:
                print(f"      inline constraint:")
                for line_str in r.inline_constraint.split("\n"):
                    print(f"        {line_str}")

    # Fork points
    if call_graph.fork_points:
        print(f"\n[2] Fork Points ({len(call_graph.fork_points)})")
        print("-" * 70)
        for f in call_graph.fork_points:
            print(f"  {f.caller}:{f.line}  fork...{f.join_type}")

    # Errors
    if call_graph.errors:
        print(f"\n[3] Errors ({len(call_graph.errors)})")
        print("-" * 70)
        for err in call_graph.errors:
            print(f"  - {err}")

    print("\n" + "=" * 70)
    print(f"Summary: {len(call_graph.randomize_calls)} randomize calls, "
          f"{len(call_graph.fork_points)} fork points, "
          f"{len(pre_hooks)} pre + {len(post_hooks)} post hooks")
    print("=" * 70)


if __name__ == "__main__":
    typer.run(randomize_app)