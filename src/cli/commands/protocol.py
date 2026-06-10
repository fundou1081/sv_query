# ==============================================================================
# protocol.py - 协议检测 CLI (Phase A Session 4)
# ==============================================================================
"""
Usage:
  python run_cli.py protocol detect --file <sv> [--module <name>]
  python run_cli.py protocol detect --filelist <fl>
  python run_cli.py protocol show AXI4
  python run_cli.py protocol list

Detects bus protocol (AXI4 / AXI4-Lite / AXI4-Stream / ...) in SystemVerilog
modules via 4-source confidence fusion:
  - name (0.30)        : 标准化后名字 vs schema.signal_roles
  - structural (0.30)  : 宽度 + 方向 + 配对 → 角色
  - pattern (0.25)     : 锚点 + 通道分组
  - handshake (0.15)   : Phase B 握手分类 (TODO)
"""

import sys
from pathlib import Path
from typing import List, Optional

import typer

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from trace.core.protocol.schema import (
    ProtocolSchemaRegistry,
    load_protocols,
)
from trace.core.protocol.detector import (
    ProtocolDetector,
    ProtocolMatch,
)
from trace.core.protocol.structural import SignalContext


protocol_app = typer.Typer(help="Bus protocol detection (Phase A)")


# ---------------------------------------------------------------------------
# 顶层 detect 命令
# ---------------------------------------------------------------------------

@protocol_app.command(name="detect")
def detect(
    file: str = typer.Option(None, "--file", "-f", help="SystemVerilog source file"),
    filelist: str = typer.Option(None, "--filelist", help="Path to filelist (.f/.fl) for multi-file projects"),
    module: str = typer.Option(None, "--module", "-m", help="Specific module to analyze"),
    schemas: str = typer.Option(
        "config/protocols",
        "--schemas",
        help="Path to protocol YAML directory",
    ),
    json_output: bool = typer.Option(
        False, "--json", help="Output as JSON instead of text"
    ),
):
    """检测模块的 bus 协议.

    默认用本地 mock SignalContext (避免 SV 编译依赖).
    完整 SV 集成等 Phase B 完成.
    """
    if not file and not filelist:
        typer.echo("Error: need --file or --filelist", err=True)
        raise typer.Exit(1)

    target = file or filelist
    typer.echo(f"Analyzing: {target}")
    if module:
        typer.echo(f"  Module: {module}")

    # 加载 schema
    reg = ProtocolSchemaRegistry.from_directory(schemas)
    if reg.count == 0:
        typer.echo(f"Error: no protocol schemas found in {schemas}", err=True)
        raise typer.Exit(1)

    # Mock signals (真实集成需要 SV 编译)
    sigs = _mock_extract_signals(target, module)

    if not sigs:
        typer.echo("No signals extracted (Phase B SV integration not yet wired)", err=True)
        typer.echo("Falling back to mock test data for protocol detector demo...")
        sigs = _get_demo_signals(target)

    if not sigs:
        typer.echo("No signals to analyze", err=True)
        raise typer.Exit(1)

    # 检测
    detector = ProtocolDetector(registry=reg)
    match = detector.detect(sigs)

    # 输出
    if json_output:
        import json
        result = {
            "protocol": match.protocol,
            "variant": match.variant,
            "confidence": match.confidence,
            "scores": {
                "name": match.name_score,
                "structural": match.structural_score,
                "pattern": match.pattern_score,
                "handshake": match.handshake_score,
            },
            "channels": {
                ch_name: {
                    "present": ch.present,
                    "score": ch.score,
                    "matched_required": ch.matched_required,
                    "matched_optional": ch.matched_optional,
                    "missing_required": ch.missing_required,
                }
                for ch_name, ch in match.channels.items()
            },
            "warnings": match.warnings,
        }
        typer.echo(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        _print_text_result(match)


@protocol_app.command(name="show")
def show(
    protocol: str = typer.Argument(..., help="Protocol name (e.g., AXI4)"),
    schemas: str = typer.Option(
        "config/protocols", "--schemas", help="Path to protocol YAML directory"
    ),
):
    """显示协议 schema 详情."""
    reg = ProtocolSchemaRegistry.from_directory(schemas)
    schema = reg.get(protocol)
    if schema is None:
        typer.echo(f"Protocol not found: {protocol}", err=True)
        typer.echo(f"Available: {reg.list_protocols()}", err=True)
        raise typer.Exit(1)

    typer.echo(f"Protocol: {schema.protocol}")
    typer.echo(f"Description: {schema.description}")
    typer.echo(f"\nChannels ({len(schema.channels)}):")
    for ch_name, ch in schema.channels.items():
        typer.echo(f"  {ch_name}: required={ch.required_count()}, optional={len(ch.optional)}")
        if ch.required:
            typer.echo(f"    required: {ch.required}")
        if ch.optional:
            typer.echo(f"    optional: {ch.optional[:3]}{'...' if len(ch.optional) > 3 else ''}")

    typer.echo(f"\nVariants ({len(schema.variants)}):")
    for v in schema.variants:
        typer.echo(f"  - {v.name}: {v.description}")
        if v.needs_signals:
            typer.echo(f"      needs: {v.needs_signals}")
        if v.needs_absent_signals:
            typer.echo(f"      absent: {v.needs_absent_signals}")


@protocol_app.command(name="list")
def list_protocols(
    schemas: str = typer.Option(
        "config/protocols", "--schemas", help="Path to protocol YAML directory"
    ),
):
    """列出所有可用协议."""
    reg = ProtocolSchemaRegistry.from_directory(schemas)
    typer.echo(f"Available protocols ({reg.count}):")
    for name in reg.list_protocols():
        schema = reg.get(name)
        typer.echo(f"  {name}: {schema.description}")


# ---------------------------------------------------------------------------
# 输出
# ---------------------------------------------------------------------------

def _print_text_result(match: ProtocolMatch):
    """文本格式输出."""
    typer.echo(f"\nDetected: {match.protocol}", nl=False)
    if match.variant:
        typer.echo(f" ({match.variant})", nl=False)
    typer.echo(f"  confidence: {match.confidence:.3f}")

    if match.confidence < 0.5:
        typer.echo("  (LOW CONFIDENCE — may be unknown protocol)")

    typer.echo(f"\n  Score breakdown:")
    typer.echo(f"    name:        {match.name_score:.3f}")
    typer.echo(f"    structural:  {match.structural_score:.3f}")
    typer.echo(f"    pattern:     {match.pattern_score:.3f}")
    typer.echo(f"    handshake:   {match.handshake_score:.3f}")

    typer.echo(f"\n  Channels:")
    for ch_name, ch in match.channels.items():
        marker = "✓" if ch.present else "✗"
        typer.echo(f"    {marker} {ch_name:<3} {ch.score:.3f}  "
                   f"req={ch.name_score:.2f} struct={ch.structural_score:.2f} pat={ch.pattern_score:.2f}")
        if ch.matched_required:
            typer.echo(f"        required: {ch.matched_required}")
        if ch.matched_optional:
            opt_short = ch.matched_optional[:5]
            more = f" (+{len(ch.matched_optional)-5})" if len(ch.matched_optional) > 5 else ""
            typer.echo(f"        optional: {opt_short}{more}")
        if ch.missing_required:
            typer.echo(f"        MISSING:  {ch.missing_required}")

    if match.warnings:
        typer.echo(f"\n  Warnings:")
        for w in match.warnings:
            typer.echo(f"    - {w}")


# ---------------------------------------------------------------------------
# Mock 数据 (Phase B 集成后移除)
# ---------------------------------------------------------------------------

def _mock_extract_signals(target: str, module: Optional[str]) -> List[SignalContext]:
    """Mock: 暂时不接 SV 编译, 返回空. Phase B 集成."""
    return []


def _get_demo_signals(target: str) -> List[SignalContext]:
    """Demo 数据: 用于在没有 SV 编译时演示检测器."""
    # 启发式: 文件名包含 "lite" → LITE, 否则 FULL
    if "lite" in target.lower():
        return [
            SignalContext("awvalid", 1, "output", "register", ["awready"]),
            SignalContext("awready", 1, "input", "port", ["awvalid"]),
            SignalContext("awaddr", 32, "output", "port", ["awvalid"]),
            SignalContext("wvalid", 1, "output", "register", ["wready"]),
            SignalContext("wready", 1, "input", "port", ["wvalid"]),
            SignalContext("wdata", 32, "output", "port", ["wvalid"]),
            SignalContext("bvalid", 1, "input", "port", ["bready"]),
            SignalContext("bready", 1, "output", "register", ["bvalid"]),
            SignalContext("bresp", 2, "input", "port", ["bvalid"]),
            SignalContext("arvalid", 1, "output", "register", ["arready"]),
            SignalContext("arready", 1, "input", "port", ["arvalid"]),
            SignalContext("araddr", 32, "output", "port", ["arvalid"]),
            SignalContext("rvalid", 1, "input", "port", ["rready"]),
            SignalContext("rready", 1, "output", "register", ["rvalid"]),
            SignalContext("rdata", 32, "input", "port", ["rvalid"]),
            SignalContext("rresp", 2, "input", "port", ["rvalid"]),
        ]
    else:
        return [
            SignalContext("awvalid", 1, "output", "register", ["awready"]),
            SignalContext("awready", 1, "input", "port", ["awvalid"]),
            SignalContext("awaddr", 32, "output", "port", ["awvalid"]),
            SignalContext("awlen", 8, "output", "port", ["awvalid"]),
            SignalContext("awsize", 3, "output", "port", ["awvalid"]),
            SignalContext("awburst", 2, "output", "port", ["awvalid"]),
            SignalContext("wvalid", 1, "output", "register", ["wready"]),
            SignalContext("wready", 1, "input", "port", ["wvalid"]),
            SignalContext("wdata", 32, "output", "port", ["wvalid", "wstrb", "wlast"]),
            SignalContext("wstrb", 4, "output", "port", ["wdata"]),
            SignalContext("wlast", 1, "output", "port", ["wdata"]),
            SignalContext("bvalid", 1, "input", "port", ["bready"]),
            SignalContext("bready", 1, "output", "register", ["bvalid"]),
            SignalContext("bresp", 2, "input", "port", ["bvalid"]),
            SignalContext("arvalid", 1, "output", "register", ["arready"]),
            SignalContext("arready", 1, "input", "port", ["arvalid"]),
            SignalContext("araddr", 32, "output", "port", ["arvalid"]),
            SignalContext("arlen", 8, "output", "port", ["arvalid"]),
            SignalContext("arsize", 3, "output", "port", ["arvalid"]),
            SignalContext("arburst", 2, "output", "port", ["arvalid"]),
            SignalContext("rvalid", 1, "input", "port", ["rready"]),
            SignalContext("rready", 1, "output", "register", ["rvalid"]),
            SignalContext("rdata", 32, "input", "port", ["rvalid"]),
            SignalContext("rresp", 2, "input", "port", ["rvalid"]),
            SignalContext("rlast", 1, "input", "port", ["rvalid"]),
        ]


# ===========================================================================
# CLI 入口
# ===========================================================================

def main():
    protocol_app()


if __name__ == "__main__":
    main()
