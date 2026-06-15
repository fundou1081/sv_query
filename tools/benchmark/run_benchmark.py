#!/usr/bin/env python3
"""
[PR5 2026-06-15] sv_query 端到端 benchmark — 跑 4 维能力在真实项目上.

用法:
  python tools/benchmark/run_benchmark.py --filelist /tmp/pulp_axi_xbar_pr2.f --target axi_xbar_dp_ram --depth 4 --output /tmp/benchmark.json
  python tools/benchmark/run_benchmark.py --filelist /tmp/pulp_axi_xbar_pr2.f --target axi_demux_intf --depth 2 --runs 5 --output /tmp/bench_dmux.json

收集:
- L1: extract_module (AST) → instance count
- L2: build_graph → node/edge/IM count
- L3: trace_fanin/fanout on key signals → result count
- L4: extract_module_edges_from_mig → cross-instance port edges
- Flakiness: 5 runs of build_graph, measure variance

输出:
- JSON 报告: /tmp/benchmark.json (machine-readable)
- (可选) Markdown 报告: --markdown 标志
"""
import argparse
import json
import os
import statistics
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# Force ERROR level for lib output
os.environ.setdefault("SV_QUERY_LOG_LEVEL", "ERROR")

# Setup path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from trace.unified_tracer import UnifiedTracer  # noqa: E402
from trace.core.graph.models import NodeKind  # noqa: E402
from trace.core.module_extractor import (  # noqa: E402
    extract_module,
    extract_module_edges_from_mig,
)
from trace.core.semantic_adapter import SemanticAdapter  # noqa: E402
from trace.core.query.signal import SignalTracer  # noqa: E402


# ---------------------------------------------------------------------------
# Helper: 内存回收
# ---------------------------------------------------------------------------

def reclaim_memory() -> None:
    """[PR1 2026-06-15] 用户提出的方法: 强制回收 macOS inactive pages."""
    try:
        a = bytearray(4 * 1024**3)  # 4GB
        time.sleep(3)
        del a
    except Exception:
        pass


# ---------------------------------------------------------------------------
# 数据收集
# ---------------------------------------------------------------------------

def collect_l1(tracer, target: str, depth: int) -> dict:
    """L1: module-level 实例抽取 (AST)."""
    try:
        sa = SemanticAdapter(tracer._get_compiler().get_root())
        result = extract_module(sa, target, max_depth=depth)
        return {
            "target": target,
            "depth": depth,
            "instance_count": len(result.instances),
            "instances": [
                {"id": i.id, "name": i.name, "def": i.def_name, "depth": i.depth}
                for i in result.instances
            ],
        }
    except Exception as e:
        return {"error": f"L1 failed: {e}"}


def collect_l2(tracer) -> dict:
    """L2: graph node/edge/IM count."""
    g = tracer._graph
    n_nodes = g.number_of_nodes()
    n_edges = g.number_of_edges()
    n_im = sum(
        1 for nid in g.nodes()
        if (n := g.get_node(nid)) and n.kind == NodeKind.INSTANTIATED_MODULE
    )
    n_port_in = sum(
        1 for nid in g.nodes()
        if (n := g.get_node(nid)) and n.kind == NodeKind.PORT_IN
    )
    n_port_out = sum(
        1 for nid in g.nodes()
        if (n := g.get_node(nid)) and n.kind == NodeKind.PORT_OUT
    )
    n_signal = sum(
        1 for nid in g.nodes()
        if (n := g.get_node(nid)) and n.kind == NodeKind.SIGNAL
    )

    # Depth distribution
    from collections import Counter
    depth_dist = Counter(nid.count(".") for nid in g.nodes())

    return {
        "nodes": n_nodes,
        "edges": n_edges,
        "instantiated_modules": n_im,
        "port_in": n_port_in,
        "port_out": n_port_out,
        "signal": n_signal,
        "depth_distribution": dict(sorted(depth_dist.items())),
    }


def collect_l3(tracer, signals: list[str]) -> dict:
    """L3: trace_fanin/fanout on key signals."""
    st = tracer._signal_tracer
    if st is None:
        # Create manually if not auto-init
        st = SignalTracer(tracer._graph, mig=tracer._module_graph)

    results = {}
    for sig in signals:
        try:
            fanout = st._collect_all_loads(sig, max_depth=3)
            fanin = st._collect_all_drivers(sig, max_depth=3)
            results[sig] = {
                "fanout": len(fanout),
                "fanin": len(fanin),
                "fanout_samples": [l.id for l in fanout[:3]],
                "fanin_samples": [d.id for d in fanin[:3]],
            }
        except Exception as e:
            results[sig] = {"error": str(e)}

    return results


def collect_l4(tracer, target: str, depth: int) -> dict:
    """L4: cross-instance port edges from MIG."""
    try:
        sa = SemanticAdapter(tracer._get_compiler().get_root())
        l1_result = extract_module(sa, target, max_depth=depth)
        mig = getattr(tracer, "_module_graph", None)
        if mig is None:
            return {"error": "no MIG available"}

        edges = extract_module_edges_from_mig(mig, l1_result.instances, max_edges=2000)

        # Group by port
        from collections import Counter
        port_counts = Counter(e["port_src"] for e in edges)

        return {
            "target": target,
            "depth": depth,
            "edge_count": len(edges),
            "in_scope_count": sum(
                1 for e in edges
                if e["src"] in {i.id for i in l1_result.instances}
                and e["dst"] in {i.id for i in l1_result.instances}
            ),
            "top_ports": dict(port_counts.most_common(10)),
        }
    except Exception as e:
        return {"error": f"L4 failed: {e}"}


def measure_flakiness(
    filelist: str = None, files: list = None, include_dirs: list = None, strict: bool = True, runs: int = 5
) -> dict:
    """[PR5+PR7] 跑 N 次 build_graph, 算总节点数变异."""
    counts = []
    im_counts = []
    # PR7: 生成 tracer init 代码 (filelist 或 files 二选一)
    if filelist:
        init_code = f"t = UnifiedTracer(filelist='{filelist}',"
    else:
        files_repr = repr(files)
        init_code = f"t = UnifiedTracer(files={files_repr},"
    for i in range(runs):
        # Each run is a fresh process to avoid heap accumulation
        result = subprocess.run(
            [
                sys.executable, "-c",
                f"""
import sys, os
sys.path.insert(0, '{PROJECT_ROOT}/src')
os.environ['SV_QUERY_LOG_LEVEL'] = 'ERROR'
from trace.unified_tracer import UnifiedTracer
from trace.core.graph.models import NodeKind
{init_code}
    include_dirs={include_dirs!r},
    strict={strict},
    log_level='ERROR',
)
g = t.build_graph()
n_im = sum(1 for nid in g.nodes() if (n := g.get_node(nid)) and n.kind == NodeKind.INSTANTIATED_MODULE)
print(g.number_of_nodes(), n_im)
""",
            ],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode == 0 and result.stdout.strip():
            parts = result.stdout.strip().split()
            if len(parts) == 2:
                counts.append(int(parts[0]))
                im_counts.append(int(parts[1]))

    if not counts:
        return {"error": "no successful runs"}

    return {
        "runs": runs,
        "node_counts": counts,
        "im_counts": im_counts,
        "node_min": min(counts),
        "node_max": max(counts),
        "node_stdev": statistics.stdev(counts) if len(counts) > 1 else 0,
        "im_min": min(im_counts),
        "im_max": max(im_counts),
        "im_stdev": statistics.stdev(im_counts) if len(im_counts) > 1 else 0,
        "deterministic_ratio_im": (
            sum(1 for c in im_counts if c == im_counts[0]) / len(im_counts)
        ),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="[PR5 2026-06-15] sv_query 端到端 benchmark — 4 维能力 (L1/L2/L3/L4) 在真实项目上."
    )
    # [PR7 2026-06-15] --files 跟 --filelist 二选一 (单文件 vs 复杂项目)
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--filelist", help="Path to filelist (.f) for multi-file projects")
    input_group.add_argument("--files", nargs="+", help="[PR7] Single file or list of files (simple projects)")
    parser.add_argument("--target", required=True, help="Top-level module name")
    parser.add_argument("--depth", type=int, default=4, help="Max instance depth")
    parser.add_argument("--include", "-I", help="Comma-separated include dirs")
    parser.add_argument(
        "--traces",
        nargs="+",
        default=None,
        help="Signals to trace (L3). Default: try common AXI signals.",
    )
    parser.add_argument("--runs", type=int, default=5, help="Flakiness measurement runs")
    parser.add_argument("--output", "-o", default="/tmp/benchmark.json", help="JSON output path")
    parser.add_argument("--markdown", action="store_true", help="Also output Markdown report")
    parser.add_argument("--skip-flakiness", action="store_true", help="Skip flakiness measurement")
    parser.add_argument("--strict", action="store_true", default=True, help="Strict mode (default ON)")
    args = parser.parse_args()

    print(f"=== [PR5] sv_query benchmark ===")
    print(f"Filelist: {args.filelist}")
    print(f"Target: {args.target}")
    print(f"Depth: {args.depth}")
    print()

    # Reclaim memory first (user-proven method, 4GB allocation)
    print("Reclaiming memory (4GB allocation trick)...")
    reclaim_memory()

    # Build tracer
    include_dirs = args.include.split(",") if args.include else None
    print("Building tracer...")
    t0 = time.time()
    if args.filelist:
        t = UnifiedTracer(
            filelist=args.filelist,
            include_dirs=include_dirs,
            strict=args.strict,
            log_level="ERROR",
        )
        project_input = args.filelist
    else:  # args.files (PR7)
        t = UnifiedTracer(
            files=args.files,
            include_dirs=include_dirs,
            strict=args.strict,
            log_level="ERROR",
        )
        project_input = " ".join(args.files)
    t.build_graph()
    build_time = time.time() - t0
    print(f"  Build time: {build_time:.2f}s")

    # Collect data
    print("\n[L1] module-level extraction (AST)...")
    l1 = collect_l1(t, args.target, args.depth)
    print(f"  Instances at depth={args.depth}: {l1.get('instance_count', 'ERR')}")

    print("\n[L2] graph topology...")
    l2 = collect_l2(t)
    print(f"  Nodes: {l2.get('nodes')}, Edges: {l2.get('edges')}, IM: {l2.get('instantiated_modules')}")

    print("\n[L3] trace fanin/fanout...")
    # Default AXI signals to try
    default_traces = [
        f"{args.target}.s_axi_awvalid",
        f"{args.target}.m_axi_awvalid",
        f"{args.target}.s_axi_awready",
        f"{args.target}.m_axi_awready",
        f"{args.target}.clk_i",
    ]
    traces = args.traces or default_traces
    l3 = collect_l3(t, traces)
    for sig, res in l3.items():
        if "error" in res:
            print(f"  {sig}: ERROR {res['error']}")
        else:
            print(f"  {sig}: fanin={res['fanin']} fanout={res['fanout']}")

    print("\n[L4] cross-instance port edges (MIG)...")
    l4 = collect_l4(t, args.target, args.depth)
    print(f"  Edges: {l4.get('edge_count', 'ERR')}, in_scope: {l4.get('in_scope_count', 'ERR')}")

    # Flakiness
    flakiness = None
    if not args.skip_flakiness:
        print(f"\n[Flakiness] {args.runs} independent runs...")
        flakiness = measure_flakiness(
            filelist=args.filelist,
            files=args.files,
            include_dirs=include_dirs or [],
            strict=args.strict,
            runs=args.runs,
        )
        if "error" not in flakiness:
            print(f"  Node range: {flakiness['node_min']}-{flakiness['node_max']} (stdev={flakiness['node_stdev']:.1f})")
            print(f"  IM range: {flakiness['im_min']}-{flakiness['im_max']}")
            print(f"  IM deterministic: {flakiness['deterministic_ratio_im']*100:.0f}%")

    # Output JSON
    report = {
        "metadata": {
            "tool": "sv_query benchmark",
            "version": "PR5+PR7 2026-06-15",
            "input_type": "filelist" if args.filelist else "files",
            "project_input": project_input,
            "filelist": args.filelist,  # deprecated alias for project_input
            "target": args.target,
            "depth": args.depth,
            "include_dirs": include_dirs,
            "timestamp": datetime.now().isoformat(),
            "build_time_seconds": round(build_time, 2),
        },
        "L1_module_extraction": l1,
        "L2_graph_topology": l2,
        "L3_signal_traces": l3,
        "L4_cross_instance_edges": l4,
        "flakiness": flakiness,
    }

    with open(args.output, "w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False, default=str)
    print(f"\n✅ Wrote JSON: {args.output}")

    # Optional Markdown
    if args.markdown:
        md_path = args.output.replace(".json", ".md")
        with open(md_path, "w") as f:
            f.write(_format_markdown(report))
        print(f"✅ Wrote Markdown: {md_path}")


def _format_markdown(report: dict) -> str:
    """Generate Markdown report from JSON data."""
    md = []
    md.append(f"# sv_query Benchmark Report\n")
    meta = report["metadata"]
    md.append(f"**Project**: `{meta['filelist']}`")
    md.append(f"**Target**: `{meta['target']}` (depth={meta['depth']})")
    md.append(f"**Build time**: {meta['build_time_seconds']}s")
    md.append(f"**Generated**: {meta['timestamp']}\n")

    md.append("## L1 — Module-level Extraction (AST)\n")
    l1 = report["L1_module_extraction"]
    if "error" in l1:
        md.append(f"❌ Error: {l1['error']}\n")
    else:
        md.append(f"- **Instance count** at depth={l1['depth']}: **{l1['instance_count']}**")
        if l1.get("instances"):
            md.append("\n### Instance tree:\n")
            for inst in l1["instances"]:
                indent = "  " * inst["depth"]
                md.append(f"{indent}- `{inst['name']}` → `{inst['def']}` (depth {inst['depth']})")
        md.append("")

    md.append("## L2 — Graph Topology (SignalGraph)\n")
    l2 = report["L2_graph_topology"]
    if "error" in l2:
        md.append(f"❌ Error: {l2['error']}\n")
    else:
        md.append(f"| Metric | Count |")
        md.append(f"|--------|------:|")
        md.append(f"| Nodes (total) | {l2['nodes']} |")
        md.append(f"| Edges (total) | {l2['edges']} |")
        md.append(f"| INSTANTIATED_MODULE | {l2['instantiated_modules']} |")
        md.append(f"| PORT_IN | {l2['port_in']} |")
        md.append(f"| PORT_OUT | {l2['port_out']} |")
        md.append(f"| SIGNAL | {l2['signal']} |")
        md.append("")
        if l2.get("depth_distribution"):
            md.append("**Depth distribution (by `.` count):**\n")
            md.append("| Depth | Nodes |")
            md.append("|------:|------:|")
            for d, c in l2["depth_distribution"].items():
                md.append(f"| {d} | {c} |")
            md.append("")

    md.append("## L3 — Signal Traces (fanin/fanout)\n")
    l3 = report["L3_signal_traces"]
    md.append("| Signal | fanin | fanout |")
    md.append("|--------|------:|-------:|")
    for sig, res in l3.items():
        if "error" in res:
            md.append(f"| `{sig}` | ❌ | ❌ |")
        else:
            md.append(f"| `{sig}` | {res['fanin']} | {res['fanout']} |")
    md.append("")

    md.append("## L4 — Cross-instance Port Edges (MIG)\n")
    l4 = report["L4_cross_instance_edges"]
    if "error" in l4:
        md.append(f"❌ Error: {l4['error']}\n")
    else:
        md.append(f"- **Total edges**: {l4['edge_count']}")
        md.append(f"- **In-scope edges** (both endpoints in target): {l4['in_scope_count']}")
        if l4.get("top_ports"):
            md.append("\n**Top shared ports**:\n")
            md.append("| Port | Connection count |")
            md.append("|------|------------------:|")
            for port, cnt in l4["top_ports"].items():
                md.append(f"| `{port}` | {cnt} |")
        md.append("")

    md.append("## Flakiness\n")
    flk = report["flakiness"]
    if flk is None:
        md.append("_Skipped._\n")
    elif "error" in flk:
        md.append(f"❌ Error: {flk['error']}\n")
    else:
        md.append(f"**{flk['runs']} independent runs**:\n")
        md.append(f"- Node range: **{flk['node_min']} - {flk['node_max']}** (stdev {flk['node_stdev']:.1f})")
        md.append(f"- IM range: **{flk['im_min']} - {flk['im_max']}**")
        md.append(f"- IM deterministic ratio: **{flk['deterministic_ratio_im']*100:.0f}%**")
        md.append("")
        md.append("**Node counts per run:**\n")
        for i, c in enumerate(flk["node_counts"], 1):
            md.append(f"  - Run {i}: {c}")
        md.append("")
        md.append("**IM counts per run:**\n")
        for i, c in enumerate(flk["im_counts"], 1):
            md.append(f"  - Run {i}: {c}")
        md.append("")

    md.append("## Summary\n")
    md.append(f"4-dimensional capability check on `{meta['target']}`:\n")
    if "error" not in l1:
        md.append(f"- [x] **L1**: {l1['instance_count']} instances extracted")
    if "error" not in l2:
        md.append(f"- [x] **L2**: {l2['nodes']} nodes / {l2['edges']} edges / {l2['instantiated_modules']} IM")
    if "error" not in l4:
        md.append(f"- [x] **L4**: {l4['in_scope_count']} cross-instance edges")
    if flk and "error" not in flk:
        det = flk["deterministic_ratio_im"] * 100
        status = "🟢" if det >= 80 else "🟡" if det >= 50 else "🔴"
        md.append(f"- [{status}] **Flakiness**: {det:.0f}% IM deterministic")
    md.append("")

    return "\n".join(md)


if __name__ == "__main__":
    main()
