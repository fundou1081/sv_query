"""
test_structural_hints.py
========================
Phase A Session 2: StructuralHints 结构性角色提示层

设计目标:
  1. 不用名字 (名字标准化是 Session 1 的事)
  2. 只看 width + direction + driver_kind + 配对
  3. 8 个角色: valid / ready / data / addr / resp / ctrl / strb / last
  4. 输出 0.0-1.0 置信度, 由 Session 4 融合层使用

测试覆盖:
  - 单特征 (width / direction / driver / pairing)
  - 端到端真实信号场景 (AXI / TL-UL / APB / AHB)
  - 边界 (0-bit / 1-bit / 超宽 / inout)
  - 配对检测 (valid+ready / data+strb / data+last)
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

from applications.bus.structural import (
    SignalContext,
    StructuralHints,
    StructuralRoleDetector,
    WidthCategory,
)


# ---------------------------------------------------------------------------
# SignalContext 构造工具
# ---------------------------------------------------------------------------

def make_sig(
    name: str,
    width: int = 1,
    direction: str = "input",
    driver_kind: str = "port",
    paired: list = None,
) -> SignalContext:
    return SignalContext(
        name=name,
        width=width,
        direction=direction,
        driver_kind=driver_kind,
        paired_signals=list(paired or []),
    )


# ---------------------------------------------------------------------------
# WidthCategory 分类
# ---------------------------------------------------------------------------

class TestWidthCategory:
    """宽度分类: 1bit / small / wide / unknown."""

    def test_1bit(self):
        assert WidthCategory.classify(1) == WidthCategory.ONE_BIT

    def test_small_2_to_8(self):
        """2-8 bit: resp / id / len / size 类控制信号."""
        for w in (2, 3, 4, 5, 6, 7, 8):
            assert WidthCategory.classify(w) == WidthCategory.SMALL

    def test_wide_above_8(self):
        """≥9 bit: data / addr 类载荷信号."""
        for w in (9, 16, 32, 64, 128, 256, 512, 1024):
            assert WidthCategory.classify(w) == WidthCategory.WIDE

    def test_zero_width_is_unknown(self):
        assert WidthCategory.classify(0) == WidthCategory.UNKNOWN

    def test_negative_width_is_unknown(self):
        assert WidthCategory.classify(-1) == WidthCategory.UNKNOWN


# ---------------------------------------------------------------------------
# 单特征: width
# ---------------------------------------------------------------------------

class TestWidthBasedHints:
    """宽度单独如何影响角色得分."""

    def test_1bit_output_suggests_valid_or_strb_or_last(self):
        """1 bit output 可能 valid / strb / last."""
        sig = make_sig("x", width=1, direction="output")
        det = StructuralRoleDetector()
        h = det.detect(sig)
        # 1-bit output: valid/strb/last 都应该得高分
        assert h.is_valid_like >= 0.3
        assert h.is_strb_like >= 0.1 or h.is_last_like >= 0.1

    def test_1bit_input_suggests_ready(self):
        """1 bit input 多半是 ready / ack / stall."""
        sig = make_sig("x", width=1, direction="input")
        det = StructuralRoleDetector()
        h = det.detect(sig)
        assert h.is_ready_like >= 0.3

    def test_wide_output_suggests_data_or_addr(self):
        """宽 (≥32) output 多半是 data (write) 或 addr."""
        sig = make_sig("x", width=32, direction="output")
        det = StructuralRoleDetector()
        h = det.detect(sig)
        assert h.is_data_like >= 0.3
        assert h.is_addr_like >= 0.2  # 32-bit addr 也有可能

    def test_wide_input_suggests_data_or_resp(self):
        """宽 input 多半是 data (read) 或 resp."""
        sig = make_sig("x", width=32, direction="input")
        det = StructuralRoleDetector()
        h = det.detect(sig)
        assert h.is_data_like >= 0.2
        # resp 通常是 2-4 bit, 所以 32-bit input 不太像 resp
        assert h.is_resp_like < 0.3

    def test_small_2to4_input_suggests_resp(self):
        """2-4 bit input 多半是 AXI/TL-UL resp."""
        sig = make_sig("x", width=2, direction="input")
        det = StructuralRoleDetector()
        h = det.detect(sig)
        assert h.is_resp_like >= 0.3

    def test_small_4to8_output_suggests_ctrl(self):
        """4-8 bit output 多半是 AXI len/size/burst/id."""
        sig = make_sig("x", width=4, direction="output")
        det = StructuralRoleDetector()
        h = det.detect(sig)
        assert h.is_ctrl_like >= 0.3


# ---------------------------------------------------------------------------
# 单特征: direction
# ---------------------------------------------------------------------------

class TestDirectionBasedHints:
    """方向单独如何影响角色得分."""

    def test_output_boosts_valid_data_addr(self):
        """output 加分给 valid / data / addr / strb."""
        sig = make_sig("x", width=32, direction="output")
        det = StructuralRoleDetector()
        h = det.detect(sig)
        # data/addr 都应该高, 但 ready/resp 应该低
        assert h.is_data_like > h.is_ready_like
        assert h.is_addr_like > h.is_ready_like

    def test_input_boosts_ready_resp(self):
        """input 加分给 ready / resp."""
        sig = make_sig("x", width=1, direction="input")
        det = StructuralRoleDetector()
        h = det.detect(sig)
        assert h.is_ready_like > h.is_valid_like
        assert h.is_ready_like >= 0.3

    def test_inout_neutral(self):
        """inout 不偏不倚."""
        sig = make_sig("x", width=32, direction="inout")
        det = StructuralRoleDetector()
        h = det.detect(sig)
        # inout 不应该有方向偏置, data 和 addr 应该相等
        assert abs(h.is_data_like - h.is_addr_like) < 0.05


# ---------------------------------------------------------------------------
# 单特征: driver_kind
# ---------------------------------------------------------------------------

class TestDriverKindHints:
    """driver_kind: register / wire / port."""

    def test_register_boosts_valid(self):
        """register (clocked) 多半是 valid (协议 ready 信号)."""
        sig = make_sig("x", width=1, direction="output", driver_kind="register")
        det = StructuralRoleDetector()
        h = det.detect(sig)
        assert h.is_valid_like >= 0.5

    def test_wire_neutral(self):
        """wire (combinational) 没有特殊 boost."""
        sig_reg = make_sig("x", width=1, direction="output", driver_kind="register")
        sig_wire = make_sig("x", width=1, direction="output", driver_kind="wire")
        det = StructuralRoleDetector()
        h_reg = det.detect(sig_reg)
        h_wire = det.detect(sig_wire)
        # register 的 valid 分数应高于 wire
        assert h_reg.is_valid_like > h_wire.is_valid_like


# ---------------------------------------------------------------------------
# 配对检测: 找 valid+ready / data+strb / data+last
# ---------------------------------------------------------------------------

class TestPairingHints:
    """配对信号影响分数."""

    def test_1bit_output_paired_with_1bit_input_boosts_valid_ready(self):
        """1-bit output + 1-bit input 配对 → valid + ready."""
        sig_valid = make_sig("v", width=1, direction="output",
                             paired=["r"])
        sig_ready = make_sig("r", width=1, direction="input",
                             paired=["v"])
        all_sigs = [sig_valid, sig_ready]
        det = StructuralRoleDetector()
        h_v = det.detect(sig_valid, all_signals=all_sigs)
        h_r = det.detect(sig_ready, all_signals=all_sigs)
        # 配对 boost 后, valid 和 ready 分数都应该高
        assert h_v.is_valid_like >= 0.5
        assert h_r.is_ready_like >= 0.5

    def test_wide_signal_paired_with_1bit_strb_boosts_strb(self):
        """宽信号 + 1-bit 配对 → strb."""
        sig_data = make_sig("wdata", width=32, direction="output",
                            paired=["wstrb"])
        sig_strb = make_sig("wstrb", width=4, direction="output",
                            paired=["wdata"])
        all_sigs = [sig_data, sig_strb]
        det = StructuralRoleDetector()
        h_strb = det.detect(sig_strb, all_signals=all_sigs)
        # strb 的分数应该高
        assert h_strb.is_strb_like >= 0.25

    def test_wide_signal_paired_with_1bit_last_boosts_last(self):
        """宽信号 + 1-bit last 配对 → last."""
        sig_data = make_sig("wdata", width=32, direction="output",
                            paired=["wlast"])
        sig_last = make_sig("wlast", width=1, direction="output",
                            paired=["wdata"])
        all_sigs = [sig_data, sig_last]
        det = StructuralRoleDetector()
        h_last = det.detect(sig_last, all_signals=all_sigs)
        assert h_last.is_last_like >= 0.25

    def test_no_pairing_lower_scores(self):
        """无配对时分数较低."""
        sig_alone = make_sig("v", width=1, direction="output", paired=[])
        det = StructuralRoleDetector()
        h_alone = det.detect(sig_alone, all_signals=[sig_alone])
        # 没配对, valid 分数应该比有配对的低
        assert h_alone.is_valid_like < 0.7


# ---------------------------------------------------------------------------
# 端到端: 真实协议信号场景
# ---------------------------------------------------------------------------

class TestRealProtocolScenarios:
    """真实 AXI / TL-UL / APB 信号的端到端测试."""

    # ----- AXI4 master view -----

    def test_axi_master_awvalid(self):
        """AXI master: awvalid = 1bit output register + paired awready."""
        sig = make_sig("awvalid", width=1, direction="output",
                       driver_kind="register", paired=["awready"])
        det = StructuralRoleDetector()
        all_sigs = [
            sig,
            make_sig("awready", width=1, direction="input", paired=["awvalid"]),
        ]
        h = det.detect(sig, all_signals=all_sigs)
        assert h.dominant_role() == "valid"
        assert h.is_valid_like >= 0.6

    def test_axi_master_awready(self):
        sig = make_sig("awready", width=1, direction="input", paired=["awvalid"])
        det = StructuralRoleDetector()
        all_sigs = [
            sig,
            make_sig("awvalid", width=1, direction="output", paired=["awready"]),
        ]
        h = det.detect(sig, all_signals=all_sigs)
        assert h.dominant_role() == "ready"
        assert h.is_ready_like >= 0.5

    def test_axi_master_awaddr(self):
        sig = make_sig("awaddr", width=32, direction="output", paired=["awvalid", "awready"])
        det = StructuralRoleDetector()
        all_sigs = [
            sig,
            make_sig("awvalid", width=1, direction="output", paired=["awaddr", "awready"]),
            make_sig("awready", width=1, direction="input", paired=["awaddr", "awvalid"]),
        ]
        h = det.detect(sig, all_signals=all_sigs)
        # dominant 应该是 data 或 addr
        assert h.dominant_role() in ("addr", "data")
        assert h.is_addr_like >= 0.3

    def test_axi_master_wdata(self):
        sig = make_sig("wdata", width=32, direction="output", paired=["wvalid", "wstrb", "wlast"])
        det = StructuralRoleDetector()
        all_sigs = [
            sig,
            make_sig("wvalid", width=1, direction="output", paired=["wdata"]),
            make_sig("wstrb", width=4, direction="output", paired=["wdata"]),
            make_sig("wlast", width=1, direction="output", paired=["wdata"]),
        ]
        h = det.detect(sig, all_signals=all_sigs)
        assert h.dominant_role() == "data"
        assert h.is_data_like >= 0.5

    def test_axi_master_awlen(self):
        """AXI len: 4-bit output (控制信号)."""
        sig = make_sig("awlen", width=4, direction="output", paired=["awvalid"])
        det = StructuralRoleDetector()
        all_sigs = [
            sig,
            make_sig("awvalid", width=1, direction="output", paired=["awlen"]),
        ]
        h = det.detect(sig, all_signals=all_sigs)
        assert h.dominant_role() == "ctrl"
        assert h.is_ctrl_like >= 0.3

    def test_axi_master_bresp(self):
        """AXI resp: 2-bit input."""
        sig = make_sig("bresp", width=2, direction="input", paired=["bvalid", "bready"])
        det = StructuralRoleDetector()
        all_sigs = [
            sig,
            make_sig("bvalid", width=1, direction="input", paired=["bresp"]),
            make_sig("bready", width=1, direction="output", paired=["bresp"]),
        ]
        h = det.detect(sig, all_signals=all_sigs)
        assert h.dominant_role() == "resp"
        assert h.is_resp_like >= 0.3

    # ----- TL-UL (OpenTitan) -----

    def test_tlul_a_valid(self):
        """TL-UL: a_valid = 1-bit output."""
        sig = make_sig("a_valid_o", width=1, direction="output", driver_kind="register",
                       paired=["a_ready_i", "a_opcode", "a_param", "a_size", "a_source", "a_address", "a_mask", "a_data", "a_user"])
        det = StructuralRoleDetector()
        all_sigs = [sig] + [
            make_sig(n, **kwargs) for n, kwargs in [
                ("a_ready_i", {"width": 1, "direction": "input", "driver_kind": "port", "paired": ["a_valid_o"]}),
                ("a_opcode", {"width": 3, "direction": "output", "driver_kind": "port", "paired": ["a_valid_o"]}),
                ("a_address", {"width": 32, "direction": "output", "driver_kind": "port", "paired": ["a_valid_o"]}),
                ("a_data", {"width": 32, "direction": "output", "driver_kind": "port", "paired": ["a_valid_o"]}),
            ]
        ]
        h = det.detect(sig, all_signals=all_sigs)
        assert h.dominant_role() == "valid"
        assert h.is_valid_like >= 0.6

    def test_tlul_d_data(self):
        sig = make_sig("d_data", width=32, direction="input", paired=["d_valid", "d_ready"])
        det = StructuralRoleDetector()
        all_sigs = [
            sig,
            make_sig("d_valid", width=1, direction="input", paired=["d_data"]),
            make_sig("d_ready", width=1, direction="output", paired=["d_data"]),
        ]
        h = det.detect(sig, all_signals=all_sigs)
        assert h.dominant_role() == "data"
        assert h.is_data_like >= 0.3

    # ----- APB -----

    def test_apb_pready(self):
        """APB: pready = 1-bit input (master 视角)."""
        sig = make_sig("pready", width=1, direction="input", paired=["psel", "penable", "pwrite"])
        det = StructuralRoleDetector()
        all_sigs = [sig, make_sig("psel", width=1, direction="output", paired=["pready"])]
        h = det.detect(sig, all_signals=all_sigs)
        # 1-bit input → ready 主导
        assert h.dominant_role() == "ready"
        assert h.is_ready_like >= 0.4

    def test_apb_pwdata(self):
        sig = make_sig("pwdata", width=32, direction="output", paired=["pwrite", "psel", "penable"])
        det = StructuralRoleDetector()
        all_sigs = [sig, make_sig("pwrite", width=1, direction="output", paired=["pwdata"])]
        h = det.detect(sig, all_signals=all_sigs)
        assert h.dominant_role() == "data"
        assert h.is_data_like >= 0.4


# ---------------------------------------------------------------------------
# StructuralHints 数据结构
# ---------------------------------------------------------------------------

class TestStructuralHints:
    """StructuralHints 数据结构 + 工具方法."""

    def test_default_all_zero(self):
        h = StructuralHints()
        assert h.is_valid_like == 0.0
        assert h.is_ready_like == 0.0
        assert h.is_data_like == 0.0

    def test_dominant_role_returns_highest(self):
        h = StructuralHints(is_valid_like=0.8, is_ready_like=0.3, is_data_like=0.5)
        assert h.dominant_role() == "valid"

    def test_dominant_role_returns_none_when_all_low(self):
        h = StructuralHints()
        # 全 0 时 max=0, 低于阈值 0.3
        assert h.dominant_role() is None

    def test_max_score(self):
        h = StructuralHints(is_valid_like=0.8, is_ready_like=0.3, is_data_like=0.5)
        assert h.max_score() == 0.8

    def test_to_dict(self):
        h = StructuralHints(is_valid_like=0.8)
        d = h.to_dict()
        assert d["is_valid_like"] == 0.8
        assert d["is_ready_like"] == 0.0

    def test_immutable_creation(self):
        """可以用 kwargs 构造."""
        h = StructuralHints(
            is_valid_like=0.7,
            is_data_like=0.5,
        )
        assert h.is_valid_like == 0.7
        assert h.is_data_like == 0.5

    def test_threshold_filter(self):
        """置信度阈值过滤: 低于阈值不计入."""
        h = StructuralHints(is_valid_like=0.2, is_ready_like=0.7)
        # max 是 0.7, dominant = ready
        assert h.dominant_role() == "ready"
        # valid 低于默认阈值 0.3, 在过滤后不应出现
        filtered = h.above_threshold(0.3)
        assert "valid" not in filtered
        assert "ready" in filtered


# ---------------------------------------------------------------------------
# SignalContext 数据结构
# ---------------------------------------------------------------------------

class TestSignalContext:
    def test_minimal(self):
        sig = SignalContext(name="x", width=1, direction="input")
        assert sig.name == "x"
        assert sig.width == 1
        assert sig.direction == "input"
        assert sig.driver_kind == "port"
        assert sig.paired_signals == []

    def test_with_paired(self):
        sig = SignalContext(
            name="valid", width=1, direction="output",
            driver_kind="register", paired_signals=["ready"],
        )
        assert sig.driver_kind == "register"
        assert "ready" in sig.paired_signals

    def test_repr_doesnt_crash(self):
        sig = SignalContext(name="x", width=1, direction="input")
        # 不应崩溃
        assert repr(sig)


# ---------------------------------------------------------------------------
# Detector 工具方法
# ---------------------------------------------------------------------------

class TestDetectorHelpers:
    def test_detect_all_returns_dict(self):
        sigs = [
            make_sig("v", width=1, direction="output", paired=["r"]),
            make_sig("r", width=1, direction="input", paired=["v"]),
        ]
        det = StructuralRoleDetector()
        results = det.detect_all(sigs)
        assert "v" in results
        assert "r" in results
        assert isinstance(results["v"], StructuralHints)
        assert isinstance(results["r"], StructuralHints)

    def test_detect_all_consistent_with_detect(self):
        sigs = [
            make_sig("v", width=1, direction="output", paired=["r"]),
            make_sig("r", width=1, direction="input", paired=["v"]),
        ]
        det = StructuralRoleDetector()
        all_results = det.detect_all(sigs)
        for sig in sigs:
            single = det.detect(sig, all_signals=sigs)
            multi = all_results[sig.name]
            # 在配对信号上分数应该一致
            for role in ["is_valid_like", "is_ready_like"]:
                assert abs(getattr(single, role) - getattr(multi, role)) < 0.01

    def test_custom_thresholds(self):
        """可配置权重 (kwargs 接受合法 boost 名)."""
        sig = make_sig("x", width=1, direction="output", driver_kind="register")
        det = StructuralRoleDetector(valid_register_boost=0.5)
        h = det.detect(sig)
        # 1-bit output register, valid_register_boost 提高 → valid 分数更高
        assert h.is_valid_like >= 0.7


# ---------------------------------------------------------------------------
# 边界 + 性能
# ---------------------------------------------------------------------------

class TestEdgeAndPerformance:
    def test_zero_width_no_crash(self):
        sig = make_sig("x", width=0, direction="input")
        det = StructuralRoleDetector()
        h = det.detect(sig)
        # 不应崩溃, 所有分数应在 [0, 1]
        for score in h._all_scores().values():
            assert 0.0 <= score <= 1.0

    def test_all_scores_in_range(self):
        """任何输入下, 分数都应在 [0, 1]."""
        for w in (0, 1, 8, 32, 1024):
            for d in ("input", "output", "inout"):
                for k in ("port", "register", "wire"):
                    sig = make_sig(f"s_{w}_{d}_{k}", width=w, direction=d, driver_kind=k)
                    det = StructuralRoleDetector()
                    h = det.detect(sig)
                    for score in h._all_scores().values():
                        assert 0.0 <= score <= 1.0, f"OOR: {w}/{d}/{k} → {h._all_scores()}"

    def test_1000_signals_fast(self):
        import time
        sigs = [
            make_sig(f"s_{i}", width=32 if i % 3 == 0 else 1,
                     direction="output" if i % 2 == 0 else "input",
                     paired=[f"s_{i+1}"] if i % 5 == 0 else [])
            for i in range(1000)
        ]
        det = StructuralRoleDetector()
        start = time.time()
        det.detect_all(sigs)
        elapsed = time.time() - start
        assert elapsed < 0.5
