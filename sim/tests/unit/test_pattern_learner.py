"""
test_pattern_learner.py
========================
Phase A Session 3: PatternLearner anchor-based 模式学习

设计目标:
  1. 从已知 valid+ready 锚点学习通道前缀
  2. 用学到的前缀分组所有信号
  3. 处理生成代码 (Chisel/SpinalHDL) + verilog-axi 风格
  4. 输出 (channel, signals, confidence) — Session 4 融合用

测试覆盖:
  - AXI4 5 通道分组 (AW/W/B/AR/R)
  - TL-UL 2 通道分组 (A/D)
  - APB 信号 (无 valid/ready, 用 setup/ready 模式)
  - Chisel/SpinalHDL 命名 (io_aw_valid 等)
  - verilog-axi 命名 (m_axi_awvalid 等)
  - 边界: 无 anchor / 无信号 / 无公共前缀
  - 置信度: 长 base 高分, 短 base 低分
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

from trace.core.protocol.pattern_learner import (
    PatternLearner,
    ChannelGroup,
    ChannelSignal,
)
from trace.core.protocol.normalize import SignalNormalizer, NormalizeConfig


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def learner() -> PatternLearner:
    return PatternLearner()


@pytest.fixture
def norm() -> SignalNormalizer:
    return SignalNormalizer(NormalizeConfig.default())


# ---------------------------------------------------------------------------
# AXI 5 通道分组
# ---------------------------------------------------------------------------

class TestAXI4Channels:
    """AXI4 master 视角: AW / W / B / AR / R 5 通道."""

    def test_aw_channel_groups_address_write_signals(self, learner):
        """AW 通道: awvalid/awready/awaddr/awlen/awsize/awburst/awid."""
        groups = learner.learn(
            anchors=[("awvalid", "awready")],
            all_signals=[
                "awvalid", "awready", "awaddr", "awlen", "awsize",
                "awburst", "awid",
                # 其他通道 (不应被分到 AW)
                "wvalid", "wready", "wdata", "wstrb", "wlast",
                "bvalid", "bready", "bresp",
            ],
        )
        aw = next((g for g in groups if g.name.lower() == "aw"), None)
        assert aw is not None, "AW 通道应该被识别"
        assert "awvalid" in aw.signals
        assert "awready" in aw.signals
        assert "awaddr" in aw.signals
        assert "awlen" in aw.signals
        assert "awsize" in aw.signals
        assert "awburst" in aw.signals
        assert "awid" in aw.signals
        # 不应包含其他通道
        assert "wvalid" not in aw.signals
        assert "bvalid" not in aw.signals

    def test_w_channel_groups_write_data(self, learner):
        groups = learner.learn(
            anchors=[("wvalid", "wready")],
            all_signals=["wvalid", "wready", "wdata", "wstrb", "wlast",
                         "awvalid", "awready", "awaddr"],
        )
        w = next((g for g in groups if g.name.lower() == "w"), None)
        assert w is not None
        assert "wvalid" in w.signals
        assert "wready" in w.signals
        assert "wdata" in w.signals
        assert "wstrb" in w.signals
        assert "wlast" in w.signals
        assert "awvalid" not in w.signals

    def test_b_channel_groups_write_response(self, learner):
        groups = learner.learn(
            anchors=[("bvalid", "bready")],
            all_signals=["bvalid", "bready", "bresp", "bid",
                         "awvalid", "awready", "awaddr"],
        )
        b = next((g for g in groups if g.name.lower() == "b"), None)
        assert b is not None
        assert "bvalid" in b.signals
        assert "bready" in b.signals
        assert "bresp" in b.signals
        assert "bid" in b.signals
        assert "awvalid" not in b.signals

    def test_ar_channel_groups_address_read(self, learner):
        groups = learner.learn(
            anchors=[("arvalid", "arready")],
            all_signals=["arvalid", "arready", "araddr", "arlen", "arsize", "arburst", "arid",
                         "rvalid", "rready", "rdata", "rresp"],
        )
        ar = next((g for g in groups if g.name.lower() == "ar"), None)
        assert ar is not None
        assert "arvalid" in ar.signals
        assert "arready" in ar.signals
        assert "araddr" in ar.signals
        assert "arlen" in ar.signals
        assert "rvalid" not in ar.signals

    def test_r_channel_groups_read_data(self, learner):
        groups = learner.learn(
            anchors=[("rvalid", "rready")],
            all_signals=["rvalid", "rready", "rdata", "rresp", "rid", "rlast",
                         "awvalid", "awready", "awaddr"],
        )
        r = next((g for g in groups if g.name.lower() == "r"), None)
        assert r is not None
        assert "rvalid" in r.signals
        assert "rready" in r.signals
        assert "rdata" in r.signals
        assert "rresp" in r.signals
        assert "rid" in r.signals
        assert "rlast" in r.signals
        assert "awvalid" not in r.signals

    def test_all_5_axi_channels(self, learner):
        """5 通道 anchor, 完整 AXI 信号列表, 每通道独立分组."""
        all_signals = [
            # AW
            "awvalid", "awready", "awaddr", "awlen", "awsize", "awburst", "awid", "awuser",
            # W
            "wvalid", "wready", "wdata", "wstrb", "wlast",
            # B
            "bvalid", "bready", "bresp", "bid",
            # AR
            "arvalid", "arready", "araddr", "arlen", "arsize", "arburst", "arid",
            # R
            "rvalid", "rready", "rdata", "rresp", "rid", "rlast",
        ]
        anchors = [
            ("awvalid", "awready"),
            ("wvalid", "wready"),
            ("bvalid", "bready"),
            ("arvalid", "arready"),
            ("rvalid", "rready"),
        ]
        groups = learner.learn(anchors=anchors, all_signals=all_signals)
        names_lower = {g.name.lower() for g in groups}
        # 5 通道都应被识别
        assert "aw" in names_lower
        assert "w" in names_lower
        assert "b" in names_lower
        assert "ar" in names_lower
        assert "r" in names_lower
        # 总共 5 个组
        assert len(groups) == 5


# ---------------------------------------------------------------------------
# TL-UL (OpenTitan) 2 通道
# ---------------------------------------------------------------------------

class TestTLULChannels:
    """OpenTitan TL-UL: A (request) / D (response) 2 通道."""

    def test_a_channel_groups_request(self, learner):
        groups = learner.learn(
            anchors=[("a_valid", "a_ready")],
            all_signals=[
                "a_valid", "a_ready", "a_opcode", "a_param",
                "a_size", "a_source", "a_address", "a_mask", "a_data", "a_user",
                "d_valid", "d_ready", "d_opcode", "d_data", "d_source", "d_error",
            ],
        )
        a = next((g for g in groups if g.name.lower() == "a"), None)
        assert a is not None
        # A 通道所有信号
        for sig in ["a_valid", "a_ready", "a_opcode", "a_param",
                    "a_size", "a_source", "a_address", "a_mask", "a_data", "a_user"]:
            assert sig in a.signals
        # D 通道不应混入
        assert "d_valid" not in a.signals
        assert "d_data" not in a.signals

    def test_d_channel_groups_response(self, learner):
        groups = learner.learn(
            anchors=[("d_valid", "d_ready")],
            all_signals=[
                "a_valid", "a_ready", "a_opcode", "a_data",
                "d_valid", "d_ready", "d_opcode", "d_data", "d_source", "d_error",
            ],
        )
        d = next((g for g in groups if g.name.lower() == "d"), None)
        assert d is not None
        for sig in ["d_valid", "d_ready", "d_opcode", "d_data", "d_source", "d_error"]:
            assert sig in d.signals
        assert "a_valid" not in d.signals

    def test_a_and_d_simultaneously(self, learner):
        all_signals = [
            "a_valid", "a_ready", "a_opcode", "a_address", "a_data",
            "d_valid", "d_ready", "d_opcode", "d_data", "d_error",
        ]
        anchors = [("a_valid", "a_ready"), ("d_valid", "d_ready")]
        groups = learner.learn(anchors=anchors, all_signals=all_signals)
        names_lower = {g.name.lower() for g in groups}
        assert "a" in names_lower
        assert "d" in names_lower


# ---------------------------------------------------------------------------
# 命名风格兼容 (Session 1 标准化集成)
# ---------------------------------------------------------------------------

class TestNamingStyles:
    """Chisel / SpinalHDL / verilog-axi 命名风格兼容."""

    def test_chisel_style_io_aw_valid(self, learner):
        """Chisel: io_aw_valid / io_aw_ready / io_aw_addr."""
        groups = learner.learn(
            anchors=[("io_aw_valid", "io_aw_ready")],
            all_signals=[
                "io_aw_valid", "io_aw_ready", "io_aw_addr", "io_aw_len",
                "io_w_valid", "io_w_ready", "io_w_data", "io_w_last",
            ],
        )
        # 标准化后 anchor 前缀是 "aw"
        aw = next((g for g in groups if g.name.lower() == "aw"), None)
        assert aw is not None
        assert "io_aw_valid" in aw.signals
        assert "io_aw_ready" in aw.signals
        assert "io_aw_addr" in aw.signals
        assert "io_aw_len" in aw.signals
        assert "io_w_valid" not in aw.signals

    def test_spinalhdl_style_no_underscore(self, learner):
        """SpinalHDL: io_awvalid (无下划线) / io_wready."""
        groups = learner.learn(
            anchors=[("io_awvalid", "io_awready")],
            all_signals=[
                "io_awvalid", "io_awready", "io_awaddr", "io_awlen",
                "io_wvalid", "io_wready", "io_wdata", "io_wlast",
            ],
        )
        aw = next((g for g in groups if g.name.lower() == "aw"), None)
        assert aw is not None
        assert "io_awvalid" in aw.signals
        assert "io_awready" in aw.signals
        assert "io_awaddr" in aw.signals
        assert "io_wvalid" not in aw.signals

    def test_verilog_axi_style(self, learner):
        """verilog-axi: m_axi_awvalid / s_axi_awready (master/slave 不同方向)."""
        groups = learner.learn(
            anchors=[("m_axi_awvalid", "s_axi_awready")],
            all_signals=[
                "m_axi_awvalid", "s_axi_awready",
                "m_axi_awaddr", "m_axi_awlen",
                "m_axi_wvalid", "s_axi_wready", "m_axi_wdata",
            ],
        )
        # anchor 一方 master 一方 slave, 但共享 "aw" 前缀
        aw = next((g for g in groups if g.name.lower() == "aw"), None)
        assert aw is not None
        assert "m_axi_awvalid" in aw.signals
        assert "s_axi_awready" in aw.signals
        assert "m_axi_awaddr" in aw.signals
        assert "m_axi_wvalid" not in aw.signals

    def test_opentitan_tlul_with_o_i_suffix(self, learner):
        """OpenTitan: a_valid_o / a_ready_i / a_opcode (无后缀)."""
        groups = learner.learn(
            anchors=[("a_valid_o", "a_ready_i")],
            all_signals=[
                "a_valid_o", "a_ready_i", "a_opcode", "a_address", "a_data",
                "d_valid_i", "d_ready_o", "d_opcode", "d_data",
            ],
        )
        a = next((g for g in groups if g.name.lower() == "a"), None)
        assert a is not None
        assert "a_valid_o" in a.signals
        assert "a_ready_i" in a.signals
        assert "a_opcode" in a.signals
        assert "a_address" in a.signals
        assert "d_valid_i" not in a.signals


# ---------------------------------------------------------------------------
# 边界 + 异常
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_no_anchor_returns_empty(self, learner):
        groups = learner.learn(anchors=[], all_signals=["x", "y", "z"])
        assert groups == []

    def test_no_signals_returns_anchors_only(self, learner):
        groups = learner.learn(anchors=[("awvalid", "awready")], all_signals=[])
        # 即使没有其他信号, anchor 本身也是一个组 (只有 valid+ready)
        assert len(groups) == 1
        aw = groups[0]
        assert "awvalid" in aw.signals
        assert "awready" in aw.signals

    def test_no_common_prefix_skipped(self, learner):
        """anchor 没有公共前缀, 跳过."""
        groups = learner.learn(
            anchors=[("xyz_foo", "abc_bar")],  # 无公共前缀
            all_signals=["xyz_foo", "abc_bar"],
        )
        assert groups == []

    def test_dangling_anchor_signal_not_in_list(self, learner):
        """anchor 的 valid/ready 不在 all_signals 中, 但还能分组其他匹配的."""
        groups = learner.learn(
            anchors=[("awvalid", "awready")],
            all_signals=["awaddr", "awlen", "awsize"],  # 没有 awvalid/awready
        )
        aw = next((g for g in groups if g.name.lower() == "aw"), None)
        # 仍然能分到 AW 通道
        assert aw is not None
        assert "awaddr" in aw.signals

    def test_short_channel_base_low_confidence(self, learner):
        """1 字符 channel base (e.g. "a") 置信度低."""
        groups = learner.learn(
            anchors=[("avalid", "aready")],
            all_signals=["avalid", "aready", "aaddr", "aopcode"],
        )
        a = next((g for g in groups if g.name.lower() == "a"), None)
        assert a is not None
        # 1 字符 base 置信度应该低于 2 字符
        assert a.confidence < 0.6

    def test_long_channel_base_high_confidence(self, learner):
        """2+ 字符 channel base 置信度高."""
        groups = learner.learn(
            anchors=[("awvalid", "awready")],
            all_signals=["awvalid", "awready", "awaddr"],
        )
        aw = next((g for g in groups if g.name.lower() == "aw"), None)
        assert aw is not None
        assert aw.confidence >= 0.7


# ---------------------------------------------------------------------------
# 通道角色推断
# ---------------------------------------------------------------------------

class TestRoleInference:
    """在分组后, 通道内每个信号推断角色 (name-based, 简单版)."""

    def test_anchor_valid_is_valid_role(self, learner):
        groups = learner.learn(
            anchors=[("awvalid", "awready")],
            all_signals=["awvalid", "awready", "awaddr"],
        )
        aw = groups[0]
        # 通过 name 查角色
        assert aw.get_role("awvalid") == "valid"
        assert aw.get_role("awready") == "ready"

    def test_addr_role(self, learner):
        groups = learner.learn(
            anchors=[("awvalid", "awready")],
            all_signals=["awvalid", "awready", "awaddr"],
        )
        aw = groups[0]
        assert aw.get_role("awaddr") == "addr"

    def test_data_role(self, learner):
        groups = learner.learn(
            anchors=[("wvalid", "wready")],
            all_signals=["wvalid", "wready", "wdata"],
        )
        w = groups[0]
        assert w.get_role("wdata") == "data"

    def test_resp_role(self, learner):
        groups = learner.learn(
            anchors=[("bvalid", "bready")],
            all_signals=["bvalid", "bready", "bresp"],
        )
        b = groups[0]
        assert b.get_role("bresp") == "resp"

    def test_ctrl_role(self, learner):
        groups = learner.learn(
            anchors=[("awvalid", "awready")],
            all_signals=["awvalid", "awready", "awlen", "awsize", "awburst", "awid"],
        )
        aw = groups[0]
        for sig in ["awlen", "awsize", "awburst", "awid"]:
            assert aw.get_role(sig) == "ctrl", f"{sig} should be ctrl"

    def test_strb_role(self, learner):
        groups = learner.learn(
            anchors=[("wvalid", "wready")],
            all_signals=["wvalid", "wready", "wstrb"],
        )
        w = groups[0]
        assert w.get_role("wstrb") == "strb"

    def test_last_role(self, learner):
        groups = learner.learn(
            anchors=[("wvalid", "wready")],
            all_signals=["wvalid", "wready", "wlast"],
        )
        w = groups[0]
        assert w.get_role("wlast") == "last"


# ---------------------------------------------------------------------------
# ChannelGroup 数据结构
# ---------------------------------------------------------------------------

class TestChannelGroup:
    def test_basic(self):
        g = ChannelGroup(
            name="AW",
            anchor_valid="awvalid",
            anchor_ready="awready",
            signals=["awvalid", "awready", "awaddr"],
            confidence=0.9,
        )
        assert g.name == "AW"
        assert len(g.signals) == 3
        assert g.confidence == 0.9

    def test_repr_doesnt_crash(self):
        g = ChannelGroup(
            name="AW",
            anchor_valid="awvalid",
            anchor_ready="awready",
            signals=["awvalid", "awready"],
            confidence=0.8,
        )
        # 不应崩溃
        s = repr(g)
        assert "AW" in s

    def test_get_role_for_unknown(self):
        g = ChannelGroup(
            name="AW",
            anchor_valid="awvalid",
            anchor_ready="awready",
            signals=["awvalid", "awready", "awweird"],
            confidence=0.8,
        )
        # 未知角色返回 "unknown"
        assert g.get_role("awweird") == "unknown"

    def test_signals_count(self):
        g = ChannelGroup(
            name="AW",
            anchor_valid="awvalid",
            anchor_ready="awready",
            signals=["awvalid", "awready", "awaddr", "awlen", "awsize"],
            confidence=0.8,
        )
        assert g.signal_count() == 5


# ---------------------------------------------------------------------------
# 性能 + 边界
# ---------------------------------------------------------------------------

class TestPerformance:
    def test_5_channels_30_signals_fast(self, learner):
        import time
        signals = (
            [f"aw{s}" for s in ["valid", "ready", "addr", "len", "size", "burst", "id"]]
            + [f"w{s}" for s in ["valid", "ready", "data", "strb", "last"]]
            + [f"b{s}" for s in ["valid", "ready", "resp", "id"]]
            + [f"ar{s}" for s in ["valid", "ready", "addr", "len"]]
            + [f"r{s}" for s in ["valid", "ready", "data", "resp", "last"]]
        )
        anchors = [
            ("awvalid", "awready"),
            ("wvalid", "wready"),
            ("bvalid", "bready"),
            ("arvalid", "arready"),
            ("rvalid", "rready"),
        ]
        start = time.time()
        learner.learn(anchors=anchors, all_signals=signals)
        elapsed = time.time() - start
        assert elapsed < 0.5
