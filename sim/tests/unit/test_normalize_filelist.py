"""
test_normalize_filelist.py
=============================
修复: filelist 多模块场景下 verilog-axi 命名变体

Bug: verilog-axi 的 slave port 命名是 `s_axi_a_awvalid` (多一层 channel letter
     prefix: a/w/b/ar/r), 标准化后变成 `aawvalid` / `wwready` 等, 与
     schema 期待的 `awvalid` / `wready` 不匹配, 导致 AXI4 评分 0/0/0/0.

Root cause: default.yaml 的 strip_prefix 有 `s_axi_` 但没有 `s_axi_a_` 等
            更具体的子前缀. 标准化后剩 `a_` 单字符前缀, 不再 strip.

修复: 在 default.yaml 的 strip_prefix 加 verilog-axi channel prefix:
      `s_axi_a_`, `s_axi_w_`, `s_axi_b_`, `s_axi_ar_`, `s_axi_r_`
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

from trace.core.protocol.normalize import SignalNormalizer, NormalizeConfig


@pytest.fixture
def default_normalizer():
    """从 default.yaml 加载的标准 normalizer (真实生产配置)."""
    config_path = Path(__file__).parent.parent.parent.parent / "config" / "protocols" / "normalize" / "default.yaml"
    cfg = NormalizeConfig.from_yaml(config_path)
    return SignalNormalizer(cfg)


class TestVerilogAxiChannelPrefix:
    """verilog-axi slave port 命名: s_axi_<channel>_<signal>."""

    @pytest.mark.parametrize("raw,expected", [
        # Write address channel
        ("s_axi_a_awvalid", "awvalid"),
        ("s_axi_a_awready", "awready"),
        ("s_axi_a_awaddr", "awaddr"),
        ("s_axi_a_awlen", "awlen"),
        ("s_axi_a_awsize", "awsize"),
        # Write data channel
        ("s_axi_w_wvalid", "wvalid"),
        ("s_axi_w_wready", "wready"),
        ("s_axi_w_wdata", "wdata"),
        ("s_axi_w_wstrb", "wstrb"),
        ("s_axi_w_wlast", "wlast"),
        # Write response channel
        ("s_axi_b_bvalid", "bvalid"),
        ("s_axi_b_bready", "bready"),
        ("s_axi_b_bresp", "bresp"),
        # Read address channel
        ("s_axi_ar_arvalid", "arvalid"),
        ("s_axi_ar_arready", "arready"),
        ("s_axi_ar_araddr", "araddr"),
        # Read data channel
        ("s_axi_r_rvalid", "rvalid"),
        ("s_axi_r_rready", "rready"),
        ("s_axi_r_rdata", "rdata"),
        ("s_axi_r_rlast", "rlast"),
    ])
    def test_channel_prefix_stripped(self, default_normalizer, raw, expected):
        """verilog-axi s_axi_<ch>_<sig> → <sig>."""
        result = default_normalizer.normalize(raw)
        assert result.normalized == expected, (
            f"{raw!r} → {result.normalized!r} (expected {expected!r})"
        )


class TestVerilogAxiRegression:
    """确保修复不影响已有 verilog-axi 命名."""

    @pytest.mark.parametrize("raw,expected", [
        # 已有 m_axi_ / s_axi_ 风格 (单层, 不变)
        ("m_axi_awvalid", "awvalid"),
        ("s_axi_awvalid", "awvalid"),
        ("m_axi_wready", "wready"),
        ("s_axi_wready", "wready"),
        # Chisel / SpinalHDL
        ("io_m_axi_awvalid", "awvalid"),
        ("io_s_axi_awready", "awready"),
        # AXI4-Lite
        ("s_axil_awvalid", "awvalid"),
        ("m_axil_awvalid", "awvalid"),
        # AXI4-Stream
        ("s_axis_tvalid", "tvalid"),
        ("m_axis_tready", "tready"),
        # OpenTitan TileLink (channel prefix a/d/h + suffix _o/_i)
        ("tl_a_valid_o", "tlavalid"),
        ("tl_h_valid_o", "tlhvalid"),
        ("tl_a_ready_i", "tlaready"),
    ])
    def test_existing_naming_unchanged(self, default_normalizer, raw, expected):
        """回归测试: 已支持的命名不能被破坏."""
        result = default_normalizer.normalize(raw)
        assert result.normalized == expected, (
            f"{raw!r} → {result.normalized!r} (regression: expected {expected!r})"
        )


class TestStripPrefixOrdering:
    """strip_prefix 必须按长度降序匹配, 短 prefix 不能在长 prefix 之前吃."""

    def test_longest_prefix_wins(self, default_normalizer):
        """s_axi_a_ 必须在 s_axi_ 之前匹配, 否则会留下 a_."""
        result = default_normalizer.normalize("s_axi_a_awvalid")
        # 如果 s_axi_ 先匹配, 会留 'a_awvalid'
        assert result.normalized != "a_awvalid"
        assert result.normalized == "awvalid"


class TestDefaultConfigParity:
    """NormalizeConfig.default() 必须与 config/protocols/normalize/default.yaml 同步.

    Bug 教训: 2026-06-11 发现 CLI 走 default() 而不是 yaml, 导致 verilog-axi dual-port
    (s_axi_a_*) 不识别. 修复加测试确保不再 drift.
    """

    def test_default_includes_verilog_axi_channel_prefix(self):
        """default() 必须包含 verilog-axi dual-port channel prefix.

        这 5 个 prefix 处理 axi_dp_ram 等 dual-port 风格:
          s_axi_a_  s_axi_w_  s_axi_b_  s_axi_ar_  s_axi_r_
        """
        cfg = NormalizeConfig.default()
        for prefix in ("s_axi_a_", "s_axi_w_", "s_axi_b_", "s_axi_ar_", "s_axi_r_"):
            assert prefix in cfg.strip_prefix, (
                f"NormalizeConfig.default() missing '{prefix}' — "
                f"yaml/config may have drifted. Sync both!"
            )

    def test_default_and_yaml_have_same_verilog_axi_prefixes(self):
        """default() 和 yaml 必须有相同的 verilog-axi prefix 集合 (双向包含)."""
        default_cfg = NormalizeConfig.default()
        yaml_cfg = NormalizeConfig.from_yaml(
            Path(__file__).parent.parent.parent.parent / "config" / "protocols" / "normalize" / "default.yaml"
        )
        # verilog-axi 相关 prefix
        verilog_axi_prefixes = {"s_axi_a_", "s_axi_w_", "s_axi_b_", "s_axi_ar_", "s_axi_r_"}
        for p in verilog_axi_prefixes:
            assert p in default_cfg.strip_prefix, f"default() missing {p}"
            assert p in yaml_cfg.strip_prefix, f"yaml missing {p}"

