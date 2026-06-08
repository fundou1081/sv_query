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

from trace.unified_tracer import UnifiedTracer

backpressure_app = typer.Typer(help="Bus backpressure topology analysis: AXI/TL-UL ready/valid chain visualization")


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
    bp_nodes = {}

    for node_id in all_nodes:
        parts = node_id.split(".")
        if len(parts) > 2:
            continue
        if _is_backpressure_signal(node_id) and _matches_channel(node_id, filter_channels):
            layer = _classify_signal_layer(node_id)
            node = graph.get_node(node_id)
            kind = str(node.kind) if node else "SIG"
            bp_nodes[node_id] = (layer, kind)

    layer_nodes = {"SLAVE": [], "ADAPTER": [], "CROSSBAR": [], "MASTER": [], "OTHER": []}
    for name, (layer, kind) in bp_nodes.items():
        layer_nodes[layer].append((name, kind))

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
    lines.append("")

    for layer in ["SLAVE", "ADAPTER", "CROSSBAR", "MASTER", "OTHER"]:
        nodes = layer_nodes[layer]
        if not nodes:
            continue
        lines.append("    subgraph " + layer)
        for name, kind in nodes:
            safe_id = _safe_name(name)
            emoji = {"SLAVE": "🔵", "ADAPTER": "🔷", "CROSSBAR": "🟠", "MASTER": "🔴"}.get(layer, "⚪")
            lines.append('        %s["%s %s"]' % (safe_id, emoji, name.split(".")[-1]))
        lines.append("    end")
        lines.append("")

    lines.append("    %% Backpressure Edges")
    lines.append("")

    for src, dst in sorted(bp_edge_set):
        src_safe = _safe_name(src)
        dst_safe = _safe_name(dst)
        src_layer = bp_nodes.get(src, ("OTHER", ""))[0]
        dst_layer = bp_nodes.get(dst, ("OTHER", ""))[0]
        if src_layer != dst_layer:
            lines.append('    %s -.->|"%s"| %s' % (src_safe, dst_layer, dst_safe))
        else:
            lines.append('    %s --> %s' % (src_safe, dst_safe))

    mermaid_code = "\n".join(lines)

    if output:
        with open(output, "w") as f:
            f.write(mermaid_code)
        print("✓ Mermaid: " + output)
        print("  Backpressure signals: " + str(len(bp_nodes)))
        print("  Edges: " + str(len(bp_edge_set)))
        active_layers = ", ".join(l for l in ["SLAVE", "ADAPTER", "CROSSBAR", "MASTER", "OTHER"] if layer_nodes[l])
        print("  Layers: " + active_layers)
    else:
        print(mermaid_code)


if __name__ == "__main__":
    backpressure_app()