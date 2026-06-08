# ==============================================================================
# backpressure.py - Bus backpressure topology analysis
# =============================================================================
"""
Usage:
  python run_cli.py backpressure --filelist <filelist> [--output <mmd>]
  python run_cli.py backpressure -f <top.sv> [--output <mmd>]

Analyzes AXI/TL-UL bus backpressure topology and generates a Mermaid diagram.
Identifies ready/valid handshake chains, FIFO full/empty signals, and crossbar
arbitration paths.
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


# Channel filter patterns
CHANNEL_PATTERNS = {
    "AW": ["awvalid", "awready", "aw_addr", "awvalid_next", "awready_next", "awvalid_reg", "awready_reg"],
    "W":  ["wvalid", "wready", "w_data", "wvalid_next", "wready_next", "wvalid_reg", "wready_reg"],
    "B":  ["bvalid", "bready", "bresp", "bvalid_next", "bready_next", "bvalid_reg", "bready_reg"],
    "AR": ["arvalid", "arready", "ar_addr", "arvalid_next", "arready_next", "arvalid_reg", "arready_reg"],
    "R":  ["rvalid", "rready", "r_data", "rvalid_next", "rready_next", "rvalid_reg", "rready_reg"],
}

# Layer classification
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
    """Classify signal into bus topology layer."""
    name_lower = signal_name.lower()
    for layer, keywords in LAYER_KEYWORDS.items():
        for kw in keywords:
            if kw in name_lower:
                return layer
    return "OTHER"


def _is_backpressure_signal(signal_name: str) -> bool:
    """Check if signal is backpressure related."""
    name_lower = signal_name.lower()
    for pattern in BP_PATTERNS:
        if pattern in name_lower:
            return True
    return False


def _matches_channel(signal_name: str, channels: list) -> bool:
    """Check if signal matches the given AXI channel(s)."""
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
    """Make signal name safe for Mermaid node ID."""
    safe = re.sub(r'[^a-zA-Z0-9_]', '_', name)
    if safe[0].isdigit():
        safe = 'n_' + safe
    return safe


@backpressure_app.command(name="analyze")
def analyze(
    file: str = typer.Option(None, "--file", "-f", help="SystemVerilog source file"),
    filelist: str = typer.Option(None, "--filelist", help="Path to filelist (.f/.fl) for multi-file projects"),
    output: str = typer.Option(None, "--output", "-o", help="Output Mermaid file (default: stdout)"),
    max_depth: int = typer.Option(3, "--max-depth", "-d", help="Maximum chain depth for tracing"),
    include: str = typer.Option(None, "--include", "-I", help="Include directory (comma-separated)"),
    max_signals: int = typer.Option(40, "--max-signals", "-n", help="Max backpressure signals to show per layer"),
    channel: str = typer.Option(None, "--channel", "-c", help="Filter by AXI channel: AW|W|B|AR|R (comma-separated for multiple)"),
) -> None:
    """Analyze bus backpressure topology and generate Mermaid diagram"""
    if not file and not filelist:
        print("Error: Either --file or --filelist must be provided", file=sys.stderr)
        raise typer.Exit(code=1)

    include_dirs = include.split(",") if include else None

    try:
        if filelist:
            tracer = UnifiedTracer(filelist=filelist, include_dirs=include_dirs)
        else:
            with open(file) as f:
                sources = {file: f.read()}
            tracer = UnifiedTracer(sources=sources, include_dirs=include_dirs)

        graph = tracer.build_graph()
    except Exception as e:
        print(f"Error building graph: {e}", file=sys.stderr)
        raise typer.Exit(code=1) from None

    # Collect all nodes and classify
    all_nodes = list(graph.nodes())
    bp_nodes = {}  # name -> (layer, kind)

    filter_channels = [c.strip().upper() for c in channel.split(",")] if channel else []

    for node_id in all_nodes:
        # Skip sub-module internal signals (depth >= 3 in path)
        parts = node_id.split(".")
        if len(parts) > 2:
            continue  # Skip sub-module internals

        if _is_backpressure_signal(node_id) and _matches_channel(node_id, filter_channels):
            layer = _classify_signal_layer(node_id)
            node = graph.get_node(node_id)
            kind = str(node.kind) if node else "SIG"
            bp_nodes[node_id] = (layer, kind)

    # Limit signals per layer
    layer_nodes = {"SLAVE": [], "ADAPTER": [], "CROSSBAR": [], "MASTER": [], "OTHER": []}
    for name, (layer, kind) in bp_nodes.items():
        layer_nodes[layer].append((name, kind))

    # Sort each layer and limit
    for layer in layer_nodes:
        layer_nodes[layer].sort(key=lambda x: x[0])
        layer_nodes[layer] = layer_nodes[layer][:max_signals // 5]

    # Build edges between backpressure signals
    all_edges = list(graph.edges())
    bp_edge_set = set()  # (src, dst)

    for src, dst in all_edges:
        if src in bp_nodes or dst in bp_nodes:
            # Include edges between two backpressure signals, OR from/to POR nodes
            src_is_bp = src in bp_nodes
            dst_is_bp = dst in bp_nodes
            if src_is_bp and dst_is_bp:
                bp_edge_set.add((src, dst))
            elif src_is_bp:
                bp_edge_set.add((src, dst))  # src=bp, dst=non-bp (e.g. intermediate driver)
            elif dst_is_bp:
                bp_edge_set.add((src, dst))  # src=non-bp (e.g. POR), dst=bp

    # Generate Mermaid
    lines = ["flowchart TB"]
    lines.append("    %% Bus Backpressure Topology")
    lines.append("    %% Generated by sv_query backpressure command")
    lines.append("")

    # Define subgraphs by layer
    for layer in ["SLAVE", "ADAPTER", "CROSSBAR", "MASTER", "OTHER"]:
        nodes = layer_nodes[layer]
        if not nodes:
            continue
        lines.append("    subgraph " + layer)
        for name, kind in nodes:
            safe_id = _safe_name(name)
            if layer == "SLAVE":
                emoji = "🔵"
            elif layer == "ADAPTER":
                emoji = "🔷"
            elif layer == "CROSSBAR":
                emoji = "🟠"
            elif layer == "MASTER":
                emoji = "🔴"
            else:
                emoji = "⚪"
            lines.append('        %s["%s %s"]' % (safe_id, emoji, name.split(".")[-1]))
        lines.append("    end")
        lines.append("")

    lines.append("    %% Backpressure Edges")
    lines.append("")

    # Add edges (deduplicated)
    for src, dst in sorted(bp_edge_set):
        src_safe = _safe_name(src)
        dst_safe = _safe_name(dst)
        src_layer = bp_nodes.get(src, ("OTHER", ""))[0]
        dst_layer = bp_nodes.get(dst, ("OTHER", ""))[0]

        # Different style for cross-layer edges
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