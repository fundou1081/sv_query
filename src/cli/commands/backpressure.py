# ==============================================================================
# backpressure.py - Bus backpressure topology analysis
# =============================================================================
"""
Usage:
  python run_cli.py backpressure analyze --filelist <filelist> [--output <mmd>]
  python run_cli.py backpressure analyze --filelist <filelist> --protocol-confirm
  python run_cli.py backpressure analyze -f <top.sv> --channel AW --protocol-confirm

Analyzes AXI/TL-UL bus backpressure topology.
  --protocol-confirm: use handshake_detector to confirm handshake semantics
  Default: generate Mermaid topology diagram
"""

import re
import sys
from pathlib import Path
from typing import Optional

import typer

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from trace.core.handshake_detector import (
    classify_signal_channel,
    detect_handshake_type,
    detect_from_signal_pair,
)
from trace.core.query.signal import SignalTracer
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
# Protocol Confirm Mode (Phase B)
# ==============================================================================

def _run_protocol_confirm(tracer: UnifiedTracer, filter_channels: list, max_signals: int):
    """使用 handshake_detector 分析所有 ready/valid 信号的握手类型"""
    graph = tracer.build_graph()
    signal_tracer = SignalTracer(graph)

    all_nodes = list(graph.nodes())
    bp_nodes = {}  # name -> (layer, channel)

    for node_id in all_nodes:
        parts = node_id.split(".")
        if len(parts) > 2:
            continue
        if _is_backpressure_signal(node_id) and _matches_channel(node_id, filter_channels):
            layer = _classify_signal_layer(node_id)
            channel = classify_signal_channel(node_id)
            bp_nodes[node_id] = (layer, channel)

    # 分类为 valid 信号 和 ready 信号
    valid_signals = [n for n in bp_nodes if "valid" in n.lower()]
    ready_signals = [n for n in bp_nodes if "ready" in n.lower()]

    valid_signals.sort()
    ready_signals.sort()


    # 建立 (valid, ready) 配对：按通道+前缀匹配
    # 例如: axi_adapter.s_axi_awvalid <-> axi_adapter.s_axi_awready
    #       axi_adapter.m_axi_awvalid <-> axi_adapter.m_axi_awready
    def _strip_suffix(sig):
        """去掉 _next/_reg/_int/_early/_valid/_ready 后缀，统一配对前缀"""
        s = sig.lower()
        for suf in ['next', 'reg', 'int', 'early']:
            if s.endswith('_' + suf):
                s = s[:-len('_' + suf)]
            elif s.endswith(suf):
                s = s[:-len(suf)]
        for suf in ['valid', 'ready']:
            if s.endswith('_' + suf):
                s = s[:-len('_' + suf)]
            elif s.endswith(suf):
                s = s[:-len(suf)]
        return s

    pairs = []
    paired_valid = set()
    for r in ready_signals:
        r_base = _strip_suffix(r)
        best_v = None
        for v in valid_signals:
            if v in paired_valid:
                continue
            v_base = _strip_suffix(v)
            if v_base == r_base and v_base:
                pairs.append((v, r))
                paired_valid.add(v)
                best_v = v
                break

    results = []
    for valid, ready in pairs[:max_signals]:
        try:
            hi = detect_from_signal_pair(signal_tracer, valid, ready)
            results.append(hi)
        except Exception:
            pass

    return results


def _print_protocol_confirm_table(results, filter_channels: list):
    """打印握手分析结果表格"""
    if not results:
        print("No handshake pairs found.")
        return

    # 按通道分组
    by_channel = {}
    for hi in results:
        by_channel.setdefault(hi.channel, []).append(hi)

    print("")
    print("=" * 100)
    print("  AXI Bus Handshake Analysis (Phase B: handshake_detector)")
    print("=" * 100)

    type_emoji = {
        "STANDARD_AXI": "✅",
        "COMBINATIONAL_BP": "🔄",
        "REGISTERED_BP": "⏱️",
        "LATCHED_BP": "🔒",
        "WIRE_PASSTHROUGH": "🔌",
        "PORT_PASSTHROUGH": "🔗",
        "CONDITIONAL_CTRL": "⚙️",
        "UNUSED": "❌",
        "UNKNOWN": "❓",
        "COMPLEX_ARB": "🔀",
    }

    type_desc = {
        "STANDARD_AXI": "if (v && r) 标准AXI握手",
        "COMBINATIONAL_BP": "assign r = !fifo_full (组合FIFO反压)",
        "REGISTERED_BP": "always_ff r <= next (寄存器延迟)",
        "LATCHED_BP": "latch 锁存器反压",
        "WIRE_PASSTHROUGH": "assign r = other (透传线)",
        "PORT_PASSTHROUGH": "port connection (跨模块透传)",
        "CONDITIONAL_CTRL": "条件驱动 (非握手)",
        "UNUSED": "无驱动/悬空",
        "UNKNOWN": "条件不明确",
        "COMPLEX_ARB": "复杂仲裁条件",
    }

    for ch in ["AW", "W", "B", "AR", "R", "A", "D", "UNKNOWN"]:
        if ch not in by_channel:
            continue
        if filter_channels and ch not in filter_channels and "UNKNOWN" not in filter_channels:
            continue
        print(f"\n  ── {ch} Channel ──")
        print(f"  {'Ready Signal':<45} {'Valid':<25} {'Type':<20} {'Condition'[:30]}")
        print(f"  {'-'*45} {'-'*25} {'-'*20} {'-'*30}")

        for hi in by_channel[ch]:
            if not hi.ready:
                continue
            emoji = type_emoji.get(hi.handshake_type, "❓")
            desc = type_desc.get(hi.handshake_type, "")
            ready_short = hi.ready.split(".")[-1] if "." in hi.ready else hi.ready
            valid_short = (hi.valid.split(".")[-1] if "." in hi.valid else hi.valid) if hi.valid else "-"
            cond_short = (hi.condition[:28] + "..") if len(hi.condition) > 30 else hi.condition
            clock_str = f" @{hi.clock_domain}" if hi.clock_domain else ""
            extra_str = ""
            if hi.extra.get("fifo_name"):
                extra_str = f" [fifo={hi.extra['fifo_name']}]"
            print(f"  {emoji} {ready_short:<43} {valid_short:<25} {hi.handshake_type:<20} {cond_short}{clock_str}{extra_str}")

    print("")
    #统计
    stats = {}
    for hi in results:
        t = hi.handshake_type
        stats[t] = stats.get(t, 0) + 1
    print(f"  Summary:")
    for t, cnt in sorted(stats.items(), key=lambda x: -x[1]):
        print(f"    {type_emoji.get(t,'❓')} {t}: {cnt}")


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
    protocol_confirm: bool = typer.Option(False, "--protocol-confirm", "-p", help="Phase B: confirm handshake semantics with handshake_detector"),
) -> None:
    """Analyze bus backpressure topology"""
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

    # ── Phase B: Protocol Confirm Mode ──────────────────────────────────────
    if protocol_confirm:
        results = _run_protocol_confirm(tracer, filter_channels, max_signals * 10)
        _print_protocol_confirm_table(results, filter_channels)
        return

    # ── Default: Mermaid Topology Mode ────────────────────────────────────────
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