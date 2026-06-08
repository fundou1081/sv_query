# ==============================================================================
# handshake.py - Bus handshake semantic analysis
# =============================================================================
"""
Usage:
  python run_cli.py handshake analyze --filelist <filelist> [--channel AW|W|B|AR|R|A|D]
  python run_cli.py handshake analyze --filelist <filelist> --signal <signal_name>
  python run_cli.py handshake scan --filelist <filelist> [--max-signals N]
  python run_cli.py handshake pair --filelist <filelist> --valid <v> --ready <r>

Analyzes ready/valid signal pairs and classifies handshake semantics.
Pure signal-level analysis — does NOT trace backpressure paths (use
`backpressure analyze` for that, which uses these results as input).
"""

import re
import sys
from pathlib import Path
from typing import Optional

import typer

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from trace.core.handshake_detector import (
    classify_signal_channel,
    detect_from_signal_pair,
    detect_handshake_type,
)
from trace.core.query.signal import SignalTracer
from trace.unified_tracer import UnifiedTracer

handshake_app = typer.Typer(help="Bus handshake semantic analysis: AXI/TL-UL ready/valid classification (Phase B)")


# ==============================================================================
# 信号名过滤
# ==============================================================================

READY_VALID_PATTERNS = [
    "_ready", "_valid", "_full", "_empty",
    "_grant", "_stall", "_pause", "_wait",
    "ready_next", "ready_int", "valid_next", "valid_int",
    "aw_ready", "w_ready", "b_ready", "ar_ready", "r_ready",
    "aw_valid", "w_valid", "b_valid", "ar_valid", "r_valid",
    "m_ready", "s_ready", "m_valid", "s_valid",
    "tready", "tvalid", "tlast", "tkeep", "tdata",
    "resp_ready", "resp_valid", "cmd_ready", "cmd_valid",
]


def _is_ready_or_valid(signal_name: str) -> bool:
    name_lower = signal_name.lower()
    for pattern in READY_VALID_PATTERNS:
        if pattern in name_lower:
            return True
    return False


def _matches_channel(signal_name: str, channels: list) -> bool:
    if not channels:
        return True
    ch = classify_signal_channel(signal_name)
    return ch in channels or ch == "UNKNOWN" and "UNKNOWN" in channels


def _strip_suffix(sig: str) -> str:
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


def _build_tracer(filelist: Optional[str], file: Optional[str], include: Optional[str]):
    """构造 UnifiedTracer，统一错误处理"""
    if not file and not filelist:
        print("Error: Either --file or --filelist must be provided", file=sys.stderr)
        raise typer.Exit(code=1)

    include_dirs = include.split(",") if include else None
    try:
        if filelist:
            return UnifiedTracer(filelist=filelist, include_dirs=include_dirs)
        with open(file) as f:
            sources = {file: f.read()}
        return UnifiedTracer(sources=sources, include_dirs=include_dirs)
    except Exception as e:
        print(f"Error building tracer: {e}", file=sys.stderr)
        raise typer.Exit(code=1) from None


# ==============================================================================
# 输出格式化
# ==============================================================================

TYPE_EMOJI = {
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

TYPE_DESC = {
    "STANDARD_AXI":       "if (v && r) 标准AXI握手",
    "COMBINATIONAL_BP":   "assign r = !fifo_full (组合FIFO反压)",
    "REGISTERED_BP":      "always_ff r <= next (寄存器延迟)",
    "LATCHED_BP":         "latch 锁存器反压",
    "WIRE_PASSTHROUGH":   "assign r = other (透传线)",
    "PORT_PASSTHROUGH":   "port connection (跨模块透传)",
    "CONDITIONAL_CTRL":   "条件驱动 (非握手)",
    "UNUSED":             "无驱动/悬空",
    "UNKNOWN":            "条件不明确",
    "COMPLEX_ARB":        "复杂仲裁条件",
}


def _print_pair(hi, indent: str = "  "):
    """打印单个 HandshakeInfo"""
    if not hi.ready:
        return
    emoji = TYPE_EMOJI.get(hi.handshake_type, "❓")
    ready_short = hi.ready.split(".")[-1] if "." in hi.ready else hi.ready
    valid_short = (hi.valid.split(".")[-1] if "." in hi.valid else hi.valid) if hi.valid else "-"
    cond = (hi.condition or "")[:50]
    clock_str = f" @{hi.clock_domain}" if hi.clock_domain else ""
    extra_str = ""
    if hi.extra.get("fifo_name") and hi.extra["fifo_name"] != "unknown":
        extra_str = f" [fifo={hi.extra['fifo_name']}]"
    if hi.extra.get("source_signal"):
        extra_str = f" [src={hi.extra['source_signal']}]"
    print(f"{indent}{emoji} {ready_short:<43} {valid_short:<25} {hi.handshake_type:<20} {cond}{clock_str}{extra_str}")


def _print_scan_table(results, filter_channels: list):
    """打印 scan 表格（按通道分组）"""
    if not results:
        print("No handshake pairs found.")
        return

    by_channel = {}
    for hi in results:
        by_channel.setdefault(hi.channel, []).append(hi)

    print("")
    print("=" * 100)
    print("  Handshake Analysis (Phase B: handshake_detector)")
    print("=" * 100)

    for ch in ["AW", "W", "B", "AR", "R", "A", "D", "UNKNOWN"]:
        if ch not in by_channel:
            continue
        if filter_channels and ch not in filter_channels:
            continue
        print(f"\n  ── {ch} Channel ──")
        print(f"  {'Ready Signal':<45} {'Valid':<25} {'Type':<20} {'Condition'[:30]}")
        print(f"  {'-'*45} {'-'*25} {'-'*20} {'-'*30}")
        for hi in by_channel[ch]:
            _print_pair(hi)

    print("")
    # 统计
    stats = {}
    for hi in results:
        t = hi.handshake_type
        stats[t] = stats.get(t, 0) + 1
    print(f"  Summary:")
    for t, cnt in sorted(stats.items(), key=lambda x: -x[1]):
        print(f"    {TYPE_EMOJI.get(t,'❓')} {t}: {cnt}")


# ==============================================================================
# 子命令：scan（扫所有 ready/valid 配对）
# ==============================================================================

@handshake_app.command(name="scan")
def scan(
    file: str = typer.Option(None, "--file", "-f", help="SystemVerilog source file"),
    filelist: str = typer.Option(None, "--filelist", help="Path to filelist (.f/.fl) for multi-file projects"),
    include: str = typer.Option(None, "--include", "-I", help="Include directory (comma-separated)"),
    channel: str = typer.Option(None, "--channel", "-c", help="Filter by bus channel: AW|W|B|AR|R|A|D (comma-separated)"),
    max_signals: int = typer.Option(40, "--max-signals", "-n", help="Max pairs to analyze"),
) -> None:
    """Scan all ready/valid signal pairs and classify handshake semantics"""
    tracer = _build_tracer(filelist, file, include)
    graph = tracer.build_graph()
    st = SignalTracer(graph)
    filter_channels = [c.strip().upper() for c in channel.split(",")] if channel else []

    # 收集候选
    all_nodes = list(graph.nodes())
    bp_nodes = {}
    for node_id in all_nodes:
        parts = node_id.split(".")
        if len(parts) > 2:
            continue
        if _is_ready_or_valid(node_id) and _matches_channel(node_id, filter_channels):
            bp_nodes[node_id] = classify_signal_channel(node_id)

    valid_signals = sorted([n for n in bp_nodes if "valid" in n.lower() or "tvalid" in n.lower()])
    ready_signals = sorted([n for n in bp_nodes if "ready" in n.lower() or "tready" in n.lower()])

    # 配对
    pairs = []
    paired_valid = set()
    for r in ready_signals:
        r_base = _strip_suffix(r)
        for v in valid_signals:
            if v in paired_valid:
                continue
            v_base = _strip_suffix(v)
            if v_base == r_base and v_base:
                pairs.append((v, r))
                paired_valid.add(v)
                break

    results = []
    for valid, ready in pairs[:max_signals]:
        try:
            hi = detect_from_signal_pair(st, valid, ready)
            results.append(hi)
        except Exception:
            pass

    _print_scan_table(results, filter_channels)


# ==============================================================================
# 子命令：analyze（分析单个 ready 信号）
# ==============================================================================

@handshake_app.command(name="analyze")
def analyze(
    file: str = typer.Option(None, "--file", "-f", help="SystemVerilog source file"),
    filelist: str = typer.Option(None, "--filelist", help="Path to filelist for multi-file projects"),
    include: str = typer.Option(None, "--include", "-I", help="Include directory (comma-separated)"),
    signal: str = typer.Option(None, "--signal", "-s", help="Ready signal to analyze (e.g. axi_adapter.s_axi_awready)"),
) -> None:
    """Analyze a single ready signal's handshake semantics"""
    tracer = _build_tracer(filelist, file, include)
    graph = tracer.build_graph()
    st = SignalTracer(graph)

    # 没指定 signal → 默认分析所有 backpressure 类
    if not signal:
        # 复用 scan 逻辑
        scan.callback(
            file=file, filelist=filelist, include=include, channel=None, max_signals=40
        )
        return

    # 指定 signal → 单个分析
    dis = st.trace_fanin_detailed(signal)
    if not dis:
        print(f"  ❌ Signal not found or no driver info: {signal}")
        return

    hi = detect_handshake_type(signal, dis)
    print("")
    print("=" * 80)
    print(f"  Handshake Analysis: {signal}")
    print("=" * 80)
    _print_pair(hi, indent="  ")

    print("")
    print(f"  Channel:        {hi.channel}")
    print(f"  Type:           {hi.handshake_type}  ({TYPE_DESC.get(hi.handshake_type, '')})")
    print(f"  Assign Type:    {hi.assign_type or '-'}")
    print(f"  Clock Domain:   {hi.clock_domain or '-'}")
    print(f"  Condition:      {hi.condition or '-'}")
    print(f"  Effective Cond: {hi.effective_condition or '-'}")
    if hi.extra:
        print(f"  Extra:")
        for k, v in hi.extra.items():
            print(f"    {k}: {v}")
    print("")


# ==============================================================================
# 子命令：pair（分析一对 valid + ready）
# ==============================================================================

@handshake_app.command(name="pair")
def pair(
    file: str = typer.Option(None, "--file", "-f", help="SystemVerilog source file"),
    filelist: str = typer.Option(None, "--filelist", help="Path to filelist for multi-file projects"),
    include: str = typer.Option(None, "--include", "-I", help="Include directory (comma-separated)"),
    valid: str = typer.Option(None, "--valid", help="Valid signal (e.g. axi_adapter.s_axi_awvalid)"),
    ready: str = typer.Option(..., "--ready", help="Ready signal (e.g. axi_adapter.s_axi_awready)"),
) -> None:
    """Analyze a (valid, ready) pair's handshake type"""
    if not valid:
        # 尝试从 signal name 推断
        valid = ready.replace("ready", "valid") if "ready" in ready.lower() else None
        if not valid:
            print("Error: --valid is required (or it can be auto-inferred from --ready if 'ready' is in the name)",
                  file=sys.stderr)
            raise typer.Exit(code=1)

    tracer = _build_tracer(filelist, file, include)
    graph = tracer.build_graph()
    st = SignalTracer(graph)

    hi = detect_from_signal_pair(st, valid, ready)
    print("")
    print("=" * 80)
    print(f"  Handshake Pair: {valid} <-> {ready}")
    print("=" * 80)
    _print_pair(hi, indent="  ")

    print("")
    print(f"  Channel:        {hi.channel}")
    print(f"  Type:           {hi.handshake_type}  ({TYPE_DESC.get(hi.handshake_type, '')})")
    print(f"  Assign Type:    {hi.assign_type or '-'}")
    print(f"  Clock Domain:   {hi.clock_domain or '-'}")
    print(f"  Condition:      {hi.condition or '-'}")
    print(f"  Effective Cond: {hi.effective_condition or '-'}")
    if hi.extra:
        print(f"  Extra:")
        for k, v in hi.extra.items():
            print(f"    {k}: {v}")
    print("")


if __name__ == "__main__":
    handshake_app()
