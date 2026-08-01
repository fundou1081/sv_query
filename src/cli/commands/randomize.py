# ruff: noqa: B007
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
                for _kind, target, inline_str, line in calls:
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
            for _kind, target, inline_str, line in calls:
                if not inline_str:
                    continue
                count += 1
                print(f"\n  [{count}] {cls_name}.{name}:{line}")
                print(f"      target:        {target}")
                print("      constraint:")
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
            print(json.dumps({"error": f"entry {cls_filter}.{method} not found", "randomize_calls": [], "fork_points": []}, indent=2))  # noqa: F821
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
                print("      inline constraint:")
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


# =============================================================================
# [Phase 3 Day 1 2026-07-07] randomize reachability — dead randomize detection
# =============================================================================

def _scan_references_semantic(tracer, target_signal: str) -> list[dict]:
    """扫描 tracer 所有 class, 找 target_signal 被引用的位置.

    [Phase 3 Day 4 2026-07-07 REWRITE 鉄律1] 完全用 Semantic AST + Visitor 模式
    不用 text grep (避免注释/字符串/substring 误判).

    策略:
      1. 拿 SemanticAdapter (从 tracer)
      2. 拿 SignalExpressionVisitor (pyslang visitor pattern, 鉄律15/26)
      3. Walk 所有 class 的 syntax.items (member declarations)
      4. For each task/function body, walk items
      5. For each ExpressionStatement/AssignmentStatement, 取 .expr 走 adapter._extract_signals_from_expr()
      6. 检查 target_signal in result (semantic signal list)

    Returns list of:
      {"class": str, "kind": "task" | "function" | "assign" | "always",
       "context": str (e.g. "task run()"), "snippet": str (source text excerpt)}
    """
    results = []

    # [鉄律28] 用 visitor pattern, 每个语法类型有对应 handler
    # [V6.9] SignalExpressionVisitor removed — using semantic_adapter._extract_signals_from_expr()
    adapter = tracer._get_adapter()
    # [V6.9] adapter._extract_signals_from_expr() used instead

    root = tracer.compilation.getRoot()

    def extract_referenced_signals(stmt_node) -> list[str]:
        """从 statement node 提取所有 referenced signals (semantic AST, visitor pattern)."""
        # statement 通常有 .expr 属性 (ExpressionStatement) 或其他
        sigs = []
        if hasattr(stmt_node, 'expr') and stmt_node.expr is not None:
            result = adapter._extract_signals_from_expr(stmt_node.expr)
            sigs.extend(result if result else [])
        # 一些 statement 类型没有 .expr (e.g. DataDeclaration, ConstraintDeclaration)
        # 这些被跳过 — 不是 code reference
        return sigs

    def is_declaration_kind(kind: str) -> bool:
        """判断是否是 declaration kind (vs reference kind)."""
        decl_kws = [
            "ClassPropertyDeclaration", "DataDeclaration",
            "ConstraintDeclaration", "ClassMethodDeclaration",
            "CovergroupDeclaration", "NetDeclaration", "ParameterDeclaration",
        ]
        return any(kw in kind for kw in decl_kws)

    def is_reference_kind(kind: str) -> bool:
        """判断是否是 reference 所在的 kind."""
        ref_kws = [
            "Assignment", "ExpressionStatement", "MemberAccess",
            "IdentifierSelect", "ProceduralAssignment", "ContinuousAssign",
            "Conditional", "NamedValue", "ElementSelect",
            "FunctionCall", "TaskCall",
        ]
        return any(kw in kind for kw in ref_kws)

    def walk_class(class_node):
        """[V6.9] Walk class using semantic AST — find SubroutineSymbol tasks/functions
        and extract signal references from their statement bodies."""
        class_name = str(getattr(class_node, "name", "")).strip()

        # Use semantic AST: visit class body to find SubroutineSymbol nodes
        def visit_class_member(node):
            kind = str(getattr(node, "kind", ""))
            if "SubroutineSymbol" in kind or "Subroutine" in kind:
                sub_name = str(getattr(node, "name", "")).strip()
                # Skip built-in routines (randomize, pre_randomize, etc.)
                if sub_name in ("randomize", "pre_randomize", "post_randomize",
                               "get_randstate", "set_randstate", "srandom",
                               "rand_mode", "constraint_mode"):
                    return
                process_subroutine(node, sub_name, class_name)
            elif "StatementKind.ExpressionStatement" in kind:
                # Direct statement in class scope (e.g. initial blocks)
                process_statement(node, class_name, "class_body")

        # Walk the class node's body via visitor or direct items
        if hasattr(class_node, 'items') and hasattr(class_node.items, '__iter__'):
            try:
                for item in class_node.items:
                    visit_class_member(item)
            except TypeError:
                pass

        # Also try via syntax bridge for method bodies
        syntax = getattr(class_node, 'syntax', None)
        if syntax is not None and hasattr(syntax, 'items'):
            try:
                for syn_item in syntax.items:
                    syn_kind = str(getattr(syn_item, "kind", ""))
                    if "ClassMethodDeclaration" in syn_kind:
                        inner = getattr(syn_item, 'declaration', None)
                        if inner is not None:
                            inner_kind = str(getattr(inner, "kind", ""))
                            # Process task/function body statements via syntax tree
                            if ("Task" in inner_kind and "Declaration" in inner_kind) or \
                               ("Function" in inner_kind and "Declaration" in inner_kind):
                                process_task_or_fn_syntax(inner, inner_kind,
                                    str(getattr(inner, "name", "")).strip(), class_name)
            except TypeError:
                pass

    def process_subroutine(sub_node, sub_name: str, class_name: str):
        """Process a SubroutineSymbol from semantic AST."""
        # Walk the subroutine's body statements
        if hasattr(sub_node, 'items') and hasattr(sub_node.items, '__iter__'):
            try:
                for stmt in sub_node.items:
                    process_statement(stmt, class_name, f"task/function {sub_name}()")
            except TypeError:
                pass

    def process_statement(stmt, class_name: str, ctx: str):
        """Extract signals from a statement node."""
        stmt_kind = str(getattr(stmt, "kind", ""))
        # Skip declarations
        decl_kws = ["ClassProperty", "DataDeclaration", "ConstraintDeclaration",
                    "ClassMethod", "Covergroup", "NetDeclaration", "Parameter"]
        if any(kw in stmt_kind for kw in decl_kws):
            return

        sigs = extract_referenced_signals(stmt)
        matched = any(
            target_signal == s or
            s.endswith('.' + target_signal) or
            s == 'this.' + target_signal
            for s in sigs
        )
        if matched:
            try:
                snippet = str(stmt).replace("\n", " ").strip()[:120]
            except Exception:
                snippet = ""
            results.append({
                "class": class_name,
                "kind": _kind_label(stmt_kind),
                "context": ctx,
                "snippet": snippet,
            })

    def process_task_or_fn_syntax(decl, decl_kind, decl_name, class_name):
        """Fallback: process task/function body via syntax tree bridge."""
        ctx_str = f"{('task' if 'Task' in decl_kind else 'function')} {decl_name}()"
        items = getattr(decl, 'items', None)
        if items is None:
            body = getattr(decl, 'body', None)
            if body is not None:
                items = getattr(body, 'items', None) or body
        if items is None:
            return
        try:
            stmts = list(items) if hasattr(items, '__iter__') else []
        except TypeError:
            return
        for stmt in stmts:
            process_statement(stmt, class_name, ctx_str)

    # 走 root 找所有 class — use semantic AST visit() pattern
    def walk_root(node):
        kind = str(getattr(node, "kind", ""))
        if "ClassType" in kind:
            walk_class(node)

    root.visit(walk_root)
    return results


def _kind_label(kind: str) -> str:
    """Map AST kind to human-readable category"""
    if "ConstraintDeclaration" in kind:
        return "constraint"
    if "ContinuousAssign" in kind:
        return "assign"
    if "AlwaysBlock" in kind or "AlwaysFFBlock" in kind or "AlwaysCombBlock" in kind:
        return "always"
    if "TaskDeclaration" in kind:
        return "task"
    if "FunctionDeclaration" in kind:
        return "function"
    if "Coverpoint" in kind:
        return "coverpoint"
    if "CoverCross" in kind:
        return "cross"
    if "Declaration" in kind:
        return "decl"
    return "other"


@randomize_app.command(name="reachability")
def reachability_cmd(
    file: str = typer.Option(None, "--file", "-f", help="SystemVerilog source file"),
    filelist: str = typer.Option(None, "--filelist", help="Path to filelist (.f/.fl) for multi-file projects"),
    cls_filter: str = typer.Option(..., "--class", help="Target class name"),
    strict: bool = typer.Option(True, "--strict/--no-strict", help="Strict mode"),
    json_output: bool = typer.Option(False, "--json", help="JSON output"),
):
    """[Phase 3 Day 1 2026-07-07] 分析 rand 变量 reachability (检测 dead randomize)

    对每个 rand/randc 变量:
      1. 找出被 randomize() 的位置
      2. 追踪它是否在其他地方被读 (assign/always/task body/covergroup/constraint)
      3. 报告 status:
         - alive: 至少被消费一次
         - dead:  从未被消费 (可能 unused 或 design bug)

    Examples:
        sv_query randomize reachability -f packet.sv --class packet
        sv_query randomize reachability -f packet.sv --class my_seq --json
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

    # 找到目标 class
    target_class = None
    for cls_name, cls_node in _find_classes(root):
        if cls_name == cls_filter:
            target_class = cls_node
            break

    if target_class is None:
        if json_output:
            import json as _json
            print(_json.dumps({"error": f"class {cls_filter} not found", "rand_vars": []}, indent=2))
        else:
            print(f"ERROR: class {cls_filter} not found", file=sys.stderr)
        raise typer.Exit(code=1)

    # 拿 rand vars
    rand_vars = _get_rand_variables(target_class)

    # 收集所有 randomize() calls (用 _find_randomize_calls 走所有 task)
    all_subs = _walk_subroutines(root)
    all_calls = []
    for cls_name, name, syntax, _ in all_subs:
        if syntax and name not in ("randomize", "pre_randomize", "post_randomize"):
            calls = _find_randomize_calls(syntax, cls_name, name)
            for kind, target, inline_str, line in calls:
                all_calls.append({
                    "class": cls_name,
                    "method": name,
                    "target": target,
                    "line": line,
                    "kind": kind,
                    "inline_constraint": inline_str,
                })

    # 跨 class 找 covergroup sample (走 CovergroupExtractor)
    from trace.core.covergroup_extractor import CovergroupExtractor
    sources = tracer.sources if hasattr(tracer, "sources") else {}
    extractor = CovergroupExtractor(sources=sources, strict=strict)
    covergroups = extractor.extract()

    # Analyze reachability for each rand var
    rand_info = []
    for vname, vkind in rand_vars:
        # 找包含这个变量的 coverpoint
        covered_in = []
        for cg in covergroups:
            for cp in cg.coverpoints:
                if vname == cp.signal:
                    covered_in.append({
                        "covergroup": cg.name,
                        "coverpoint": cp.name or cp.signal,
                        "in_class": cg.in_class,
                    })

        # 在所有 randomize() calls 里找这个 var
        # (看 inline constraint 跟 target receiver name)
        randomized_in = []
        for call in all_calls:
            # target 是 `req` 不是 `addr`, 但 randomize() 是 for receiver 整个 object
            # 所以只要 target receiver 是 rand var 所属 class 的 instance, 这个 var 被随机化
            # 简化: 如果 call.target 是某个 class 名 + 这个 var 是那 class 的 rand var
            # 那这个 var 被 randomize
            if call["kind"] == "randomize_with_constraint":
                # inline constraint 里有这个 var → 明确 randomized
                if vname in call["inline_constraint"]:
                    randomized_in.append(call)
            else:
                # bare randomize() — 假设所有 rand vars 都随机化
                randomized_in.append(call)

        # 找 references (excluding declaration, 跨 class 扫描) - [Phase 3 Day 4] semantic version
        refs = _scan_references_semantic(tracer, vname)

        # 过滤掉 declaration 本身
        consumer_refs = [r for r in refs if r["kind"] != "decl"]

        status = "alive" if (consumer_refs or covered_in) else "dead"

        rand_info.append({
            "name": vname,
            "kind": vkind,
            "status": status,
            "randomized_count": len(randomized_in),
            "covered_count": len(covered_in),
            "consumed_count": len(consumer_refs),
            "consumers": consumer_refs,
            "covered_in": covered_in,
            "randomized_in": randomized_in[:5],  # cap
        })

    if json_output:
        import json as _json
        out = {
            "class": cls_filter,
            "total_rand_vars": len(rand_info),
            "alive_count": sum(1 for r in rand_info if r["status"] == "alive"),
            "dead_count": sum(1 for r in rand_info if r["status"] == "dead"),
            "rand_vars": rand_info,
        }
        print(_json.dumps(out, indent=2, ensure_ascii=False))
        return

    # Human-readable output
    print("=" * 70)
    print(f"Randomize Reachability: {cls_filter}")
    print("=" * 70)

    alive = sum(1 for r in rand_info if r["status"] == "alive")
    dead = sum(1 for r in rand_info if r["status"] == "dead")
    print(f"  Total rand vars: {len(rand_info)} (alive: {alive}, dead: {dead})")

    for info in rand_info:
        status_marker = "🟢 ALIVE" if info["status"] == "alive" else "🔴 DEAD"
        print(f"\n  [{status_marker}] {info['kind']} {info['name']}")
        print(f"    randomized:    {info['randomized_count']} call(s)")
        if info['randomized_in']:
            for c in info['randomized_in']:
                constraint_str = f" with {c['inline_constraint']}" if c['inline_constraint'] else ""
                print(f"      - {c['class']}.{c['method']}:{c['line']} {c['target']}.randomize(){constraint_str}")

        print(f"    consumed:      {info['consumed_count']} location(s)")
        if info['consumers']:
            for r in info['consumers'][:5]:
                print(f"      - {r['kind']:12s} in {r['context']}: {r['snippet'][:60]}")

        print(f"    covered:       {info['covered_count']} covergroup(s)")
        if info['covered_in']:
            for c in info['covered_in']:
                print(f"      - {c['covergroup']}.{c['coverpoint']} (in class {c['in_class']})")

    print("\n" + "=" * 70)
    if dead > 0:
        print(f"⚠️  {dead} dead randomize(s) detected (never consumed)")
    else:
        print("✅ All rand vars are consumed")
    print("=" * 70)


if __name__ == "__main__":
    typer.run(randomize_app)
