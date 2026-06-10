"""
test_protocol_axistream.py
============================
Phase A: AXI4-Stream 协议检测

测试覆盖:
  - 完整 AXI4-Stream (tvalid/tready/tdata + tlast/tkeep/tid/tdest/tuser)
  - AXI4-Stream Lite (无 tlast/tkeep/tid/tdest/tuser)
  - AXI4-Stream Packet (必有 tlast)
  - Chisel/SpinalHDL 风格 (io_axis_*)
  - verilog-axi 风格 (s_axis_*/m_axis_*) — 真实项目风格
  - 多协议竞争: AXI4-Stream 不被误识为 AXI4
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

from applications.bus.schema import (
    ProtocolSchemaRegistry,
    load_protocols,
)
from applications.bus.detector import ProtocolDetector
from applications.bus.structural import SignalContext
from applications.bus.handshake_provider import NameBasedHandshakeProvider


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def registry() -> ProtocolSchemaRegistry:
    return ProtocolSchemaRegistry.from_directory("config/protocols")


@pytest.fixture
def detector(registry) -> ProtocolDetector:
    return ProtocolDetector(
        registry=registry,
        handshake_provider=NameBasedHandshakeProvider(),
    )


# ---------------------------------------------------------------------------
# Signal 构造 helper
# ---------------------------------------------------------------------------

def make_axis_sigs(prefix: str = "", include_lite: bool = False) -> list:
    """构造 AXI4-Stream 信号 (master 视角: tvalid/tlast out, tready in, tdata out)."""
    sigs = [
        SignalContext(f"{prefix}tvalid", 1, "output", "register",
                      [f"{prefix}tready"]),
        SignalContext(f"{prefix}tready", 1, "input", "port",
                      [f"{prefix}tvalid"]),
        SignalContext(f"{prefix}tdata", 32, "output", "port",
                      [f"{prefix}tvalid", f"{prefix}tlast", f"{prefix}tkeep"]),
    ]
    if not include_lite:
        sigs += [
            SignalContext(f"{prefix}tlast", 1, "output", "port",
                          [f"{prefix}tdata"]),
            SignalContext(f"{prefix}tkeep", 4, "output", "port",
                          [f"{prefix}tdata"]),
        ]
    return sigs


def make_axis_with_meta(prefix: str = "") -> list:
    """完整 AXI4-Stream (含 tid/tdest/tuser)."""
    sigs = make_axis_sigs(prefix)
    sigs += [
        SignalContext(f"{prefix}tid", 8, "output", "port",
                      [f"{prefix}tvalid"]),
        SignalContext(f"{prefix}tdest", 4, "output", "port",
                      [f"{prefix}tvalid"]),
        SignalContext(f"{prefix}tuser", 8, "output", "port",
                      [f"{prefix}tvalid"]),
    ]
    return sigs


# ---------------------------------------------------------------------------
# Schema 加载
# ---------------------------------------------------------------------------

class TestAXIStreamSchema:
    def test_load_default(self, registry):
        assert "AXI4-Stream" in registry.protocols

    def test_channels(self, registry):
        schema = registry.get("AXI4-Stream")
        assert "HANDSHAKE" in schema.channels
        assert "DATA" in schema.channels
        assert "PACKET" in schema.channels
        assert "STROBE" in schema.channels
        assert "META" in schema.channels

    def test_signal_roles(self, registry):
        schema = registry.get("AXI4-Stream")
        assert "tvalid" in schema.signal_roles
        assert "tready" in schema.signal_roles
        assert "tdata" in schema.signal_roles
        assert "tlast" in schema.signal_roles
        assert schema.signal_roles["tvalid"].role == "valid"

    def test_variants(self, registry):
        schema = registry.get("AXI4-Stream")
        names = {v.name for v in schema.variants}
        assert "AXI4_STREAM" in names
        assert "AXI4_STREAM_LITE" in names
        assert "AXI4_STREAM_PACKET" in names


# ---------------------------------------------------------------------------
# 基本检测
# ---------------------------------------------------------------------------

class TestBasicDetection:
    def test_detect_full(self, detector):
        sigs = make_axis_sigs()
        result = detector.detect(sigs)
        assert result.protocol == "AXI4-Stream"
        assert result.confidence >= 0.5

    def test_detect_with_meta(self, detector):
        """含 tid/tdest/tuser 也应正确检测."""
        sigs = make_axis_with_meta()
        result = detector.detect(sigs)
        assert result.protocol == "AXI4-Stream"
        assert result.confidence >= 0.6

    def test_detect_lite(self, detector):
        """Lite (无 tlast/tkeep/tid/tdest/tuser) 也应正确检测."""
        sigs = make_axis_sigs(include_lite=True)
        result = detector.detect(sigs)
        assert result.protocol == "AXI4-Stream"
        assert result.variant == "AXI4_STREAM_LITE"

    def test_detect_packet(self, detector):
        """Packet (必有 tlast) 也应正确检测."""
        sigs = make_axis_sigs()  # 默认含 tlast
        result = detector.detect(sigs)
        # 完整版本有 tlast, 应该被识别为 PACKET (有 tlast) 而不是 LITE
        assert result.variant in ("AXI4_STREAM", "AXI4_STREAM_PACKET")

    def test_channels_present(self, detector):
        sigs = make_axis_sigs()
        result = detector.detect(sigs)
        for ch_name in ["HANDSHAKE", "DATA"]:
            assert ch_name in result.channels
            assert result.channels[ch_name].present


# ---------------------------------------------------------------------------
# 命名风格兼容
# ---------------------------------------------------------------------------

class TestNamingStyles:
    def test_chisel_style(self, detector):
        """Chisel: io_axis_tvalid / io_axis_tready / io_axis_tdata."""
        sigs = [
            SignalContext("io_axis_tvalid", 1, "output", "register",
                          ["io_axis_tready"]),
            SignalContext("io_axis_tready", 1, "input", "port",
                          ["io_axis_tvalid"]),
            SignalContext("io_axis_tdata", 32, "output", "port",
                          ["io_axis_tvalid"]),
            SignalContext("io_axis_tlast", 1, "output", "port",
                          ["io_axis_tdata"]),
        ]
        result = detector.detect(sigs)
        assert result.protocol == "AXI4-Stream"

    def test_verilog_axi_style(self, detector):
        """verilog-axi: s_axis_tvalid / s_axis_tready / s_axis_tdata (slave 视角)."""
        sigs = [
            SignalContext("s_axis_tvalid", 1, "input", "port",
                          ["s_axis_tready"]),
            SignalContext("s_axis_tready", 1, "output", "register",
                          ["s_axis_tvalid"]),
            SignalContext("s_axis_tdata", 32, "input", "port",
                          ["s_axis_tvalid"]),
            SignalContext("s_axis_tlast", 1, "input", "port",
                          ["s_axis_tdata"]),
            SignalContext("s_axis_tkeep", 4, "input", "port",
                          ["s_axis_tdata"]),
        ]
        result = detector.detect(sigs)
        assert result.protocol == "AXI4-Stream"

    def test_mixed_master_slave(self, detector):
        """verilog-axi master 视角: m_axis_*."""
        sigs = [
            SignalContext("m_axis_tvalid", 1, "output", "register",
                          ["m_axis_tready"]),
            SignalContext("m_axis_tready", 1, "input", "port",
                          ["m_axis_tvalid"]),
            SignalContext("m_axis_tdata", 64, "output", "port",
                          ["m_axis_tvalid", "m_axis_tlast", "m_axis_tkeep"]),
            SignalContext("m_axis_tlast", 1, "output", "port", ["m_axis_tdata"]),
            SignalContext("m_axis_tkeep", 8, "output", "port", ["m_axis_tdata"]),
            SignalContext("m_axis_tid", 8, "output", "port", ["m_axis_tvalid"]),
            SignalContext("m_axis_tdest", 4, "output", "port", ["m_axis_tvalid"]),
        ]
        result = detector.detect(sigs)
        assert result.protocol == "AXI4-Stream"
        assert result.confidence >= 0.5


# ---------------------------------------------------------------------------
# 多协议竞争
# ---------------------------------------------------------------------------

class TestMultiProtocolCompetition:
    def test_not_misdetected_as_axi4(self, detector):
        """AXI4-Stream 不应被误识为 AXI4 (有 awaddr/awvalid 等会混淆)."""
        sigs = make_axis_sigs()
        result = detector.detect(sigs)
        # Top-1 必须是 AXI4-Stream
        assert result.protocol == "AXI4-Stream"
        assert result.protocol != "AXI4"

    def test_axi4_still_wins_on_axi4_signals(self, detector):
        """AXI4 仍能在 AXI4 信号下正确识别."""
        sigs = [
            SignalContext("awvalid", 1, "output", "register", ["awready"]),
            SignalContext("awready", 1, "input", "port", ["awvalid"]),
            SignalContext("awaddr", 32, "output", "port", ["awvalid"]),
            SignalContext("wvalid", 1, "output", "register", ["wready"]),
            SignalContext("wready", 1, "input", "port", ["wvalid"]),
            SignalContext("wdata", 32, "output", "port", ["wvalid"]),
        ]
        result = detector.detect(sigs)
        assert result.protocol == "AXI4"

    def test_priority_over_ahb_on_tvalid_tready(self, detector):
        """tvalid/tready 不应被 AHB 抢去 (AHB 配对是 hready/hresp)."""
        sigs = make_axis_sigs()
        result = detector.detect(sigs)
        # top-1 应该是 AXI4-Stream
        assert result.protocol == "AXI4-Stream"


# ---------------------------------------------------------------------------
# 变体检测
# ---------------------------------------------------------------------------

class TestVariantDetection:
    def test_lite_variant(self, detector):
        sigs = make_axis_sigs(include_lite=True)
        result = detector.detect(sigs)
        # 无 tlast/tkeep/tstrb/tid/tdest/tuser → LITE
        assert result.variant == "AXI4_STREAM_LITE"

    def test_full_variant(self, detector):
        """完整 + meta → 可能是 STREAM (default) 或 PACKET."""
        sigs = make_axis_with_meta()
        result = detector.detect(sigs)
        # 有 tlast → 不是 LITE
        assert result.variant != "AXI4_STREAM_LITE"


# ---------------------------------------------------------------------------
# 真实项目回归 (verilog-axi)
# ---------------------------------------------------------------------------

class TestRealVerilogAXI:
    """模拟 verilog-axi axi_vfifo_enc/dec 内部信号."""

    def test_s_axis_signals(self, detector):
        """Slave 视角: s_axis_tdata/tvalid/tready/tlast/tkeep/tid/tdest/tuser."""
        sigs = [
            SignalContext("s_axis_tdata", 64, "input", "port", ["s_axis_tvalid"]),
            SignalContext("s_axis_tkeep", 8, "input", "port", ["s_axis_tdata"]),
            SignalContext("s_axis_tvalid", 1, "input", "port", ["s_axis_tready"]),
            SignalContext("s_axis_tready", 1, "output", "register", ["s_axis_tvalid"]),
            SignalContext("s_axis_tlast", 1, "input", "port", ["s_axis_tdata"]),
            SignalContext("s_axis_tid", 8, "input", "port", ["s_axis_tvalid"]),
            SignalContext("s_axis_tdest", 4, "input", "port", ["s_axis_tvalid"]),
            SignalContext("s_axis_tuser", 1, "input", "port", ["s_axis_tvalid"]),
        ]
        result = detector.detect(sigs)
        assert result.protocol == "AXI4-Stream"
        assert result.confidence >= 0.5
