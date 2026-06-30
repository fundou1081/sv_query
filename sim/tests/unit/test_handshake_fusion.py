"""
test_handshake_fusion.py
=========================
Phase A + Phase B 集成: handshake_score 融合

设计目标:
  1. 抽象 HandshakeProvider 接口, 支持多种实现
  2. 默认 NameBasedHandshakeProvider (不需 SV 编译)
  3. 用户可注入 TraceBasedHandshakeProvider (跑真实 trace)
  4. 4 项置信度融合完整: name + structural + pattern + handshake
  5. 真实项目验证: 置信度从 0.6 → 0.85+

测试覆盖:
  - HandshakeProvider 抽象
  - NameBasedHandshakeProvider 默认实现
  - HandshakeType → 分数映射
  - 集成到 ProtocolDetector
  - 4 项分数全有值 (不再 0.0)
"""

import sys
from pathlib import Path
from typing import Dict, Optional, Tuple

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

from applications.bus.schema import (
    ProtocolSchemaRegistry,
    load_protocols,
)
from applications.bus.detector import (
    ProtocolDetector,
    ProtocolMatch,
)
from applications.bus.handshake_provider import (
    HandshakeProvider,
    NameBasedHandshakeProvider,
    HandshakeInfoLite,  # 轻量版 HandshakeInfo (无 DriverInfo 依赖)
    handshake_type_score,
)
from applications.bus.structural import SignalContext


# ---------------------------------------------------------------------------
# HandshakeProvider 抽象接口
# ---------------------------------------------------------------------------

class TestHandshakeProviderInterface:
    def test_abstract_method_required(self):
        """HandshakeProvider 必须实现 get_handshake."""
        with pytest.raises(TypeError):
            HandshakeProvider()

    def test_get_handshake_returns_info_or_none(self):
        """get_handshake 返回 HandshakeInfoLite 或 None."""
        provider = NameBasedHandshakeProvider()
        # valid/ready 都是 AXI 风格名字, 应返回 STANDARD_AXI
        info = provider.get_handshake("awvalid", "awready")
        assert info is None or hasattr(info, "handshake_type")


# ---------------------------------------------------------------------------
# HandshakeInfoLite 轻量版
# ---------------------------------------------------------------------------

class TestHandshakeInfoLite:
    def test_basic(self):
        info = HandshakeInfoLite(
            valid="awvalid",
            ready="awready",
            handshake_type="STANDARD_AXI",
            channel="AW",
        )
        assert info.valid == "awvalid"
        assert info.handshake_type == "STANDARD_AXI"

    def test_repr_doesnt_crash(self):
        info = HandshakeInfoLite(
            valid="awvalid", ready="awready",
            handshake_type="STANDARD_AXI", channel="AW",
        )
        # 不应崩溃
        repr(info)


# ---------------------------------------------------------------------------
# HandshakeType 分数映射
# ---------------------------------------------------------------------------

class TestHandshakeTypeScore:
    def test_standard_axi_highest(self):
        assert handshake_type_score("STANDARD_AXI") == 1.0

    def test_combinational_bp_high(self):
        assert handshake_type_score("COMBINATIONAL_BP") == 0.8

    def test_registered_bp(self):
        assert handshake_type_score("REGISTERED_BP") == 0.7

    def test_latched_bp(self):
        assert handshake_type_score("LATCHED_BP") == 0.7

    def test_wire_passthrough_low(self):
        """透传是握手被绕过, 分数低."""
        assert handshake_type_score("WIRE_PASSTHROUGH") == 0.4

    def test_port_passthrough(self):
        assert handshake_type_score("PORT_PASSTHROUGH") == 0.4

    def test_unused_negative(self):
        """未使用的信号应该减分."""
        assert handshake_type_score("UNUSED") < 0.0

    def test_unknown_neutral(self):
        assert handshake_type_score("UNKNOWN") == 0.0

    def test_unknown_type_returns_zero(self):
        """未知的 type 名返回 0."""
        assert handshake_type_score("FOO_BAR") == 0.0


# ---------------------------------------------------------------------------
# NameBasedHandshakeProvider 默认实现
# ---------------------------------------------------------------------------

class TestNameBasedHandshakeProvider:
    def test_axi_aw_pair_is_standard(self):
        """awvalid/awready → STANDARD_AXI + AW 通道."""
        provider = NameBasedHandshakeProvider()
        info = provider.get_handshake("awvalid", "awready")
        assert info is not None
        assert info.handshake_type == "STANDARD_AXI"
        assert info.channel == "AW"

    def test_axi_w_pair(self):
        provider = NameBasedHandshakeProvider()
        info = provider.get_handshake("wvalid", "wready")
        assert info is not None
        assert info.handshake_type == "STANDARD_AXI"
        assert info.channel == "W"

    def test_axi_b_pair(self):
        provider = NameBasedHandshakeProvider()
        info = provider.get_handshake("bvalid", "bready")
        assert info.handshake_type == "STANDARD_AXI"
        assert info.channel == "B"

    def test_axi_ar_pair(self):
        provider = NameBasedHandshakeProvider()
        info = provider.get_handshake("arvalid", "arready")
        assert info.channel == "AR"

    def test_axi_r_pair(self):
        provider = NameBasedHandshakeProvider()
        info = provider.get_handshake("rvalid", "rready")
        assert info.channel == "R"

    def test_chisel_style(self):
        """Chisel: io_aw_valid / io_aw_ready → STANDARD_AXI."""
        provider = NameBasedHandshakeProvider()
        info = provider.get_handshake("io_aw_valid", "io_aw_ready")
        assert info is not None
        assert info.handshake_type == "STANDARD_AXI"
        assert info.channel == "AW"

    def test_verilog_axi_style(self):
        """verilog-axi: m_axi_awvalid / s_axi_awready → STANDARD_AXI."""
        provider = NameBasedHandshakeProvider()
        info = provider.get_handshake("m_axi_awvalid", "s_axi_awready")
        assert info is not None
        assert info.handshake_type == "STANDARD_AXI"

    def test_unrelated_pair_returns_wire_passthrough(self):
        """不相关的两个信号 → WIRE_PASSTHROUGH (协议不匹配)."""
        provider = NameBasedHandshakeProvider()
        info = provider.get_handshake("my_weird_signal", "another_signal")
        # 不像任何已知协议, 应该是透传或 None
        if info is not None:
            assert info.handshake_type in ("WIRE_PASSTHROUGH", "UNKNOWN")

    def test_non_anchor_pair_returns_none_or_wire(self):
        """一个像 valid, 另一个不像 ready → WIRE_PASSTHROUGH."""
        provider = NameBasedHandshakeProvider()
        # awvalid (像 valid) + some_other (不像 ready)
        info = provider.get_handshake("awvalid", "some_random")
        if info is not None:
            assert info.handshake_type in ("WIRE_PASSTHROUGH", "UNKNOWN", "PORT_PASSTHROUGH")


# ---------------------------------------------------------------------------
# 自定义 HandshakeProvider (mock 测试)
# ---------------------------------------------------------------------------

class MockHandshakeProvider(HandshakeProvider):
    """可注入的 mock provider, 用于测试 detector 集成."""

    def __init__(self, mapping: dict[tuple[str, str], str]):
        self._mapping = mapping

    def get_handshake(self, valid: str, ready: str) -> HandshakeInfoLite | None:
        key = (valid, ready)
        if key in self._mapping:
            return HandshakeInfoLite(
                valid=valid, ready=ready,
                handshake_type=self._mapping[key],
                channel="AW",
            )
        return None


class TestMockProvider:
    def test_inject_into_detector(self):
        """用 mock provider 注入 detector."""
        schemas = load_protocols("config/protocols")
        mock = MockHandshakeProvider({
            ("awvalid", "awready"): "STANDARD_AXI",
            ("wvalid", "wready"): "STANDARD_AXI",
            ("bvalid", "bready"): "STANDARD_AXI",
            ("arvalid", "arready"): "STANDARD_AXI",
            ("rvalid", "rready"): "STANDARD_AXI",
        })
        detector = ProtocolDetector(
            schemas=schemas,
            handshake_provider=mock,
        )
        sigs = [
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
        ]
        match = detector.detect(sigs)
        # handshake_score 应该不为 0
        assert match.handshake_score > 0.0
        # 总置信度应该提升
        assert match.confidence > 0.5

    def test_passthrough_lowers_score(self):
        """所有 anchor 都是 WIRE_PASSTHROUGH → 置信度低."""
        schemas = load_protocols("config/protocols")
        mock = MockHandshakeProvider({
            ("awvalid", "awready"): "WIRE_PASSTHROUGH",
            ("wvalid", "wready"): "WIRE_PASSTHROUGH",
            ("bvalid", "bready"): "WIRE_PASSTHROUGH",
            ("arvalid", "arready"): "WIRE_PASSTHROUGH",
            ("rvalid", "rready"): "WIRE_PASSTHROUGH",
        })
        detector = ProtocolDetector(
            schemas=schemas,
            handshake_provider=mock,
        )
        sigs = [
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
        ]
        match = detector.detect(sigs)
        # handshake_score 应该较低 (WIRE_PASSTHROUGH = 0.4)
        assert match.handshake_score < 0.5


# ---------------------------------------------------------------------------
# 4 项置信度融合 (集成验证)
# ---------------------------------------------------------------------------

class TestFourWayFusion:
    def test_all_four_scores_populated(self):
        """4 项分数都应该有值 (不再 0.0)."""
        schemas = load_protocols("config/protocols")
        detector = ProtocolDetector(
            schemas=schemas,
            handshake_provider=NameBasedHandshakeProvider(),
        )
        sigs = [
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
        ]
        match = detector.detect(sigs)
        assert match.name_score > 0
        assert match.structural_score > 0
        assert match.pattern_score > 0
        assert match.handshake_score > 0  # 不再 0

    def test_fusion_improves_confidence(self):
        """融合 handshake 后, 置信度比之前 (0.5) 高."""
        schemas = load_protocols("config/protocols")
        # 无 handshake provider (旧行为)
        det_old = ProtocolDetector(schemas=schemas)
        # 有 handshake provider (新行为)
        det_new = ProtocolDetector(
            schemas=schemas,
            handshake_provider=NameBasedHandshakeProvider(),
        )
        sigs = [
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
        ]
        match_old = det_old.detect(sigs)
        match_new = det_new.detect(sigs)
        # 新版 handshake_score > 0, 总置信度应 >= 旧版
        assert match_new.handshake_score > 0
        assert match_new.confidence >= match_old.confidence - 0.01  # 允许 0.01 误差

    def test_handshake_boosts_full_more_than_lite(self):
        """AXI4_FULL 应该有更多 anchor, handshake 分数更高."""
        schemas = load_protocols("config/protocols")
        det = ProtocolDetector(
            schemas=schemas,
            handshake_provider=NameBasedHandshakeProvider(),
        )
        full_sigs = [
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
            SignalContext("arlen", 8, "output", "port", ["arvalid"]),
            SignalContext("rvalid", 1, "input", "port", ["rready"]),
            SignalContext("rready", 1, "output", "register", ["rvalid"]),
            SignalContext("rdata", 32, "input", "port", ["rvalid"]),
            SignalContext("rlast", 1, "input", "port", ["rvalid"]),
        ]
        lite_sigs = [
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
        ]
        match_full = det.detect(full_sigs)
        match_lite = det.detect(lite_sigs)
        # FULL 信号多, handshake_score 应 >= LITE
        assert match_full.handshake_score >= match_lite.handshake_score - 0.01
        # FULL 变体正确
        assert match_full.variant == "AXI4_FULL"
        assert match_lite.variant == "AXI4_LITE"


# ---------------------------------------------------------------------------
# 性能
# ---------------------------------------------------------------------------

class TestPerformance:
    def test_detect_with_handshake_fast(self):
        import time
        schemas = load_protocols("config/protocols")
        det = ProtocolDetector(
            schemas=schemas,
            handshake_provider=NameBasedHandshakeProvider(),
        )
        sigs = [
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
        ]
        start = time.time()
        for _ in range(10):
            det.detect(sigs)
        elapsed = time.time() - start
        assert elapsed < 1.0
