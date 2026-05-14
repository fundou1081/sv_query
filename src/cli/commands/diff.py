#==============================================================================
# diff.py - graph diff command
#============================================================================

import sys
import json
from pathlib import Path

import typer
import pyslang

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from trace.unified_tracer import UnifiedTracer
from trace.core.graph.diff import diff_graph, diff_reachability, diff_with_health

diff_app = typer.Typer(help="Compare two versions of SystemVerilog code")


def output_json(data: dict, pretty: bool = False) -> None:
    indent = 2 if pretty else None
    print(json.dumps(data, indent=indent, ensure_ascii=False))


def output_text(data: dict) -> None:
    """纯文本输出"""
    result = data.get("result", {})

    # Check if we have full health analysis or just basic diff
    graph_diff = result.get("graph_diff", {})
    stable_core = result.get("stable_core", [])
    health_old = result.get("health_score_old")
    health_new = result.get("health_score_new")
    health_delta = result.get("health_delta")
    coupling = result.get("coupling_warning", {})
    reach_diff = result.get("reachability_diff", {})

    # === Graph Diff ===
    print("=== Graph Diff ===")
    added = graph_diff.get("added_nodes", [])
    removed = graph_diff.get("removed_nodes", [])
    added_edges = graph_diff.get("added_edges", [])
    removed_edges = graph_diff.get("removed_edges", [])

    if graph_diff.get("identical"):
        print("  Graphs are identical")
    else:
        if added:
            print(f"  Added nodes ({len(added)}): {', '.join(added[:5])}{'...' if len(added) > 5 else ''}")
        if removed:
            print(f"  Removed nodes ({len(removed)}): {', '.join(removed[:5])}{'...' if len(removed) > 5 else ''}")
        if added_edges:
            print(f"  Added edges ({len(added_edges)})")
        if removed_edges:
            print(f"  Removed edges ({len(removed_edges)})")

    # === Health Score (if available) ===
    if health_old is not None and health_new is not None:
        print("\n=== Architecture Health ===")
        print(f"  Old graph health: {health_old:.2%}")
        print(f"  New graph health: {health_new:.2%}")
        delta_str = f"{health_delta:+.2%}" if health_delta else "N/A"
        print(f"  Health delta: {delta_str}")

        if stable_core:
            print(f"  Stable core ({len(stable_core)} nodes): {', '.join(stable_core[:5])}{'...' if len(stable_core) > 5 else ''}")

        if coupling:
            level = coupling.get('level', 'unknown')
            if level == 'critical':
                print(f"  Coupling warning: *** CRITICAL *** (small change, high instability)")
            elif level == 'high':
                print(f"  Coupling warning: ** HIGH ** (small change, elevated instability)")
            elif level == 'medium':
                print(f"  Coupling warning: * MEDIUM *")
            else:
                print(f"  Coupling level: {level.upper()}")

    # === Reachability Diff ===
    if reach_diff.get("changed_nodes"):
        print("\n=== Reachability Diff ===")
        newly = reach_diff.get("newly_impacted", [])
        no_longer = reach_diff.get("no_longer_impacted", [])
        if newly:
            print(f"  Newly impacted: {', '.join(newly[:5])}{'...' if len(newly) > 5 else ''}")
        if no_longer:
            print(f"  No longer impacted: {', '.join(no_longer[:5])}{'...' if len(no_longer) > 5 else ''}")


@diff_app.command()
def compare(
    old: Path = typer.Argument(..., help="Old version SystemVerilog file"),
    new: Path = typer.Argument(..., help="New version SystemVerilog file"),
    signal: str = typer.Option(None, "--signal", "-s", help="Signal to analyze reachability diff"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output JSON format"),
    pretty: bool = typer.Option(False, "--pretty", "-p", help="Pretty-print JSON"),
) -> None:
    """Compare two versions of SystemVerilog code"""
    try:
        tree_old = pyslang.SyntaxTree.fromFile(str(old))
        tree_new = pyslang.SyntaxTree.fromFile(str(new))

        tracer_old = UnifiedTracer(trees={str(old): tree_old})
        tracer_new = UnifiedTracer(trees={str(new): tree_new})

        graph_old = tracer_old.build_graph()
        graph_new = tracer_new.build_graph()

        # Phase 1: Full health analysis (方案一 + 方案四)
        full_result = diff_with_health(graph_old, graph_new)

        # Extract graph diff for compatibility
        diff_result = full_result['graph_diff']
        result_data = {
            "added_nodes": diff_result.added_nodes,
            "removed_nodes": diff_result.removed_nodes,
            "added_edges": [list(e) for e in diff_result.added_edges],
            "removed_edges": [list(e) for e in diff_result.removed_edges],
            "modified_nodes": diff_result.modified_nodes,
            "identical": diff_result.identical,
        }

        reach_diff_data = {}
        if signal and not diff_result.identical:
            changed_nodes = diff_result.added_nodes + diff_result.removed_nodes + list(diff_result.modified_nodes.keys())
            reach_diff_data = diff_reachability(changed_nodes, graph_old, graph_new)

        data = {
            "ok": True,
            "command": "diff_compare",
            "params": {"old": str(old), "new": str(new), "signal": signal},
            "result": {
                "graph_diff": result_data,
                "stable_core": full_result['stable_core'],
                "health_score_old": full_result['health_score_old'],
                "health_score_new": full_result['health_score_new'],
                "health_delta": full_result['health_delta'],
                "coupling_warning": full_result['coupling_warning'],
                "reachability_diff": reach_diff_data,
            },
            "errors": []
        }

        if json_output:
            output_json(data, pretty)
        else:
            output_text(data)

    except Exception as e:
        data = {
            "ok": False,
            "command": "diff_compare",
            "error": str(e),
            "errors": [str(e)]
        }
        if json_output:
            output_json(data)
        else:
            print(f"Error: {e}", file=sys.stderr)
        raise typer.Exit(code=1)