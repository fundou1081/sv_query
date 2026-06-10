"""
test_protocol_v2_schemas.py
============================
Phase A v2: TL-UL / APB / AHB / Wishbone schema + 检测测试

测试覆盖:
  - 5 个协议全部加载 (AXI4 + TL-UL + APB + AHB + Wishbone)
  - 每个协议的 basic 检测
  - 变体检测 (APB3 vs APB4, AHB vs AHB_LITE, WISHBONE_CLASSIC vs PIPELINED)
  - 真实信号命名风格 (Chisel/SpinalHDL/verilog-axi/verilog-axis)
  - 多协议竞争: TL-UL 不应被误识为 AXI4, APB 不应被误识为 AHB
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

from trace.core.protocol.schema import (
    ProtocolSchemaRegistry,
    load_protocols,
)
from trace.core.protocol.detector import ProtocolDetector
from trace.core.protocol.structural import SignalContext
from trace.core.protocol.handshake_provider import NameBasedHandshakeProvider


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


def make_anchor_pair(name: str):
    """构造 (valid, ready) 配对 helper."""
    return [
        SignalContext(f"{name}_valid", 1, "output", "register", [f"{name}_ready"]),
        SignalContext(f"{name}_ready", 1, "input", "port", [f"{name}_valid"]),
    ]


# ---------------------------------------------------------------------------
# Schema 加载
# ---------------------------------------------------------------------------

class TestAllSchemasLoad:
    def test_load_6_protocols(self, registry):
        """应该加载 6 个协议 (v3+: 加 AXI4-Stream)."""
        assert registry.count == 6
        assert "AXI4" in registry.protocols
        assert "AXI4-Stream" in registry.protocols
        assert "TL-UL" in registry.protocols
        assert "APB" in registry.protocols
        assert "AHB" in registry.protocols
        assert "Wishbone" in registry.protocols

    def test_each_protocol_has_channels(self, registry):
        for proto in ["AXI4", "AXI4-Stream", "TL-UL", "APB", "AHB", "Wishbone"]:
            schema = registry.get(proto)
            assert len(schema.channels) > 0, f"{proto} has no channels"

    def test_each_protocol_has_variants(self, registry):
        for proto in ["AXI4", "AXI4-Stream", "TL-UL", "APB", "AHB", "Wishbone"]:
            schema = registry.get(proto)
            assert len(schema.variants) > 0, f"{proto} has no variants"


# ---------------------------------------------------------------------------
# TL-UL 检测
# ---------------------------------------------------------------------------

def make_tlul_sigs():
    """完整 TL-UL 模块 (host + device)."""
    sigs = []
    # A 通道
    sigs += make_anchor_pair("a")
    sigs += [
        SignalContext("a_opcode", 3, "output", "port", ["a_valid"]),
        SignalContext("a_param", 3, "output", "port", ["a_valid"]),
        SignalContext("a_size", 2, "output", "port", ["a_valid"]),
        SignalContext("a_source", 32, "output", "port", ["a_valid"]),
        SignalContext("a_address", 32, "output", "port", ["a_valid"]),
        SignalContext("a_mask", 4, "output", "port", ["a_valid"]),
        SignalContext("a_data", 32, "output", "port", ["a_valid"]),
    ]
    # D 通道
    sigs += make_anchor_pair("d")
    sigs += [
        SignalContext("d_opcode", 3, "input", "port", ["d_valid"]),
        SignalContext("d_data", 32, "input", "port", ["d_valid"]),
        SignalContext("d_source", 32, "input", "port", ["d_valid"]),
        SignalContext("d_error", 1, "input", "port", ["d_valid"]),
    ]
    return sigs


class TestTLULDetection:
    def test_detect_tlul(self, detector):
        sigs = make_tlul_sigs()
        result = detector.detect(sigs)
        assert result.protocol == "TL-UL", f"expected TL-UL, got {result.protocol}"
        assert result.confidence >= 0.6

    def test_tlul_not_misdetected_as_axi4(self, detector):
        """TL-UL 不应被识为 AXI4."""
        sigs = make_tlul_sigs()
        result = detector.detect(sigs)
        # Top-1 必须是 TL-UL
        assert result.protocol != "AXI4"

    def test_tlul_channels(self, detector):
        """TL-UL 应该有 A 和 D 2 通道."""
        sigs = make_tlul_sigs()
        result = detector.detect(sigs)
        assert "A" in result.channels
        assert "D" in result.channels
        assert result.channels["A"].present
        assert result.channels["D"].present

    def test_tlul_with_o_i_suffix(self, detector):
        """OpenTitan: a_valid_o / a_ready_i / d_valid_i / d_ready_o."""
        sigs = [
            SignalContext("a_valid_o", 1, "output", "register", ["a_ready_i"]),
            SignalContext("a_ready_i", 1, "input", "port", ["a_valid_o"]),
            SignalContext("a_opcode", 3, "output", "port", ["a_valid_o"]),
            SignalContext("a_address", 32, "output", "port", ["a_valid_o"]),
            SignalContext("a_data", 32, "output", "port", ["a_valid_o"]),
            SignalContext("d_valid_i", 1, "input", "port", ["d_ready_o"]),
            SignalContext("d_ready_o", 1, "output", "register", ["d_valid_i"]),
            SignalContext("d_opcode", 3, "input", "port", ["d_valid_i"]),
            SignalContext("d_data", 32, "input", "port", ["d_valid_i"]),
        ]
        result = detector.detect(sigs)
        # _o/_i 后缀被 Session 1 标准化去除
        assert result.protocol == "TL-UL"


# ---------------------------------------------------------------------------
# APB 检测
# ---------------------------------------------------------------------------

def make_apb3_sigs():
    """APB v3 (无 pprot / pstrb)."""
    return [
        SignalContext("psel", 1, "output", "register", ["pready"]),
        SignalContext("penable", 1, "output", "register", ["pready"]),
        SignalContext("pwrite", 1, "output", "register", ["pready"]),
        SignalContext("paddr", 32, "output", "port", ["psel", "penable"]),
        SignalContext("pwdata", 32, "output", "port", ["pwrite"]),
        SignalContext("pready", 1, "input", "port", ["psel", "penable"]),
        SignalContext("prdata", 32, "input", "port", ["pready"]),
    ]


def make_apb4_sigs():
    """APB v4 (有 pprot / pstrb)."""
    sigs = make_apb3_sigs()
    sigs += [
        SignalContext("pprot", 3, "output", "port", ["psel"]),
        SignalContext("pstrb", 4, "output", "port", ["pwdata"]),
    ]
    return sigs


class TestAPBDetection:
    def test_detect_apb3(self, detector):
        sigs = make_apb3_sigs()
        result = detector.detect(sigs)
        assert result.protocol == "APB", f"expected APB, got {result.protocol}"
        assert result.variant == "APB3"
        assert result.confidence >= 0.5

    def test_detect_apb4(self, detector):
        sigs = make_apb4_sigs()
        result = detector.detect(sigs)
        assert result.protocol == "APB"
        assert result.variant == "APB4"
        assert result.confidence >= 0.5

    def test_apb_not_misdetected_as_axi4(self, detector):
        sigs = make_apb3_sigs()
        result = detector.detect(sigs)
        assert result.protocol != "AXI4"

    def test_apb_not_misdetected_as_ahb(self, detector):
        sigs = make_apb3_sigs()
        result = detector.detect(sigs)
        assert result.protocol != "AHB"

    def test_apb_chisel_style(self, detector):
        """Chisel: io_psel / io_penable / io_paddr."""
        sigs = [
            SignalContext("io_psel", 1, "output", "register", ["io_pready"]),
            SignalContext("io_penable", 1, "output", "register", ["io_pready"]),
            SignalContext("io_pwrite", 1, "output", "register", ["io_pready"]),
            SignalContext("io_paddr", 32, "output", "port", ["io_psel"]),
            SignalContext("io_pwdata", 32, "output", "port", ["io_pwrite"]),
            SignalContext("io_pready", 1, "input", "port", ["io_psel"]),
            SignalContext("io_prdata", 32, "input", "port", ["io_pready"]),
        ]
        result = detector.detect(sigs)
        assert result.protocol == "APB"


# ---------------------------------------------------------------------------
# AHB 检测
# ---------------------------------------------------------------------------

def make_ahb_sigs():
    """完整 AHB (含仲裁)."""
    return [
        # Address/Control
        SignalContext("haddr", 32, "output", "port", ["hready"]),
        SignalContext("htrans", 2, "output", "port", ["hready"]),
        SignalContext("hwrite", 1, "output", "port", ["hready"]),
        SignalContext("hsize", 3, "output", "port", ["hready"]),
        SignalContext("hburst", 3, "output", "port", ["hready"]),
        # Data
        SignalContext("hwdata", 32, "output", "port", ["hready"]),
        SignalContext("hrdata", 32, "input", "port", ["hready"]),
        # Response
        SignalContext("hready", 1, "input", "port", ["hready"]),
        SignalContext("hresp", 1, "input", "port", ["hready"]),
        # Arbitration
        SignalContext("hbusreq", 1, "output", "register", ["hgrant"]),
        SignalContext("hgrant", 1, "input", "port", ["hbusreq"]),
    ]


def make_ahb_lite_sigs():
    """AHB-Lite (无仲裁)."""
    sigs = [s for s in make_ahb_sigs() if s.name not in ("hbusreq", "hgrant")]
    return sigs


class TestAHBDetection:
    def test_detect_ahb(self, detector):
        sigs = make_ahb_sigs()
        result = detector.detect(sigs)
        assert result.protocol == "AHB", f"expected AHB, got {result.protocol}"
        assert result.confidence >= 0.5

    def test_detect_ahb_lite(self, detector):
        sigs = make_ahb_lite_sigs()
        result = detector.detect(sigs)
        assert result.protocol == "AHB"
        assert result.variant == "AHB_LITE"

    def test_ahb_not_misdetected_as_axi4(self, detector):
        sigs = make_ahb_sigs()
        result = detector.detect(sigs)
        assert result.protocol != "AXI4"

    def test_ahb_channels(self, detector):
        sigs = make_ahb_sigs()
        result = detector.detect(sigs)
        for ch_name in ["ADDR_CTRL", "DATA_WRITE", "DATA_READ", "RESP", "ARB"]:
            assert ch_name in result.channels


# ---------------------------------------------------------------------------
# Wishbone 检测
# ---------------------------------------------------------------------------

def make_wishbone_classic_sigs():
    """Classic Wishbone."""
    return [
        SignalContext("cyc", 1, "output", "register", ["ack"]),
        SignalContext("stb", 1, "output", "register", ["ack"]),
        SignalContext("we", 1, "output", "port", ["cyc"]),
        SignalContext("adr", 32, "output", "port", ["cyc"]),
        SignalContext("dat_o", 32, "output", "port", ["cyc", "we"]),
        SignalContext("dat_i", 32, "input", "port", ["ack"]),
        SignalContext("ack", 1, "input", "port", ["cyc", "stb"]),
    ]


def make_wishbone_pipelined_sigs():
    """Pipelined Wishbone (有 tag)."""
    sigs = make_wishbone_classic_sigs()
    sigs += [SignalContext("tag", 4, "output", "port", ["cyc"])]
    return sigs


class TestWishboneDetection:
    def test_detect_classic(self, detector):
        sigs = make_wishbone_classic_sigs()
        result = detector.detect(sigs)
        assert result.protocol == "Wishbone", f"expected Wishbone, got {result.protocol}"
        assert result.variant == "WISHBONE_CLASSIC"

    def test_detect_pipelined(self, detector):
        sigs = make_wishbone_pipelined_sigs()
        result = detector.detect(sigs)
        assert result.protocol == "Wishbone"
        assert result.variant == "WISHBONE_PIPELINED"

    def test_wishbone_not_misdetected_as_axi4(self, detector):
        sigs = make_wishbone_classic_sigs()
        result = detector.detect(sigs)
        assert result.protocol != "AXI4"

    def test_wishbone_channels(self, detector):
        sigs = make_wishbone_classic_sigs()
        result = detector.detect(sigs)
        for ch_name in ["CTRL", "ADDR", "DATA_WRITE", "DATA_READ", "RESP"]:
            assert ch_name in result.channels


# ---------------------------------------------------------------------------
# 多协议竞争
# ---------------------------------------------------------------------------

class TestMultiProtocolCompetition:
    """当一个模块有多个协议候选, 应选 top-1 (最高置信度)."""

    def test_tlul_beats_axi4_on_tlul_signals(self, detector):
        sigs = make_tlul_sigs()
        result = detector.detect(sigs)
        # TL-UL 应该战胜 AXI4
        assert result.protocol == "TL-UL"
        # AXI4 也应该有分数 (作为候选), 但低于 TL-UL
        # 因为 TL-UL 信号不会被 AXI4 完全匹配
        assert result.confidence > 0.5

    def test_apb_beats_ahb_on_apb_signals(self, detector):
        sigs = make_apb3_sigs()
        result = detector.detect(sigs)
        # APB 应该战胜 AHB
        assert result.protocol == "APB"

    def test_wishbone_beats_others_on_wb_signals(self, detector):
        sigs = make_wishbone_classic_sigs()
        result = detector.detect(sigs)
        # Wishbone 应该战胜其他
        assert result.protocol == "Wishbone"

    def test_axi4_still_wins_on_axi4_signals(self, detector):
        """在 AXI4 信号下, AXI4 仍应该是 top-1."""
        sigs = [
            SignalContext("awvalid", 1, "output", "register", ["awready"]),
            SignalContext("awready", 1, "input", "port", ["awvalid"]),
            SignalContext("awaddr", 32, "output", "port", ["awvalid"]),
            SignalContext("awlen", 8, "output", "port", ["awvalid"]),
            SignalContext("awsize", 3, "output", "port", ["awvalid"]),
            SignalContext("awburst", 2, "output", "port", ["awvalid"]),
            SignalContext("wvalid", 1, "output", "register", ["wready"]),
            SignalContext("wready", 1, "input", "port", ["wvalid"]),
            SignalContext("wdata", 32, "output", "port", ["wvalid"]),
            SignalContext("wstrb", 4, "output", "port", ["wdata"]),
            SignalContext("wlast", 1, "output", "port", ["wdata"]),
            SignalContext("bvalid", 1, "input", "port", ["bready"]),
            SignalContext("bready", 1, "output", "register", ["bvalid"]),
            SignalContext("bresp", 2, "input", "port", ["bvalid"]),
            SignalContext("arvalid", 1, "output", "register", ["arready"]),
            SignalContext("arready", 1, "input", "port", ["arvalid"]),
            SignalContext("araddr", 32, "output", "port", ["arvalid"]),
            SignalContext("rvalid", 1, "input", "port", ["rready"]),
            SignalContext("rready", 1, "output", "register", ["rvalid"]),
            SignalContext("rdata", 32, "input", "port", ["rvalid"]),
        ]
        result = detector.detect(sigs)
        assert result.protocol == "AXI4"
        assert result.variant == "AXI4_FULL"


# ---------------------------------------------------------------------------
# 置信度质量
# ---------------------------------------------------------------------------

class TestConfidenceQuality:
    """每个协议真实信号应达到合理置信度 (>= 0.6)."""

    @pytest.mark.parametrize("sigs_fn,proto,variant,min_conf", [
        (make_tlul_sigs, "TL-UL", "TL-UL", 0.6),
        (make_apb3_sigs, "APB", "APB3", 0.5),
        (make_apb4_sigs, "APB", "APB4", 0.5),
        (make_ahb_sigs, "AHB", "AHB", 0.5),
        (make_ahb_lite_sigs, "AHB", "AHB_LITE", 0.4),
        (make_wishbone_classic_sigs, "Wishbone", "WISHBONE_CLASSIC", 0.4),
        (make_wishbone_pipelined_sigs, "Wishbone", "WISHBONE_PIPELINED", 0.4),
    ])
    def test_confidence_above_threshold(self, detector, sigs_fn, proto, variant, min_conf):
        sigs = sigs_fn()
        result = detector.detect(sigs)
        assert result.protocol == proto, f"expected {proto}, got {result.protocol}"
        if variant:
            assert result.variant == variant
        assert result.confidence >= min_conf, f"{proto} confidence too low: {result.confidence}"
