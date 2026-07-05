# ==============================================================================
# backpressure.py - Bus backpressure topology analysis
# =============================================================================
"""
Usage:
  python run_cli.py backpressure analyze --filelist <filelist> [--output <mmd>]
  python run_cli.py backpressure analyze -f <top.sv> --channel AW

Analyzes AXI/TL-UL bus backpressure topology and generates Mermaid diagram.

For signal-level handshake classification, use:
  sv_query handshake scan --filelist xxx
  sv_query handshake analyze --filelist xxx --signal yyy
  sv_query handshake pair --filelist xxx --ready yyy
"""

import re
import sys
from pathlib import Path

import typer

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from trace.core.handshake_detector import (
    HandshakeInfo,
    detect_handshake_type,
    detect_handshake_type_with_node,
)
from trace.core.query.signal import SignalTracer
from trace.unified_tracer import UnifiedTracer

backpressure_app = typer.Typer(help="Bus backpressure topology analysis: AXI/TL-UL ready/valid chain visualization")


# Handshake type emoji for Mermaid node labels
_HANDSHAKE_EMOJI = {
    "STANDARD_AXI":       "✅",
    "COMBINATIONAL_BP":   "🔄",
    "REGISTERED_BP":      "⏱️",
    "LATCHED_BP":         "🔒",
    "WIRE_PASSTHROUGH":   "🔌",
    "PORT_PASSTHROUGH":   "🔗",
    "CONDITIONAL_CTRL":   "⚙️",
    "UNUSED":             "❌",
    "UNKNOWN":            "❓",
    "COMPLEX_ARB":        "🔀",
}

# Backpressure-relevant types: actually participate in backpressure flow
# WIRE/PORT_PASSTHROUGH are wires, not real backpressure sources
# CONDITIONAL_CTRL is state-machine driven (still relevant to backpressure)
_BACKPRESSURE_RELEVANT = {
    "STANDARD_AXI", "COMBINATIONAL_BP", "REGISTERED_BP", "LATCHED_BP",
    "CONDITIONAL_CTRL", "COMPLEX_ARB",
}

_PASSTHROUGH_TYPES = {"WIRE_PASSTHROUGH", "PORT_PASSTHROUGH"}


# Backpressure signal name patterns
BP_PATTERNS = [
    "_ready", "_valid", "_full", "_empty",
    "_grant", "_stall", "_pause", "_wait",
    "ready_next", "ready_int", "valid_next", "valid_int",
    "aw_ready", "w_ready", "b_ready", "ar_ready", "r_ready",
    "aw_valid", "w_valid", "b_valid", "ar_valid", "r_valid",
    "m_ready", "s_ready", "m_valid", "s_valid",
]


CHANNEL_PATTERNS = {
    "AW": ["awvalid", "awready", "aw_addr", "awvalid_next", "awready_next", "awvalid_reg", "awready_reg"],
    "W":  ["wvalid", "wready", "w_data", "wvalid_next", "wready_next", "wvalid_reg", "wready_reg"],
    "B":  ["bvalid", "bready", "bresp", "bvalid_next", "bready_next", "bvalid_reg", "bready_reg"],
    "AR": ["arvalid", "arready", "ar_addr", "arvalid_next", "arready_next", "arvalid_reg", "arready_reg"],
    "R":  ["rvalid", "rready", "r_data", "rvalid_next", "rready_next", "rvalid_reg", "rready_reg"],
}

LAYER_KEYWORDS = {
    "SLAVE": ["s_axi", "s_axil", "s_axis", "slave", "upstream"],
    "ADAPTER": ["adapter", "fifo", "buf", "queue"],
    "CROSSBAR": ["crossbar", "interconnect", "router", "demux", "mux"],
    "MASTER": ["m_axi", "m_axil", "m_axis", "master", "downstream"],
}

LAYER_COLORS = {
    "SLAVE": "#4CAF50",
    "ADAPTER": "#2196F3",
    "CROSSBAR": "#FF9800",
    "MASTER": "#F44336",
}


def _classify_signal_layer(signal_name: str) -> str:
    name_lower = signal_name.lower()
    for layer, keywords in LAYER_KEYWORDS.items():
        for kw in keywords:
            if kw in name_lower:
                return layer
    return "OTHER"


def _is_backpressure_signal(signal_name: str) -> bool:
    name_lower = signal_name.lower()
    for pattern in BP_PATTERNS:
        if pattern in name_lower:
            return True
    return False


def _matches_channel(signal_name: str, channels: list) -> bool:
    if not channels:
        return True
    name_lower = signal_name.lower()
    for ch in channels:
        ch_upper = ch.upper()
        if ch_upper in CHANNEL_PATTERNS:
            for pattern in CHANNEL_PATTERNS[ch_upper]:
                if pattern in name_lower:
                    return True
    return False


def _safe_name(name: str) -> str:
    safe = re.sub(r'[^a-zA-Z0-9_]', '_', name)
    if safe[0].isdigit():
        safe = 'n_' + safe
    return safe


def _classify_handshakes(graph, signal_names: list) -> dict[str, HandshakeInfo]:
    """使用 handshake_detector 为每个 ready/valid 信号分类握手类型

    Returns:
        {signal_name: HandshakeInfo}
    """
    st = SignalTracer(graph)
    results = {}
    for sig in signal_names:
        try:
            dis = st.trace_fanin_detailed(sig)
            node = graph.get_node(sig)
            node_kind = str(node.kind) if node else None
            if dis:
                hi = detect_handshake_type_with_node(sig, dis, node_kind=node_kind)
                results[sig] = hi
            else:
                # 使用带节点信息的版本以区分 PORT_IN
                hi = detect_handshake_type_with_node(sig, dis or [], node_kind=node_kind)
                results[sig] = hi
        except Exception:
            results[sig] = HandshakeInfo(
                valid="", ready=sig,
                handshake_type="UNKNOWN",
                channel="UNKNOWN",
                condition="", effective_condition="",
                assign_type="", clock_domain="", extra={}
            )
    return results


# ==============================================================================
# analyze command
# ==============================================================================

@backpressure_app.command(name="analyze")
def analyze(
    file: str = typer.Option(None, "--file", "-f", help="SystemVerilog source file"),
    filelist: str = typer.Option(None, "--filelist", help="Path to filelist (.f/.fl) for multi-file projects"),
    output: str = typer.Option(None, "--output", "-o", help="Output Mermaid file (default: stdout)"),
    include: str = typer.Option(None, "--include", "-I", help="Include directory (comma-separated)"),
    max_signals: int = typer.Option(40, "--max-signals", "-n", help="Max backpressure signals to show per layer"),
    channel: str = typer.Option(None, "--channel", "-c", help="Filter by AXI channel: AW|W|B|AR|R (comma-separated)"),
    show_passthroughs: bool = typer.Option(False, "--show-passthroughs", help="Show wire/port passthroughs (default: hidden)"),
) -> None:
    """Analyze bus backpressure topology and generate Mermaid diagram.

    For signal-level handshake classification, use `sv_query handshake`:
      sv_query handshake scan --filelist xxx
      sv_query handshake analyze --filelist xxx --signal yyy
      sv_query handshake pair --filelist xxx --ready yyy
    """
    if not file and not filelist:
        print("Error: Either --file or --filelist must be provided", file=sys.stderr)
        raise typer.Exit(code=1)

    include_dirs = include.split(",") if include else None
    filter_channels = [c.strip().upper() for c in channel.split(",")] if channel else []

    try:
        if filelist:
            tracer = UnifiedTracer(filelist=filelist, include_dirs=include_dirs)
        else:
            with open(file) as f:
                sources = {file: f.read()}
            tracer = UnifiedTracer(sources=sources, include_dirs=include_dirs)
    except Exception as e:
        print(f"Error building tracer: {e}", file=sys.stderr)
        raise typer.Exit(code=1) from None

    # ── Mermaid Topology Mode ────────────────────────────────────────
    try:
        graph = tracer.build_graph()
    except Exception as e:
        print(f"Error building graph: {e}", file=sys.stderr)
        raise typer.Exit(code=1) from None

    all_nodes = list(graph.nodes())
    candidate_nodes = {}

    for node_id in all_nodes:
        parts = node_id.split(".")
        if len(parts) > 2:
            continue
        if _is_backpressure_signal(node_id) and _matches_channel(node_id, filter_channels):
            layer = _classify_signal_layer(node_id)
            node = graph.get_node(node_id)
            kind = str(node.kind) if node else "SIG"
            candidate_nodes[node_id] = (layer, kind)

    # ── Phase B: handshake classification filter ─────────────────────
    handshake_info = _classify_handshakes(graph, list(candidate_nodes.keys()))

    bp_nodes = {}  # 最终画进拓扑图的节点
    filtered_out = {}  # 被过滤掉的 (--show-passthroughs 时补上)
    for sig, (layer, kind) in candidate_nodes.items():
        hi = handshake_info.get(sig)
        ht = hi.handshake_type if hi else "UNKNOWN"
        if ht in _PASSTHROUGH_TYPES and not show_passthroughs:
            filtered_out[sig] = (layer, kind, ht)
            continue
        bp_nodes[sig] = (layer, kind, ht)

    layer_nodes = {"SLAVE": [], "ADAPTER": [], "CROSSBAR": [], "MASTER": [], "OTHER": []}
    for name, (layer, kind, ht) in bp_nodes.items():
        layer_nodes[layer].append((name, kind, ht))

    for layer in layer_nodes:
        layer_nodes[layer].sort(key=lambda x: x[0])
        layer_nodes[layer] = layer_nodes[layer][:max_signals // 5]

    all_edges = list(graph.edges())
    bp_edge_set = set()

    for src, dst in all_edges:
        src_is_bp = src in bp_nodes
        dst_is_bp = dst in bp_nodes
        if src_is_bp and dst_is_bp:
            bp_edge_set.add((src, dst))
        elif src_is_bp:
            bp_edge_set.add((src, dst))
        elif dst_is_bp:
            bp_edge_set.add((src, dst))

    lines = ["flowchart TB"]
    lines.append("    %% Bus Backpressure Topology")
    lines.append("    %% Generated by sv_query backpressure command")
    lines.append("    %% Legend: ✅STANDARD_AXI 🔄COMB_BP ⏱️REG_BP ⚙️COND_CTRL 🔌🔗PASSTHROUGH")

    # 统计
    type_stats = {}
    for sig, (layer, kind, ht) in bp_nodes.items():
        type_stats[ht] = type_stats.get(ht, 0) + 1
    for sig, (layer, kind, ht) in filtered_out.items():
        type_stats[f"[filtered:{ht}]"] = type_stats.get(f"[filtered:{ht}]", 0) + 1

    lines.append("")

    for layer in ["SLAVE", "ADAPTER", "CROSSBAR", "MASTER", "OTHER"]:
        nodes = layer_nodes[layer]
        if not nodes:
            continue
        lines.append("    subgraph " + layer)
        for name, kind, ht in nodes:
            safe_id = _safe_name(name)
            layer_emoji = {"SLAVE": "🔵", "ADAPTER": "🔷", "CROSSBAR": "🟠", "MASTER": "🔴"}.get(layer, "⚪")
            hs_emoji = _HANDSHAKE_EMOJI.get(ht, "❓")
            short_name = name.split(".")[-1]
            # Mermaid label: emoji + signal short name + handshake type tag
            lines.append('        %s["%s %s<br/><i>%s</i>"]' % (safe_id, layer_emoji, short_name, ht))
        lines.append("    end")
        lines.append("")

    lines.append("    %% Backpressure Edges")
    lines.append("")

    for src, dst in sorted(bp_edge_set):
        src_safe = _safe_name(src)
        dst_safe = _safe_name(dst)
        src_layer = bp_nodes.get(src, ("OTHER", "", ""))[0]
        dst_layer = bp_nodes.get(dst, ("OTHER", "", ""))[0]
        src_ht = bp_nodes.get(src, ("OTHER", "", "UNKNOWN"))[2]
        if src_layer != dst_layer:
            tag = f"{src_ht}"
            lines.append('    %s -.->|"%s"| %s' % (src_safe, tag, dst_safe))
        else:
            lines.append('    %s --> %s' % (src_safe, dst_safe))

    mermaid_code = "\n".join(lines)

    if output:
        with open(output, "w") as f:
            f.write(mermaid_code)
        _print_backpressure_stats(bp_nodes, bp_edge_set, filtered_out, layer_nodes, type_stats, output)
    else:
        # [FIX 2026-07-05] 即使没 --output 也输出统计行 — 让 CLI 用户能看到 BP 信号数 / edges / filtered out
        print(mermaid_code)
        _print_backpressure_stats(bp_nodes, bp_edge_set, filtered_out, layer_nodes, type_stats)


def _print_backpressure_stats(bp_nodes, bp_edge_set, filtered_out, layer_nodes, type_stats, output_path=None):
    """[FIX 2026-07-05] Print backpressure analysis stats (always, even without --output)"""
    if output_path:
        print("✓ Mermaid: " + output_path)
    print("  Backpressure signals: " + str(len(bp_nodes)))
    print("  Edges: " + str(len(bp_edge_set)))
    print("  Filtered out (passthroughs): " + str(len(filtered_out)))
    active_layers = ", ".join(l for l in ["SLAVE", "ADAPTER", "CROSSBAR", "MASTER", "OTHER"] if layer_nodes[l])
    print("  Layers: " + active_layers)
    print("")
    print("  Handshake type breakdown:")
    for t, cnt in sorted(type_stats.items(), key=lambda x: -x[1]):
        print(f"    {_HANDSHAKE_EMOJI.get(t, '❓')} {t}: {cnt}")




if __name__ == "__main__":
    backpressure_app()


# ==============================================================================
# [B 2026-06-13] deadlock 子命令 — 静态死锁候选检测
# ==============================================================================

@backpressure_app.command(name="deadlock")
def deadlock(
    file: str = typer.Option(None, "--file", "-f", help="SystemVerilog source file"),
    filelist: str = typer.Option(None, "--filelist", help="Path to filelist for multi-file projects"),
    include: str = typer.Option(None, "--include", "-I", help="Include directory (comma-separated)"),
    protocol: str = typer.Option(
        "TL-UL", "--protocol", "-p",
        help="Protocol name (TL-UL/AXI4/AHB/APB) — drives semantics rules",
    ),
    semantics_dir: str = typer.Option(
        "config/protocols/semantics", "--semantics-dir",
        help="Path to semantics YAML directory",
    ),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
    strict: bool = typer.Option(False, "--strict/--no-strict", help="Strict mode (default non-strict: 优雅降级)"),
) -> None:
    """[B 2026-06-13] [EXPERIMENTAL] Static deadlock candidate detection.

    从 SignalGraph + ProtocolSemantics 检测:
      - combinational loop (valid ↔ ready 环)
      - cross-channel loop (跨通道 ready 链环)
      - response_after_request (响应不到达请求 driver 链)
    """
    from trace.unified_tracer import UnifiedTracer
    from applications.bus.semantics import load_semantics
    from applications.bus.deadlock import detect_deadlock_candidates

    # 1. 加载语义
    try:
        sem = load_semantics(protocol, dir_path=semantics_dir)
    except FileNotFoundError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)

    # 2. 构造 graph
    if not file and not filelist:
        typer.echo("Error: need --file or --filelist", err=True)
        raise typer.Exit(1)
    include_dirs = include.split(",") if include else None
    try:
        if filelist:
            tracer = UnifiedTracer(filelist=filelist, include_dirs=include_dirs, strict=strict)
        else:
            with open(file) as f:
                sources = {file: f.read()}
            tracer = UnifiedTracer(sources=sources, include_dirs=include_dirs, strict=strict)
    except Exception as e:
        typer.echo(f"Error building tracer: {e}", err=True)
        raise typer.Exit(1)

    # 3. 抑制 stdout 噪声, 在 --json 模式下 progress 走 stderr
    if json_output:
        _info = lambda msg: typer.echo(msg, err=True)
    else:
        _info = typer.echo
    _info(f"Protocol: {sem.protocol}")
    _info(f"Rules: {len(sem.deadlock_rules)}")

    graph = tracer.build_graph()
    _info(f"Graph: {graph.number_of_nodes()} nodes, {graph.number_of_edges()} edges")

    # 4. 检测
    findings = detect_deadlock_candidates(sem, graph)

    # 5. 输出
    if json_output:
        import json
        from dataclasses import asdict
        result = {
            "protocol": sem.protocol,
            "graph_nodes": graph.number_of_nodes(),
            "graph_edges": graph.number_of_edges(),
            "findings": [asdict(f) for f in findings],
            "summary": {
                "total": len(findings),
                "errors": sum(1 for f in findings if f.severity == "error"),
                "warnings": sum(1 for f in findings if f.severity == "warning"),
                "info": sum(1 for f in findings if f.severity == "info"),
            },
        }
        typer.echo(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        if not findings:
            _info("✓ No deadlock candidates found")
        else:
            _info(f"\n=== {len(findings)} deadlock candidate(s) ===")
            for f in findings:
                icon = {"error": "🔴", "warning": "🟡", "info": "ℹ️"}.get(f.severity, "•")
                _info(f"\n  {icon} [{f.severity}] {f.rule_id} ({f.kind})")
                _info(f"      {f.description}")
                if f.node_ids:
                    _info(f"      nodes: {', '.join(f.node_ids[:3])}{'...' if len(f.node_ids) > 3 else ''}")
                if f.evidence:
                    _info(f"      evidence: {f.evidence}")
            # summary
            n_err = sum(1 for f in findings if f.severity == "error")
            n_warn = sum(1 for f in findings if f.severity == "warning")
            n_info = sum(1 for f in findings if f.severity == "info")
            _info(f"\nSummary: {n_err} error(s), {n_warn} warning(s), {n_info} info")