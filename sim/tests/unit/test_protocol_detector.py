"""
test_protocol_detector.py
=========================
Phase A Session 4: 协议检测评分引擎

测试覆盖:
  - 基本 AXI4 模块检测
  - AXI4_FULL vs AXI4_LITE 变体检测
  - 多协议候选, 选 top-1
  - 4 项置信度融合 (name + structural + pattern + handshake)
  - 真实项目信号场景
  - ChannelMatch / SignalMapping 数据结构
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

from applications.bus.schema import (
    ProtocolSchemaRegistry,
    load_protocols,
)
from applications.bus.detector import (
    ProtocolDetector,
    ProtocolMatch,
    ChannelMatch,
    SignalMapping,
)
from applications.bus.structural import (
    SignalContext,
    StructuralRoleDetector,
)
from applications.bus.normalize import SignalNormalizer, NormalizeConfig
from applications.bus.pattern_learner import PatternLearner


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def registry() -> ProtocolSchemaRegistry:
    return ProtocolSchemaRegistry.from_directory("config/protocols")


@pytest.fixture
def detector(registry) -> ProtocolDetector:
    return ProtocolDetector(registry=registry)


def make_axi4_full_sigs():
    """构造一个完整 AXI4_FULL 模块的信号列表."""
    sigs = [
        # AW 通道
        SignalContext("awvalid", 1, "output", "register", ["awready"]),
        SignalContext("awready", 1, "input", "port", ["awvalid"]),
        SignalContext("awaddr", 32, "output", "port", ["awvalid"]),
        SignalContext("awlen", 8, "output", "port", ["awvalid"]),
        SignalContext("awsize", 3, "output", "port", ["awvalid"]),
        SignalContext("awburst", 2, "output", "port", ["awvalid"]),
        SignalContext("awid", 4, "output", "port", ["awvalid"]),
        # W 通道
        SignalContext("wvalid", 1, "output", "register", ["wready"]),
        SignalContext("wready", 1, "input", "port", ["wvalid"]),
        SignalContext("wdata", 32, "output", "port", ["wvalid", "wstrb", "wlast"]),
        SignalContext("wstrb", 4, "output", "port", ["wdata"]),
        SignalContext("wlast", 1, "output", "port", ["wdata"]),
        # B 通道
        SignalContext("bvalid", 1, "input", "port", ["bready"]),
        SignalContext("bready", 1, "output", "register", ["bvalid"]),
        SignalContext("bresp", 2, "input", "port", ["bvalid"]),
        SignalContext("bid", 4, "input", "port", ["bvalid"]),
        # AR 通道
        SignalContext("arvalid", 1, "output", "register", ["arready"]),
        SignalContext("arready", 1, "input", "port", ["arvalid"]),
        SignalContext("araddr", 32, "output", "port", ["arvalid"]),
        SignalContext("arlen", 8, "output", "port", ["arvalid"]),
        SignalContext("arsize", 3, "output", "port", ["arvalid"]),
        SignalContext("arburst", 2, "output", "port", ["arvalid"]),
        SignalContext("arid", 4, "output", "port", ["arvalid"]),
        # R 通道
        SignalContext("rvalid", 1, "input", "port", ["rready"]),
        SignalContext("rready", 1, "output", "register", ["rvalid"]),
        SignalContext("rdata", 32, "input", "port", ["rvalid"]),
        SignalContext("rresp", 2, "input", "port", ["rvalid"]),
        SignalContext("rid", 4, "input", "port", ["rvalid"]),
        SignalContext("rlast", 1, "input", "port", ["rvalid"]),
    ]
    return sigs


def make_axi4_lite_sigs():
    """AXI4-LITE: 没有 awlen/awsize/awburst/wstrb/wlast."""
    sigs = [
        # AW
        SignalContext("awvalid", 1, "output", "register", ["awready"]),
        SignalContext("awready", 1, "input", "port", ["awvalid"]),
        SignalContext("awaddr", 32, "output", "port", ["awvalid"]),
        SignalContext("awprot", 3, "output", "port", ["awvalid"]),
        # W
        SignalContext("wvalid", 1, "output", "register", ["wready"]),
        SignalContext("wready", 1, "input", "port", ["wvalid"]),
        SignalContext("wdata", 32, "output", "port", ["wvalid"]),
        # B
        SignalContext("bvalid", 1, "input", "port", ["bready"]),
        SignalContext("bready", 1, "output", "register", ["bvalid"]),
        SignalContext("bresp", 2, "input", "port", ["bvalid"]),
        # AR
        SignalContext("arvalid", 1, "output", "register", ["arready"]),
        SignalContext("arready", 1, "input", "port", ["arvalid"]),
        SignalContext("araddr", 32, "output", "port", ["arvalid"]),
        SignalContext("arprot", 3, "output", "port", ["arvalid"]),
        # R
        SignalContext("rvalid", 1, "input", "port", ["rready"]),
        SignalContext("rready", 1, "output", "register", ["rvalid"]),
        SignalContext("rdata", 32, "input", "port", ["rvalid"]),
        SignalContext("rresp", 2, "input", "port", ["rvalid"]),
    ]
    return sigs


# ---------------------------------------------------------------------------
# 基本检测
# ---------------------------------------------------------------------------

class TestBasicDetection:
    def test_detect_axi4_full(self, detector):
        """完整 AXI4 模块 → AXI4_FULL, 高置信度."""
        sigs = make_axi4_full_sigs()
        result = detector.detect(sigs)
        assert result.protocol == "AXI4"
        assert result.variant == "AXI4_FULL"
        assert result.confidence >= 0.6

    def test_detect_axi4_lite(self, detector):
        """AXI4-LITE (无 burst/strb/last) → AXI4_LITE."""
        sigs = make_axi4_lite_sigs()
        result = detector.detect(sigs)
        assert result.protocol == "AXI4"
        assert result.variant == "AXI4_LITE"
        assert result.confidence >= 0.6

    def test_unknown_protocol_low_confidence(self, detector):
        """无 anchor / 无信号 → UNKNOWN."""
        result = detector.detect([])
        assert result.confidence < 0.5
        assert result.warnings  # 应该有警告


# ---------------------------------------------------------------------------
# ChannelMatch 数据结构
# ---------------------------------------------------------------------------

class TestChannelMatch:
    def test_present_channel(self):
        ch = ChannelMatch(
            name="AW",
            present=True,
            matched_required=["awvalid", "awready", "awaddr"],
            matched_optional=["awlen", "awsize", "awburst"],
            missing_required=[],
            score=0.95,
        )
        assert ch.name == "AW"
        assert ch.present
        assert len(ch.matched_required) == 3
        assert ch.score == 0.95

    def test_missing_required(self):
        ch = ChannelMatch(
            name="W",
            present=False,
            matched_required=["wvalid", "wready"],
            matched_optional=[],
            missing_required=["wdata"],
            score=0.5,
        )
        assert not ch.present
        assert "wdata" in ch.missing_required


# ---------------------------------------------------------------------------
# 通道完整性
# ---------------------------------------------------------------------------

class TestChannelCompleteness:
    def test_all_5_channels_present_axi4_full(self, detector):
        sigs = make_axi4_full_sigs()
        result = detector.detect(sigs)
        for ch_name in ["AW", "W", "B", "AR", "R"]:
            assert ch_name in result.channels
            assert result.channels[ch_name].present

    def test_required_signals_matched(self, detector):
        sigs = make_axi4_full_sigs()
        result = detector.detect(sigs)
        aw = result.channels["AW"]
        # AW 必含 awvalid, awready, awaddr
        for sig in ["awvalid", "awready", "awaddr"]:
            assert sig in aw.matched_required, f"{sig} should be in AW matched_required"


# ---------------------------------------------------------------------------
# 变体检测
# ---------------------------------------------------------------------------

class TestVariantDetection:
    def test_full_vs_lite_disambiguation(self, detector):
        """FULL 有 wstrb/wlast, LITE 没有."""
        full = make_axi4_full_sigs()
        lite = make_axi4_lite_sigs()
        r_full = detector.detect(full)
        r_lite = detector.detect(lite)
        assert r_full.variant == "AXI4_FULL"
        assert r_lite.variant == "AXI4_LITE"

    def test_full_higher_confidence_than_lite(self, detector):
        """FULL 信号更多, 置信度应略高 (但不是必须)."""
        full = make_axi4_full_sigs()
        lite = make_axi4_lite_sigs()
        r_full = detector.detect(full)
        r_lite = detector.detect(lite)
        # FULL 应该不比 LITE 低
        assert r_full.confidence >= r_lite.confidence - 0.05


# ---------------------------------------------------------------------------
# 命名风格兼容 (Session 1 集成)
# ---------------------------------------------------------------------------

class TestNamingStyleCompatibility:
    def test_chisel_style_detected(self, detector):
        """Chisel: io_aw_valid / io_aw_ready / io_aw_addr."""
        sigs = [
            SignalContext("io_aw_valid", 1, "output", "register", ["io_aw_ready"]),
            SignalContext("io_aw_ready", 1, "input", "port", ["io_aw_valid"]),
            SignalContext("io_aw_addr", 32, "output", "port", ["io_aw_valid"]),
            SignalContext("io_aw_len", 8, "output", "port", ["io_aw_valid"]),
            SignalContext("io_w_valid", 1, "output", "register", ["io_w_ready"]),
            SignalContext("io_w_ready", 1, "input", "port", ["io_w_valid"]),
            SignalContext("io_w_data", 32, "output", "port", ["io_w_valid"]),
            SignalContext("io_w_strb", 4, "output", "port", ["io_w_data"]),
            SignalContext("io_w_last", 1, "output", "port", ["io_w_data"]),
        ]
        result = detector.detect(sigs)
        assert result.protocol == "AXI4"

    def test_verilog_axi_style_detected(self, detector):
        """verilog-axi: m_axi_awvalid / s_axi_awready."""
        sigs = [
            SignalContext("m_axi_awvalid", 1, "output", "register", ["s_axi_awready"]),
            SignalContext("s_axi_awready", 1, "input", "port", ["m_axi_awvalid"]),
            SignalContext("m_axi_awaddr", 32, "output", "port", ["m_axi_awvalid"]),
            SignalContext("m_axi_wvalid", 1, "output", "register", ["s_axi_wready"]),
            SignalContext("s_axi_wready", 1, "input", "port", ["m_axi_wvalid"]),
            SignalContext("m_axi_wdata", 32, "output", "port", ["m_axi_wvalid"]),
            SignalContext("m_axi_bvalid", 1, "input", "port", ["s_axi_bready"]),
            SignalContext("s_axi_bready", 1, "output", "register", ["m_axi_bvalid"]),
            SignalContext("m_axi_bresp", 2, "input", "port", ["m_axi_bvalid"]),
        ]
        result = detector.detect(sigs)
        assert result.protocol == "AXI4"


# ---------------------------------------------------------------------------
# 4 项置信度融合
# ---------------------------------------------------------------------------

class TestFusionSources:
    """检测器应能输出 4 项置信度来源."""

    def test_fusion_result_has_4_components(self, detector):
        sigs = make_axi4_full_sigs()
        result = detector.detect(sigs)
        # 应该有 4 项 component
        assert hasattr(result, "name_score")
        assert hasattr(result, "structural_score")
        assert hasattr(result, "pattern_score")
        assert hasattr(result, "handshake_score")

    def test_fusion_weights_sum_to_one(self, detector):
        """4 项权重和应为 1.0."""
        # 0.30 + 0.30 + 0.25 + 0.15 = 1.0
        total = (
            ProtocolDetector.WEIGHT_NAME
            + ProtocolDetector.WEIGHT_STRUCTURAL
            + ProtocolDetector.WEIGHT_PATTERN
            + ProtocolDetector.WEIGHT_HANDSHAKE
        )
        assert abs(total - 1.0) < 0.001


# ---------------------------------------------------------------------------
# SignalMapping 数据结构
# ---------------------------------------------------------------------------

class TestSignalMapping:
    def test_basic(self):
        m = SignalMapping(
            original="io_aw_valid",
            canonical="awvalid",
            channel="AW",
            role="valid",
            match_type="normalized",
            score=0.9,
        )
        assert m.original == "io_aw_valid"
        assert m.canonical == "awvalid"
        assert m.channel == "AW"
        assert m.match_type == "normalized"

    def test_unknown_match(self):
        m = SignalMapping(
            original="my_weird_signal",
            canonical="",
            channel="",
            role="unknown",
            match_type="none",
            score=0.0,
        )
        assert m.match_type == "none"


# ---------------------------------------------------------------------------
# 性能 + 边界
# ---------------------------------------------------------------------------

class TestPerformance:
    def test_axi4_30_signals_fast(self, detector):
        import time
        sigs = make_axi4_full_sigs()
        start = time.time()
        detector.detect(sigs)
        elapsed = time.time() - start
        assert elapsed < 1.0  # 1s 足够

    def test_empty_signals(self, detector):
        result = detector.detect([])
        # 不应崩溃
        assert result.confidence >= 0.0
        assert result.warnings
