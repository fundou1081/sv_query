# ==============================================================================
# test_handshake_detector.py - Phase B handshake detection tests
# ==============================================================================
"""
Tests for src/trace/core/handshake_detector.py
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

from trace.core.graph.models import DriverInfo, TraceNode
from trace.core.handshake_detector import (
    _classify_by_name,
    _classify_one_driver,
    _split_condition,
    classify_signal_channel,
    detect_from_signal_pair,
    detect_handshake_type,
    find_counterpart_in_condition,
)


# ==============================================================================
# 工具函数测试
# ==============================================================================

class TestSplitCondition:
    def test_and_split(self):
        assert _split_condition("awvalid && awready") == ["awvalid", "awready"]

    def test_or_split(self):
        assert _split_condition("a_valid || b_valid") == ["a_valid", "b_valid"]

    def test_empty(self):
        assert _split_condition("") == []

    def test_whitespace(self):
        assert _split_condition("  valid  &&  ready  ") == ["valid", "ready"]


class TestClassifyByName:
    def test_aw_channel(self):
        assert _classify_by_name("axi_adapter.s_axi_awvalid") == "AW"
        assert _classify_by_name("axi_adapter.s_axi_awready") == "AW"

    def test_w_channel(self):
        assert _classify_by_name("axi_adapter.s_axi_wvalid") == "W"

    def test_b_channel(self):
        assert _classify_by_name("axi_adapter.s_axi_bready") == "B"

    def test_ar_channel(self):
        assert _classify_by_name("axi_adapter.s_axi_arvalid") == "AR"

    def test_r_channel(self):
        assert _classify_by_name("axi_adapter.s_axi_rready") == "R"

    def test_a_channel(self):
        assert _classify_by_name("ram.ram_a_rd_resp_valid") == "A"

    def test_d_channel(self):
        assert _classify_by_name("s_axis_desc_tvalid") == "D"

    def test_unknown(self):
        assert _classify_by_name("random_signal") == "UNKNOWN"

    def test_classify_signal_channel_alias(self):
        assert classify_signal_channel("s_axi_awready") == "AW"


# ==============================================================================
# 核心检测函数测试
# ==============================================================================

def make_di(condition="", expression="", assign_type="", clock_domain="", target_signal="test_signal"):
    from trace.core.graph.models import NodeKind
    node = TraceNode(
        id=target_signal, name=target_signal, module="test_module",
        kind=NodeKind.SIGNAL, width=(0, 0),
    )
    return DriverInfo(
        node=node,
        condition=condition,
        expression=expression,
        assign_type=assign_type,
        clock_domain=clock_domain,
        target_signal=target_signal,
    )


class TestDetectHandshakeType:
    """detect_handshake_type 单 driver 测试"""

    def test_unused(self):
        """无 driver → UNUSED"""
        hi = detect_handshake_type("s_axi_awready", [])
        assert hi.handshake_type == "UNUSED"
        assert hi.ready == "s_axi_awready"

    def test_standard_axi(self):
        """if (valid && ready) → STANDARD_AXI"""
        dis = [make_di(condition="awvalid && awready", assign_type="always_ff")]
        hi = detect_handshake_type("s_axi_awready", dis)
        assert hi.handshake_type == "STANDARD_AXI"
        assert hi.channel == "AW"
        assert "awvalid" in hi.valid.lower()

    def test_combinational_bp_fifo_cond(self):
        """条件含 !full → COMBINATIONAL_BP (FIFO 反压)"""
        dis = [make_di(
            condition="!out_fifo_full && m_axi_wvalid_int",
            assign_type="always_comb",
        )]
        hi = detect_handshake_type("m_axi_wready_int", dis)
        assert hi.handshake_type == "COMBINATIONAL_BP"
        assert hi.extra.get("fifo_name") == "out_fifo_full"
        assert "m_axi_wvalid_int" in hi.valid

    def test_combinational_bp_fifo_expr(self):
        """表达式含 !empty → COMBINATIONAL_BP"""
        dis = [make_di(
            expression="!in_fifo_empty",
            assign_type="always_comb",
        )]
        hi = detect_handshake_type("m_axi_rready", dis)
        assert hi.handshake_type == "COMBINATIONAL_BP"
        assert "empty" in hi.extra.get("fifo_name", "")

    def test_registered_bp(self):
        """always_ff 无 cond → REGISTERED_BP"""
        dis = [make_di(
            expression="next_ready",
            assign_type="always_ff",
            clock_domain="clk",
        )]
        hi = detect_handshake_type("s_axi_awready_reg", dis)
        assert hi.handshake_type == "REGISTERED_BP"
        assert hi.assign_type == "always_ff"

    def test_conditional_ctrl(self):
        """有 cond 但无 valid/ready 关键字 → CONDITIONAL_CTRL"""
        dis = [make_di(
            condition="axi_state_reg == AXI_STATE_IDLE",
            assign_type="always_ff",
        )]
        hi = detect_handshake_type("axi_cmd_ready", dis)
        assert hi.handshake_type == "CONDITIONAL_CTRL"

    def test_complex_arb(self):
        """|| 条件 → COMPLEX_ARB"""
        dis = [make_di(
            condition="a_valid || b_valid",
            assign_type="always_comb",
        )]
        hi = detect_handshake_type("d_ready", dis)
        assert hi.handshake_type == "COMPLEX_ARB"

    def test_wire_passthrough(self):
        """continuous assign with simple signal expr → WIRE_PASSTHROUGH"""
        dis = [make_di(
            expression="s_axi_rready",
            assign_type="continuous",
        )]
        hi = detect_handshake_type("ram_rd_resp_ready", dis)
        assert hi.handshake_type == "WIRE_PASSTHROUGH"
        assert hi.extra.get("source_signal") == "s_axi_rready"

    def test_port_passthrough(self):
        """port connection → PORT_PASSTHROUGH"""
        dis = [make_di(
            expression="",
            assign_type="connection",
            clock_domain="a_clk",
        )]
        hi = detect_handshake_type("ram_a_rd_resp_ready", dis)
        assert hi.handshake_type == "PORT_PASSTHROUGH"
        assert hi.clock_domain == "a_clk"


class TestPriorityBasedSelection:
    """多 driver 时按优先级选最佳判定"""

    def test_priority_fifo_over_passthrough(self):
        """FIFO 条件优先于透传 (后者来自其他 driver)"""
        dis = [
            # 第一个: 透传
            make_di(expression="m_axi_wready_int_reg", assign_type="continuous"),
            # 第二个: FIFO 反压
            make_di(
                condition="!out_fifo_full && m_axi_wvalid_int",
                assign_type="always_comb",
            ),
        ]
        hi = detect_handshake_type("m_axi_wready_int", dis)
        # COMBINATIONAL_BP 比 WIRE_PASSTHROUGH 优先级高
        assert hi.handshake_type == "COMBINATIONAL_BP"
        assert "out_fifo_full" in hi.condition

    def test_priority_standard_axi_over_registered(self):
        """标准握手优先于寄存器延迟"""
        dis = [
            make_di(expression="next_ready", assign_type="always_ff", clock_domain="clk"),
            make_di(condition="awvalid && awready", assign_type="always_ff", clock_domain="clk"),
        ]
        hi = detect_handshake_type("s_axi_awready", dis)
        assert hi.handshake_type == "STANDARD_AXI"

    def test_priority_over_unknown(self):
        """有意义的类型优先于 UNKNOWN"""
        dis = [
            make_di(condition="", expression="", assign_type="", clock_domain=""),
            make_di(condition="rvalid && rready", assign_type="always_ff"),
        ]
        hi = detect_handshake_type("s_axi_rready", dis)
        assert hi.handshake_type == "STANDARD_AXI"


# ==============================================================================
# 工具函数测试
# ==============================================================================

class TestFindCounterpartInCondition:
    def test_basic(self):
        c = find_counterpart_in_condition("awvalid && awready", "awready")
        assert c == "awvalid"

    def test_not_found(self):
        c = find_counterpart_in_condition("awvalid && awready", "missing")
        assert c is None

    def test_empty(self):
        assert find_counterpart_in_condition("", "awready") is None


# ==============================================================================
# _classify_one_driver 单元测试 (内部 API)
# ==============================================================================

class TestClassifyOneDriver:
    def test_standard_axi_returns_handshake_info(self):
        di = make_di(condition="awvalid && awready", assign_type="always_ff")
        hi = _classify_one_driver("s_axi_awready", di)
        assert hi is not None
        assert hi.handshake_type == "STANDARD_AXI"

    def test_passthrough_returns_handshake_info(self):
        di = make_di(expression="other_signal", assign_type="continuous")
        hi = _classify_one_driver("test_ready", di)
        assert hi is not None
        assert hi.handshake_type == "WIRE_PASSTHROUGH"

    def test_no_match_returns_none(self):
        di = make_di(condition="", expression="", assign_type="blocking")
        # 没有 cond/expr/assign_type 都不匹配
        # 但 expression 为空时 PORT_PASSTHROUGH 会匹配
        # 用一个不会匹配任何 case 的 input
        di = make_di(condition="", expression="", assign_type="other_type")
        hi = _classify_one_driver("test_ready", di)
        # assign_type 不在 connection/""/continuous 中，所有 case 都不匹配
        assert hi is None
