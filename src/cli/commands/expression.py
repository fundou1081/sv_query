# ==============================================================================
# expression.py - expression node subcommands
# ============================================================================
# [Expression Node] CLI commands for building expression nodes

import json
import sys
from pathlib import Path

import typer

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from trace.core.semantic_adapter import SemanticAdapter
from trace.unified_tracer import UnifiedTracer


def output_json(data: dict, pretty: bool = False) -> None:
    indent = 2 if pretty else None
    print(json.dumps(data, indent=indent, ensure_ascii=False))


def output_text(data: dict) -> None:
    """纯文本输出"""
    command = data.get("command", "")
    result = data.get("result", {})

    if command == "build_expression":
        expr_id = result.get("expression_id", "")
        operands = result.get("operands", [])
        expression = result.get("expression", "")
        print("Expression node created:")
        print(f"  ID: {expr_id}")
        print(f"  Expression: {expression}")
        print(f"  Operands: {operands}")

        edges = result.get("edges", [])
        if edges:
            print("  Edges:")
            for edge in edges:
                print(f"    {edge['src']} → {edge['dst']} ({edge['kind']})")

    elif command == "build_function_call":
        func_id = result.get("function_id", "")
        func_name = result.get("function_name", "")
        arguments = result.get("arguments", [])
        print("Function call node created:")
        print(f"  ID: {func_id}")
        print(f"  Function: {func_name}")
        print(f"  Arguments: {arguments}")

    elif command == "build_conditional":
        cond_id = result.get("condition_id", "")
        condition = result.get("condition", "")
        true_branch = result.get("true_branch", "")
        false_branch = result.get("false_branch", "")
        print("Conditional expression node created:")
        print(f"  ID: {cond_id}")
        print(f"  Condition: {condition}")
        print(f"  True: {true_branch}")
        print(f"  False: {false_branch}")


expression_app = typer.Typer(help="Build expression nodes")


@expression_app.command("build")
def build(
    operands: str = typer.Option(..., "--operands", "-o", help="Comma-separated operands (e.g., 'a,b')"),
    expression: str = typer.Option(..., "--expression", "-e", help="Expression string (e.g., 'a + b')"),
    result: str = typer.Option(..., "--result", "-r", help="Result signal name"),
    file: Path = typer.Option(None, "--file", "-f", help="SystemVerilog source file (optional)"),
    module: str = typer.Option("", "--module", "-m", help="Module name"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output JSON format"),
    pretty: bool = typer.Option(False, "--pretty", "-p", help="Pretty-print JSON"),
) -> None:
    """Build an expression node"""
    try:
        operands_list = [op.strip() for op in operands.split(",")]

        # 如果提供了文件，使用 DriverExtractor
        if file:
            # [FIX 2026-07-06] DriverExtractor 没有 build_expression 方法 (dead-code path 早期写但没跑过).
            # 当前 'with --file' 自动从 RTL 提取 operands/expression 没实现.
            # Fallback 到 ExpressionBuilder 无图模式, 把 --file 当 metadata only.
            typer.echo(
                "Warning: --file 当前未使用 (DriverExtractor 没暴露 build_expression). "
                "Operands/expression 必须手动提供. 见 TODO expression.py:15.",
                err=True,
            )

        # [FIX 2026-07-06] 当前所有命令都用 ExpressionBuilder (无图模式)
        from trace.core.builder.expression_builder import ExpressionBuilder
        from trace.core.graph.models import SignalGraph
        graph = SignalGraph()
        builder = ExpressionBuilder(graph)
        if True:  # 之前这里分 if/else, 现合并
            # 无文件模式：直接使用 ExpressionBuilder
            from trace.core.builder.expression_builder import ExpressionBuilder
            from trace.core.graph.models import SignalGraph

            graph = SignalGraph()
            builder = ExpressionBuilder(graph)
            expr_id = builder.build_expression(
                operands=operands_list, expression=expression, result=result, module=module
            )

        # 构建边信息
        edges = []
        for op in operands_list:
            edges.append({"src": op, "dst": expr_id, "kind": "DRIVER"})
        edges.append({"src": expr_id, "dst": result, "kind": "DRIVER"})

        data = {
            "ok": True,
            "command": "build_expression",
            "params": {"operands": operands_list, "expression": expression, "result": result, "module": module},
            "result": {
                "expression_id": expr_id,
                "operands": operands_list,
                "expression": expression,
                "result": result,
                "edges": edges,
            },
            "errors": [],
        }

        if json_output:
            output_json(data, pretty)
        else:
            output_text(data)

    except Exception as e:
        data = {"ok": False, "command": "build_expression", "error": str(e), "errors": [str(e)]}
        if json_output:
            output_json(data)
        else:
            print(f"Error: {e}", file=sys.stderr)
        raise typer.Exit(code=1) from None


@expression_app.command("func")
def function_call(
    function_name: str = typer.Option(..., "--name", "-n", help="Function name"),
    arguments: str = typer.Option(..., "--args", "-a", help="Comma-separated arguments (e.g., 'a,b')"),
    result: str = typer.Option(..., "--result", "-r", help="Result signal name"),
    file: Path = typer.Option(None, "--file", "-f", help="SystemVerilog source file (optional)"),
    module: str = typer.Option("", "--module", "-m", help="Module name"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output JSON format"),
    pretty: bool = typer.Option(False, "--pretty", "-p", help="Pretty-print JSON"),
) -> None:
    """Build a function call node"""
    try:
        args_list = [arg.strip() for arg in arguments.split(",")]

        if file:
            # [FIX 2026-07-06] DriverExtractor 没有 build_function_call 方法. Fallback 到 ExpressionBuilder.
            typer.echo(
                "Warning: --file 当前未使用 (DriverExtractor 没暴露 build_function_call).",
                err=True,
            )

        from trace.core.builder.expression_builder import ExpressionBuilder
        from trace.core.graph.models import SignalGraph
        graph = SignalGraph()
        builder = ExpressionBuilder(graph)
        func_id = builder.build_function_call(
            function_name=function_name, arguments=args_list, result=result, module=module
        )

        data = {
            "ok": True,
            "command": "build_function_call",
            "params": {"function_name": function_name, "arguments": args_list, "result": result},
            "result": {
                "function_id": func_id,
                "function_name": function_name,
                "arguments": args_list,
                "result": result,
            },
            "errors": [],
        }

        if json_output:
            output_json(data, pretty)
        else:
            output_text(data)

    except Exception as e:
        data = {"ok": False, "command": "build_function_call", "error": str(e), "errors": [str(e)]}
        if json_output:
            output_json(data)
        else:
            print(f"Error: {e}", file=sys.stderr)
        raise typer.Exit(code=1) from None


@expression_app.command("cond")
def conditional(
    condition: str = typer.Option(..., "--cond", "-c", help="Condition signal"),
    true_branch: str = typer.Option(..., "--true", "-t", help="True branch signal"),
    false_branch: str = typer.Option(..., "--false", help="False branch signal"),
    result: str = typer.Option(..., "--result", "-r", help="Result signal name"),
    file: Path = typer.Option(None, "--file", "-f", help="SystemVerilog source file (optional)"),
    module: str = typer.Option("", "--module", "-m", help="Module name"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output JSON format"),
    pretty: bool = typer.Option(False, "--pretty", "-p", help="Pretty-print JSON"),
) -> None:
    """Build a conditional expression node (sel ? a : b)"""
    try:
        if file:
            # [FIX 2026-07-06] DriverExtractor 没有 build_conditional 方法. Fallback 到 ExpressionBuilder.
            typer.echo(
                "Warning: --file 当前未使用 (DriverExtractor 没暴露 build_conditional).",
                err=True,
            )

        from trace.core.builder.expression_builder import ExpressionBuilder
        from trace.core.graph.models import SignalGraph
        graph = SignalGraph()
        builder = ExpressionBuilder(graph)
        cond_id = builder.build_conditional(
            condition=condition, true_branch=true_branch, false_branch=false_branch, result=result, module=module
        )

        data = {
            "ok": True,
            "command": "build_conditional",
            "params": {
                "condition": condition,
                "true_branch": true_branch,
                "false_branch": false_branch,
                "result": result,
            },
            "result": {
                "condition_id": cond_id,
                "condition": condition,
                "true_branch": true_branch,
                "false_branch": false_branch,
                "result": result,
            },
            "errors": [],
        }

        if json_output:
            output_json(data, pretty)
        else:
            output_text(data)

    except Exception as e:
        data = {"ok": False, "command": "build_conditional", "error": str(e), "errors": [str(e)]}
        if json_output:
            output_json(data)
        else:
            print(f"Error: {e}", file=sys.stderr)
        raise typer.Exit(code=1) from None
