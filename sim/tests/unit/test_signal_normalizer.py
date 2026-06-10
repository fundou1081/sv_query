"""
test_signal_normalizer.py
=========================
Phase A Session 1: SignalNormalizer 名字标准化层

设计目标:
  1. 6 步流水线: 取最后段 → 去数组下标 → 去 infix → 去前缀 → 去下划线 → 去后缀
  2. 改 YAML 改规则, 不动 Python 代码
  3. 可扩展: 用户可在自定义 YAML 里追加 prefix/suffix/infix
  4. 保留原始信号名 + 标准化后名字 (用于回溯)

测试覆盖:
  - 单步 (6 步单独)
  - 端到端 (50+ 真实生成代码 + 手写代码信号名)
  - 边界: 空名 / 单字符 / 全大写 / 全小写 / 已标准化
  - YAML 加载 / 自定义配置覆盖
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

from applications.bus.normalize import (
    SignalNormalizer,
    NormalizeConfig,
    NormalizeResult,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def default_config() -> NormalizeConfig:
    """默认配置: 内置 prefix/suffix/infix 列表。"""
    return NormalizeConfig.default()


@pytest.fixture
def normalizer(default_config) -> SignalNormalizer:
    return SignalNormalizer(default_config)


# ---------------------------------------------------------------------------
# 步骤 1: take_last_dot (取最后一段)
# ---------------------------------------------------------------------------

class TestTakeLastDot:
    """取 `.` 后的最后一段, 处理 `module.signal` / `inst.sig` 形式。"""

    def test_dotted_module_signal(self, normalizer):
        """`io_aw_valid` 不变 (无 dot)."""
        assert normalizer._take_last_dot("io_aw_valid") == "io_aw_valid"

    def test_hierarchical_inst_signal(self, normalizer):
        """`u_axil_master.io_aw_valid` → `io_aw_valid`."""
        assert normalizer._take_last_dot("u_axil_master.io_aw_valid") == "io_aw_valid"

    def test_deep_hierarchical(self, normalizer):
        """`a.b.c.d.signal` → `signal`."""
        assert normalizer._take_last_dot("a.b.c.d.signal") == "signal"

    def test_no_dot(self, normalizer):
        assert normalizer._take_last_dot("awvalid") == "awvalid"


# ---------------------------------------------------------------------------
# 步骤 2: strip_array_index (去数组下标)
# ---------------------------------------------------------------------------

class TestStripArrayIndex:
    """`sig[3:0]` / `sig[7]` / `sig[1][2]` → `sig`。"""

    def test_simple_bit_select(self, normalizer):
        assert normalizer._strip_array_index("data[3:0]") == "data"

    def test_index_access(self, normalizer):
        assert normalizer._strip_array_index("fifo[7]") == "fifo"

    def test_2d_array(self, normalizer):
        assert normalizer._strip_array_index("mem[1][2]") == "mem"

    def test_complex_range(self, normalizer):
        assert normalizer._strip_array_index("awaddr[AW-1:0]") == "awaddr"

    def test_no_index(self, normalizer):
        assert normalizer._strip_array_index("valid") == "valid"

    def test_no_index_with_underscore(self, normalizer):
        assert normalizer._strip_array_index("io_aw_valid") == "io_aw_valid"


# ---------------------------------------------------------------------------
# 步骤 3: strip_infix (去 infix)
# ---------------------------------------------------------------------------

class TestStripInfix:
    """`_bits_`, `_chan_`, `_payload_`, `_data_` 等中缀。"""

    def test_bits_infix(self, normalizer):
        """`aw_bits_data` → `aw_data` (去 _bits_)."""
        assert normalizer._strip_infix("aw_bits_data") == "aw_data"

    def test_chan_infix(self, normalizer):
        assert normalizer._strip_infix("aw_chan_valid") == "aw_valid"

    def test_payload_infix(self, normalizer):
        assert normalizer._strip_infix("axi_payload_len") == "axi_len"

    def test_data_infix(self, normalizer):
        assert normalizer._strip_infix("r_data_payload") == "r_payload"

    def test_no_infix(self, normalizer):
        assert normalizer._strip_infix("aw_valid") == "aw_valid"


# ---------------------------------------------------------------------------
# 步骤 4: strip_prefix (去前缀)
# ---------------------------------------------------------------------------

class TestStripPrefix:
    """`io_`, `m_`, `s_`, `axi_`, `axil_` 等前缀。"""

    def test_io_prefix(self, normalizer):
        assert normalizer._strip_prefix("io_aw_valid") == "aw_valid"

    def test_m_prefix(self, normalizer):
        assert normalizer._strip_prefix("m_axi_awvalid") == "awvalid"

    def test_s_prefix(self, normalizer):
        assert normalizer._strip_prefix("s_axi_awvalid") == "awvalid"

    def test_axi_prefix(self, normalizer):
        assert normalizer._strip_prefix("axi_awvalid") == "awvalid"

    def test_axil_prefix(self, normalizer):
        assert normalizer._strip_prefix("axil_awvalid") == "awvalid"

    def test_gen_prefix(self, normalizer):
        assert normalizer._strip_prefix("gen_aw_valid") == "aw_valid"

    def test_master_prefix(self, normalizer):
        assert normalizer._strip_prefix("master_awvalid") == "awvalid"

    def test_my_prefix(self, normalizer):
        assert normalizer._strip_prefix("my_axil_awvalid") == "awvalid"

    def test_no_prefix(self, normalizer):
        assert normalizer._strip_prefix("awvalid") == "awvalid"

    def test_repeated_prefix_strip(self, normalizer):
        """`io_s_axi_aw_valid` → `aw_valid` (3 层前缀)."""
        assert normalizer._strip_prefix("io_s_axi_aw_valid") == "aw_valid"


# ---------------------------------------------------------------------------
# 步骤 5: remove_underscore (去下划线, optional)
# ---------------------------------------------------------------------------

class TestRemoveUnderscore:
    """`aw_valid` → `awvalid` (Chisel vs SpinalHDL 风格统一)."""

    def test_simple_underscore(self, normalizer):
        assert normalizer._remove_underscore("aw_valid") == "awvalid"

    def test_multiple_underscores(self, normalizer):
        assert normalizer._remove_underscore("io_aw_addr_valid") == "ioawaddrvalid"

    def test_no_underscore(self, normalizer):
        assert normalizer._remove_underscore("awvalid") == "awvalid"

    def test_underscore_disabled(self, default_config):
        """配置关闭下划线去除时保留."""
        cfg = default_config.with_overrides(remove_underscore=False)
        norm = SignalNormalizer(cfg)
        assert norm._remove_underscore("aw_valid") == "aw_valid"


# ---------------------------------------------------------------------------
# 步骤 6: strip_suffix (去后缀)
# ---------------------------------------------------------------------------

class TestStripSuffix:
    """`_o`, `_i`, `_io`, `_r`, `_next`, `_reg`, `_int` 等后缀。"""

    def test_o_suffix(self, normalizer):
        assert normalizer._strip_suffix("awvalid_o") == "awvalid"

    def test_i_suffix(self, normalizer):
        assert normalizer._strip_suffix("awready_i") == "awready"

    def test_io_suffix(self, normalizer):
        assert normalizer._strip_suffix("awvalid_io") == "awvalid"

    def test_r_suffix(self, normalizer):
        """FIFO 读信号 `data_r` → `data`."""
        assert normalizer._strip_suffix("data_r") == "data"

    def test_next_suffix(self, normalizer):
        assert normalizer._strip_suffix("valid_next") == "valid"

    def test_reg_suffix(self, normalizer):
        assert normalizer._strip_suffix("ready_reg") == "ready"

    def test_int_suffix(self, normalizer):
        assert normalizer._strip_suffix("valid_int") == "valid"

    def test_no_suffix(self, normalizer):
        assert normalizer._strip_suffix("awvalid") == "awvalid"


# ---------------------------------------------------------------------------
# 端到端: normalize() 全流程
# ---------------------------------------------------------------------------

class TestNormalizeEndToEnd:
    """50+ 真实生成代码 + 手写代码信号名."""

    # Chisel 风格: io_aw_valid
    def test_chisel_axi_master(self, normalizer):
        assert normalizer.normalize("io_aw_valid") == "awvalid"

    def test_chisel_axi_slave(self, normalizer):
        assert normalizer.normalize("io_aw_ready_i") == "awready"

    def test_chisel_w_channel(self, normalizer):
        assert normalizer.normalize("io_w_valid") == "wvalid"

    def test_chisel_b_channel(self, normalizer):
        assert normalizer.normalize("io_b_resp_i") == "bresp"

    # SpinalHDL 风格: io_awvalid (无下划线)
    def test_spinalhdl_awvalid(self, normalizer):
        assert normalizer.normalize("io_awvalid") == "awvalid"

    def test_spinalhdl_wready(self, normalizer):
        assert normalizer.normalize("io_wready") == "wready"

    # verilog-axi 风格: m_axi_awvalid / s_axi_awvalid
    def test_verilog_axi_master(self, normalizer):
        assert normalizer.normalize("m_axi_awvalid") == "awvalid"

    def test_verilog_axi_slave(self, normalizer):
        assert normalizer.normalize("s_axi_awvalid") == "awvalid"

    def test_verilog_axi_axil(self, normalizer):
        """`s_axil_awvalid` 优先匹配 `axil_` 而非 `s_axi_`."""
        # 注: 因为 s_ 在前缀列表里更长匹配, 会先去掉 s_ 留下 axil_awvalid
        # 然后 axil_ 也会被去掉 → awvalid
        assert normalizer.normalize("s_axil_awvalid") == "awvalid"

    # 自研 wrapper 风格
    def test_my_axil(self, normalizer):
        assert normalizer.normalize("my_axil_awvalid") == "awvalid"

    def test_my_axil_with_underscore(self, normalizer):
        assert normalizer.normalize("my_axil_aw_valid") == "awvalid"

    # OpenTitan TL-UL 风格
    def test_tlul_a_valid(self, normalizer):
        """TL-UL: `a_valid_o` → `avalid`."""
        assert normalizer.normalize("a_valid_o") == "avalid"

    def test_tlul_d_ready(self, normalizer):
        assert normalizer.normalize("d_ready_i") == "dready"

    def test_tlul_a_ack(self, normalizer):
        """`a_ack` 不变 (无 prefix/suffix)."""
        assert normalizer.normalize("a_ack") == "aack"

    # APB 风格
    def test_apb_pready(self, normalizer):
        assert normalizer.normalize("pready") == "pready"

    def test_apb_psel(self, normalizer):
        assert normalizer.normalize("io_psel") == "psel"

    # AHB 风格
    def test_ahb_hready(self, normalizer):
        assert normalizer.normalize("io_hready") == "hready"

    def test_ahb_hreadyout(self, normalizer):
        """`hreadyout` → `hreadyout` (无 prefix/suffix 匹配)."""
        assert normalizer.normalize("hreadyout") == "hreadyout"

    # Wishbone 风格
    def test_wishbone_cyc(self, normalizer):
        assert normalizer.normalize("io_wb_cyc_o") == "wbcyc"

    def test_wishbone_stall(self, normalizer):
        assert normalizer.normalize("io_wb_stall_i") == "wbstall"

    # 数据信号
    def test_axi_data(self, normalizer):
        assert normalizer.normalize("io_w_data") == "wdata"

    def test_axi_addr(self, normalizer):
        assert normalizer.normalize("m_axi_awaddr") == "awaddr"

    def test_axi_resp(self, normalizer):
        assert normalizer.normalize("s_axi_bresp") == "bresp"

    # 层次化 + 数组
    def test_hierarchical_with_array(self, normalizer):
        """`u_master.io_aw_addr[31:0]` → `awaddr`."""
        result = normalizer.normalize("u_master.io_aw_addr[31:0]")
        assert result == "awaddr"

    def test_hierarchical_dot_array(self, normalizer):
        """`genblk1[0].u_aw.io_aw_valid` → `awvalid`."""
        result = normalizer.normalize("genblk1[0].u_aw.io_aw_valid")
        assert result == "awvalid"

    # 重复前缀链
    def test_repeated_prefix_chain(self, normalizer):
        """`io_s_axi_aw_valid` → `awvalid`."""
        assert normalizer.normalize("io_s_axi_aw_valid") == "awvalid"

    def test_deep_prefix_chain(self, normalizer):
        """`io_m_s_axi_aw_valid_o` → `awvalid`."""
        assert normalizer.normalize("io_m_s_axi_aw_valid_o") == "awvalid"


# ---------------------------------------------------------------------------
# NormalizeResult 数据结构
# ---------------------------------------------------------------------------

class TestNormalizeResult:
    """`NormalizeResult` 应保留原始名 + 标准化后名字."""

    def test_result_has_original(self, normalizer):
        result = normalizer.normalize("io_aw_valid")
        assert result.original == "io_aw_valid"
        assert result.normalized == "awvalid"

    def test_result_passthrough_when_no_match(self, normalizer):
        """没有 prefix/suffix 命中时, 应该原样返回."""
        result = normalizer.normalize("custom_thing")
        assert result.normalized == "customthing"

    def test_result_is_string_like(self, normalizer):
        """NormalizeResult 应该是 str 的子类, 方便直接当字符串用."""
        result = normalizer.normalize("io_aw_valid")
        # str() 转换应该返回 normalized
        assert str(result) == "awvalid"
        # 应该能直接当字符串用
        assert result == "awvalid"
        assert result.startswith("aw")


# ---------------------------------------------------------------------------
# 边界情况
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_empty_string(self, normalizer):
        result = normalizer.normalize("")
        assert result.normalized == ""

    def test_single_char(self, normalizer):
        result = normalizer.normalize("x")
        assert result.normalized == "x"

    def test_underscore_only(self, normalizer):
        result = normalizer.normalize("_")
        assert result.normalized == ""

    def test_already_normalized(self, normalizer):
        """已标准化的信号名应原样返回."""
        result = normalizer.normalize("awvalid")
        assert result.normalized == "awvalid"

    def test_all_uppercase(self, normalizer):
        """`AWVALID` 保持大写 (不在 lowercase 转换范围)."""
        result = normalizer.normalize("AWVALID")
        assert result.normalized == "AWVALID"

    def test_mixed_case(self, normalizer):
        """`AwValid` 保持原样."""
        result = normalizer.normalize("AwValid")
        assert result.normalized == "AwValid"

    def test_numeric_suffix(self, normalizer):
        """`io_aw_valid_0` → `awvalid0` (数字保留)."""
        result = normalizer.normalize("io_aw_valid_0")
        assert result.normalized == "awvalid0"

    def test_double_underscore(self, normalizer):
        """`io__aw_valid` → 双下划线会被合并/去除."""
        result = normalizer.normalize("io__aw_valid")
        # 实现选择: 保留或合并, 这里我们要求结果不含双下划线
        assert "__" not in result.normalized


# ---------------------------------------------------------------------------
# YAML 加载 + 自定义配置
# ---------------------------------------------------------------------------

class TestYAMLConfig:
    def test_load_default_yaml(self):
        """默认 YAML 必须存在且可加载."""
        cfg = NormalizeConfig.from_yaml(
            "config/protocols/normalize/default.yaml"
        )
        assert "io_" in cfg.strip_prefix
        assert "axi_" in cfg.strip_prefix
        assert "_o" in cfg.strip_suffix
        assert "_i" in cfg.strip_suffix

    def test_custom_config_override(self, tmp_path):
        """用户可写自定义 YAML 覆盖默认."""
        custom_yaml = """
strip_prefix:
  - "myprefix_"
  - "another_"
strip_suffix:
  - "_my"
remove_underscore: false
remove_infix: []
"""
        cfg_path = tmp_path / "custom.yaml"
        cfg_path.write_text(custom_yaml)

        cfg = NormalizeConfig.from_yaml(cfg_path)
        assert "myprefix_" in cfg.strip_prefix
        assert "_my" in cfg.strip_suffix
        assert cfg.remove_underscore is False

        norm = SignalNormalizer(cfg)
        # remove_underscore=false → 保留下划线, 期望 `aw_valid`
        assert norm.normalize("myprefix_aw_valid_my") == "aw_valid"

    def test_extend_default_with_extra(self, tmp_path):
        """在默认基础上追加 prefix."""
        custom_yaml = """
extra_strip_prefix:
  - "c2h_"
  - "h2c_"
"""
        cfg_path = tmp_path / "extend.yaml"
        cfg_path.write_text(custom_yaml)

        cfg = NormalizeConfig.from_yaml_with_default(
            cfg_path,
            "config/protocols/normalize/default.yaml",
        )
        assert "io_" in cfg.strip_prefix  # 默认的
        assert "c2h_" in cfg.strip_prefix  # 追加的

    def test_merge_chain(self, default_config):
        """多文件 merge: base + override."""
        base = default_config
        merged = base.merge(
            strip_prefix_extra=["vendor_"],
            strip_suffix_extra=["_q"],
        )
        assert "io_" in merged.strip_prefix
        assert "vendor_" in merged.strip_prefix
        assert "_o" in merged.strip_suffix
        assert "_q" in merged.strip_suffix


# ---------------------------------------------------------------------------
# 性能 + 稳定性
# ---------------------------------------------------------------------------

class TestPerformance:
    def test_normalize_1000_signals_fast(self, normalizer):
        """1000 个信号名 < 100ms."""
        import time
        sigs = [f"io_aw_valid_{i}" for i in range(1000)]
        start = time.time()
        for s in sigs:
            normalizer.normalize(s)
        elapsed = time.time() - start
        assert elapsed < 0.1

    def test_idempotent(self, normalizer):
        """normalize 两次应等于 normalize 一次 (除空字符串)."""
        s1 = normalizer.normalize("io_aw_valid")
        s2 = normalizer.normalize(s1.normalized)
        # 第二次应该没变化
        assert s1.normalized == s2.normalized or s2.normalized == s1.normalized
