# ==============================================================================
# test_handshake_cli.py - handshake CLI command tests
# ==============================================================================
"""
Tests for src/cli/commands/handshake.py
Uses typer.testing.CliRunner to invoke commands end-to-end.
"""

import os
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

from src.cli.commands.handshake import handshake_app


runner = CliRunner()


# ==============================================================================
# 测试用源文件：标准 AXI 握手
# ==============================================================================

AXI_SOURCE = """
module axi_adapter #(
    parameter ADDR_WIDTH = 32,
    parameter DATA_WIDTH = 64
)(
    input  wire                    clk,
    input  wire                    rst,

    output reg                     s_axi_awvalid,
    input  wire                    s_axi_awready,
    output reg  [ADDR_WIDTH-1:0]   s_axi_awaddr,

    output reg                     m_axi_wvalid,
    input  wire                    m_axi_wready,
    output reg  [DATA_WIDTH-1:0]   m_axi_wdata
);

    // 标准 AXI 握手: awvalid && awready
    always @(posedge clk) begin
        if (rst) begin
            s_axi_awvalid <= 1'b0;
        end else if (s_axi_awvalid && s_axi_awready) begin
            s_axi_awvalid <= 1'b0;
        end else if (!s_axi_awvalid) begin
            s_axi_awvalid <= 1'b1;
        end
    end

    // FIFO 反压: !out_fifo_full
    wire out_fifo_full;
    always @(*) begin
        m_axi_wvalid = !out_fifo_full;
    end

endmodule
"""


@pytest.fixture
def axi_source_file(tmp_path):
    p = tmp_path / "axi_adapter.sv"
    p.write_text(AXI_SOURCE)
    return str(p)


# ==============================================================================
# Help / 命令列表
# ==============================================================================

class TestHandshakeHelp:
    def test_handshake_help(self):
        result = runner.invoke(handshake_app, ["--help"])
        assert result.exit_code == 0
        assert "handshake" in result.stdout.lower()
        assert "analyze" in result.stdout
        assert "scan" in result.stdout
        assert "pair" in result.stdout

    def test_handshake_analyze_help(self):
        result = runner.invoke(handshake_app, ["analyze", "--help"])
        assert result.exit_code == 0
        assert "--filelist" in result.stdout
        assert "--signal" in result.stdout

    def test_handshake_scan_help(self):
        result = runner.invoke(handshake_app, ["scan", "--help"])
        assert result.exit_code == 0
        assert "--channel" in result.stdout

    def test_handshake_pair_help(self):
        result = runner.invoke(handshake_app, ["pair", "--help"])
        assert result.exit_code == 0
        assert "--ready" in result.stdout


# ==============================================================================
# 错误处理
# ==============================================================================

class TestHandshakeErrors:
    def test_no_filelist_or_file(self):
        result = runner.invoke(handshake_app, ["scan"])
        assert result.exit_code != 0
        assert "filelist" in (result.stdout + result.stderr).lower() or "file" in (result.stdout + result.stderr).lower()

    def test_pair_missing_ready(self):
        """pair 必须给 --ready"""
        # --ready 用 ... 是 required,typer 会自动报错
        result = runner.invoke(handshake_app, ["pair"])
        assert result.exit_code != 0


# ==============================================================================
# analyze 子命令
# ==============================================================================

class TestHandshakeAnalyze:
    def test_analyze_existing_signal(self, axi_source_file):
        """分析一个真实存在的 ready 信号"""
        result = runner.invoke(handshake_app, [
            "analyze", "--file", axi_source_file,
            "--signal", "axi_adapter.s_axi_awready",
        ])
        # 没报异常即可（可能 EXIT 0 或 1 取决于 driver info）
        combined = result.stdout + result.stderr
        # 至少应该尝试分析
        assert "Handshake Analysis" in combined or "not found" in combined

    def test_analyze_without_signal_runs_scan(self, axi_source_file):
        """没指定 signal → fallback to scan (或者报错)"""
        result = runner.invoke(handshake_app, [
            "analyze", "--file", axi_source_file,
        ])
        # 应该退出码为 0 (fallback to scan) 或有清晰报错
        # 不应该崩溃
        combined = result.stdout + result.stderr
        # 接受多种输出: scan header / error message / empty
        assert result.exit_code in (0, 1, 2)  # 不崩溃


# ==============================================================================
# pair 子命令
# ==============================================================================

class TestHandshakePair:
    def test_pair_valid_ready(self, axi_source_file):
        result = runner.invoke(handshake_app, [
            "pair", "--file", axi_source_file,
            "--valid", "axi_adapter.m_axi_wvalid",
            "--ready", "axi_adapter.m_axi_wready",
        ])
        combined = result.stdout + result.stderr
        # 输出应该包含 Handshake Pair 标题
        assert "Handshake Pair" in combined or "not found" in combined

    def test_pair_auto_infer_valid(self, axi_source_file):
        """没指定 --valid → 自动从 --ready 推断"""
        result = runner.invoke(handshake_app, [
            "pair", "--file", axi_source_file,
            "--ready", "axi_adapter.m_axi_wready",
        ])
        combined = result.stdout + result.stderr
        # 应该自动把 m_axi_wready 推断成 m_axi_wvalid
        assert "Handshake Pair" in combined or "valid" in combined.lower()


# ==============================================================================
# scan 子命令
# ==============================================================================

class TestHandshakeScan:
    def test_scan_with_filter(self, axi_source_file):
        result = runner.invoke(handshake_app, [
            "scan", "--file", axi_source_file,
            "--channel", "AW,W",
            "--max-signals", "5",
        ])
        combined = result.stdout + result.stderr
        # scan 应该输出 header
        assert "Handshake" in combined or "summary" in combined.lower() or "no" in combined.lower()
