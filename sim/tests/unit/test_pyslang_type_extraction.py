"""
test_pyslang_type_extraction.py
=================================
[Phase 1 2026-06-24] 测试 parse_width_from_pyslang 工具函数在各种
SystemVerilog type 构造上的能力.

基于 sim/tests/pyslang_type_fixtures/type_taxonomy.sv:
  - 1-bit scalar (logic)
  - 1D vector with literal/parameter/arithmetic width
  - $clog2 derived parameters
  - 2D packed array
  - Unpacked array of logic
  - Package typedef → logic / enum / packed struct / packed union
  - Module-scope typedef
  - Nested typedef (typedef → typedef)

每种 case 都注释 [W=N] (金标准). 测试 assert (width, hi, lo) 完全一致.

Fixture: sim/tests/pyslang_type_fixtures/conftest.py 提供共享 helper
+ 工业项目 skip 逻辑.
"""
import os
import sys
from pathlib import Path

# 让 test 找得到 conftest 里的 helper
PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT / "sim" / "tests" / "pyslang_type_fixtures"))

import pytest

# multi_pkg test 用的 fixture 路径 (a_pkg.f)
A_PKG_FILELIST = Path(__file__).resolve().parents[3] / "sim" / "tests" / "pyslang_type_fixtures" / "a_pkg.f"


# ============================================================================
# 黄金标准: (sig_name, expected_width, expected_hi, expected_lo, scenario)
# ============================================================================
# 每个 case 是 type_taxonomy.sv 里的一个 signal 加上它的金标准 width.
# 测试 runtime 调 parse_width_from_pyslang 看是否能拿到 (W, hi, lo).
# ============================================================================

TYPE_TAXONOMY_CASES = [
    # --- 1-bit scalar ---
    ("clk",        1,  0, 0, "1-bit scalar (logic)"),
    ("rst_n",      1,  0, 0, "1-bit scalar (logic)"),
    ("enable_i",   1,  0, 0, "1-bit scalar (logic)"),
    ("valid_i",    1,  0, 0, "1-bit scalar (logic)"),
    ("ready_o",    1,  0, 0, "1-bit scalar (logic)"),
    ("trig_i",     1,  0, 0, "1-bit scalar (logic)"),

    # --- 1D vector with literal width ---
    # (sel_i 是 [3:0] → 4-bit)

    # --- 1D vector with parameter width ---
    ("data_i",     32, 31, 0, "1D logic[WIDTH-1:0] (WIDTH=32)"),
    ("data_o",     32, 31, 0, "1D logic[WIDTH-1:0] (WIDTH=32)"),
    ("half_i",     16, 15, 0, "1D logic[WIDTH/2-1:0] (WIDTH=32, /2=16)"),
    ("quarter_o",  8,  7, 0, "1D logic[WIDTH/4-1:0] (WIDTH=32, /4=8)"),
    ("src_i",      32, 31, 0, "1D logic[N_SRC-1:0] (N_SRC=32)"),

    # --- $clog2 derived ---
    ("depth_idx_i", 2,  1, 0, "$clog2(DEPTH)=2 (DEPTH=4)"),
    ("count_idx_o", 3,  2, 0, "$clog2(COUNT)=3 (COUNT=8)"),
    ("src_idx_o",   5,  4, 0, "$clog2(N_SRC)=5 (N_SRC=32)"),

    # --- package typedef → logic ---
    ("word_i",     32, 31, 0, "typedef word_t → logic[31:0]"),
    ("word_o",     32, 31, 0, "typedef word_t → logic[31:0]"),
    ("halfword_i", 16, 15, 0, "typedef halfword_t → logic[15:0]"),
    ("byte_i",     8,  7, 0, "typedef byte_t → logic[7:0]"),

    # --- package typedef → enum ---
    ("state_i",    2,  1, 0, "typedef enum state_t (4 vals, ceil(log2(4))=2)"),
    ("state_o",    2,  1, 0, "typedef enum state_t (4 vals)"),

    # --- package typedef → packed struct ---
    ("instr_i",    32, 31, 0, "typedef packed struct (8+24=32)"),
    ("instr_o",    32, 31, 0, "typedef packed struct (8+24=32)"),

    # --- package typedef → packed union ---
    ("word_u_i",   32, 31, 0, "typedef packed union (max(32, 32)=32)"),
    ("word_u_o",   32, 31, 0, "typedef packed union (max(32, 32)=32)"),

    # --- nested typedef (typedef → typedef) ---
    ("cached_word_i", 32, 31, 0, "typedef cached_word_t → word_t → logic[31:0]"),
    ("cached_state_o", 2,  1, 0, "typedef cached_state_t → state_t (2-bit enum)"),

    # --- 2D packed array (外层宽度) ---
    ("matrix_i",   4,  3, 0, "2D logic[DEPTH-1:0][WIDTH-1:0] (外层=4)"),
    ("bytes_o",    8,  7, 0, "2D logic[COUNT-1:0][7:0] (外层=8)"),

    # --- 内部 signals ---
    ("pipe_q",     32, 31, 0, "internal logic[WIDTH-1:0]"),
    ("half_q",     16, 15, 0, "internal logic[WIDTH/2-1:0]"),
    ("depth_idx_q", 2,  1, 0, "internal $clog2(DEPTH)"),
    ("count_idx_q", 3,  2, 0, "internal $clog2(COUNT)"),
    ("src_idx_q",   5,  4, 0, "internal $clog2(N_SRC)"),
    ("fsm_q",      2,  1, 0, "internal typedef state_t"),
    ("decoded_q",  32, 31, 0, "internal typedef instr_t (packed struct)"),
    ("word_u_q",   32, 31, 0, "internal typedef word_u (packed union)"),

    # --- module-scope typedef ---
    ("local_reg",  32, 31, 0, "module-scope typedef local_word_t"),

    # --- unpacked array (取 packed 维度) ---
    ("mem",          8,  7, 0, "unpacked array `logic[7:0] mem[DEPTH]` → packed 维度 8-bit"),
]


# ============================================================================
# 测试 1: parse_width_from_pyslang 在 type_taxonomy 跑全场景
# ============================================================================
class TestPyslangTypeExtraction:
    """parse_width_from_pyslang 全面 type 场景测试."""

    @pytest.mark.parametrize(
        "sig_name,exp_w,exp_hi,exp_lo,scenario",
        TYPE_TAXONOMY_CASES,
        ids=[c[0] + " (" + c[4] + ")" for c in TYPE_TAXONOMY_CASES],
    )
    def test_type_taxonomy_signal(
        self, type_taxonomy_sv, parse_pyslang_width,
        sig_name, exp_w, exp_hi, exp_lo, scenario,
    ):
        """type_taxonomy.sv 里每个 signal 都能解析成 (W, hi, lo)."""
        result = parse_pyslang_width(
            sig_name, file=str(type_taxonomy_sv)
        )
        assert result is not None, (
            f"[{scenario}] parse_width_from_pyslang('{sig_name}') returned None — "
            f"expected ({exp_w}, {exp_hi}, {exp_lo})"
        )
        w, hi, lo = result
        assert w == exp_w and hi == exp_hi and lo == exp_lo, (
            f"[{scenario}] {sig_name}: got ({w}-bit [{hi}:{lo}]), "
            f"expected ({exp_w}-bit [{exp_hi}:{exp_lo}])"
        )

    def test_unpacked_array_packed_dim(self, type_taxonomy_sv, parse_pyslang_width):
        """unpacked array `logic [7:0] mem [DEPTH]` 取 packed 维度 = 8-bit."""
        result = parse_pyslang_width("mem", file=str(type_taxonomy_sv))
        assert result is not None, "mem signal not found"
        w, hi, lo = result
        assert (w, hi, lo) == (8, 7, 0), (
            f"unpacked array should yield packed dim 8-bit, got ({w}, {hi}, {lo})"
        )


# ============================================================================
# 测试 2: _parse_logic_type_str 单元测试
# ============================================================================
class TestParseLogicTypeStr:
    """_parse_logic_type_str 字符串解析单元测试 (不依赖 sv_query)."""

    @pytest.mark.parametrize("type_str,exp_w,exp_hi,exp_lo", [
        ("logic",            1,  0, 0),   # 1-bit scalar
        ("bit",              1,  0, 0),   # 1-bit scalar
        ("reg",              1,  0, 0),   # 1-bit scalar
        ("logic[15:0]",     16, 15, 0),   # 1D vector
        ("logic[31:0]",     32, 31, 0),   # 1D vector
        ("logic[4:0]",       5,  4, 0),   # 1D vector (5-bit)
        ("logic[0:0]",       1,  0, 0),   # 1-bit packed
        ("logic[3:0][31:0]", 4,  3, 0),   # 2D packed (外层)
        ("logic[7:0]$[0:3]", 8,  7, 0),   # unpacked array (取 packed dim)
        ("logic[1:0][7:0]",  2,  1, 0),   # 2D packed
    ])
    def test_valid_type_strings(self, parse_logic_type_str, type_str, exp_w, exp_hi, exp_lo):
        """已知 type 字符串都解析正确."""
        r = parse_logic_type_str(type_str)
        assert r is not None, f"{type_str!r} should parse"
        hi, lo = r
        w = hi - lo + 1
        assert (w, hi, lo) == (exp_w, exp_hi, exp_lo)

    @pytest.mark.parametrize("type_str", [
        "types_pkg::word_t",        # package typedef (单独看 — 拿不到 underlying)
        "struct packed{...}",       # packed struct (单独看 — 缺字段)
        "",                          # 空字符串
    ])
    def test_unsupported_type_strings(self, parse_logic_type_str, type_str):
        """未支持的 type 字符串返回 None (不是 crash)."""
        r = parse_logic_type_str(type_str)
        assert r is None, f"{type_str!r} should NOT parse, got {r}"


# ============================================================================
# 测试 3: OpenTitan prim_max_tree 工业 IP ($clog2 + nested typedef)
# ============================================================================
class TestOpenTitanPrimMaxTree:
    """[Gold] OpenTitan 工业 IP: $clog2 derived + parameter int."""

    @pytest.fixture(scope="class")
    def width_results(self, opentitan_prim_max_tree_filelist, parse_pyslang_width):
        """对 prim_max_tree 5 个关键 signal 跑 parse_width_from_pyslang."""
        return {
            sig: parse_pyslang_width(sig, filelist=str(opentitan_prim_max_tree_filelist))
            for sig in ["max_idx_o", "max_value_o", "values_i", "valid_i", "clk_i"]
        }

    def test_max_idx_o_clog2_5bit(self, width_results):
        """max_idx_o: localparam SrcWidth = $clog2(32) = 5."""
        r = width_results["max_idx_o"]
        assert r is not None and r == (5, 4, 0), f"max_idx_o: got {r}, expected (5, 4, 0)"

    def test_max_value_o_param_8bit(self, width_results):
        """max_value_o: parameter int Width = 8."""
        r = width_results["max_value_o"]
        assert r is not None and r == (8, 7, 0), f"max_value_o: got {r}, expected (8, 7, 0)"

    def test_values_i_nested_32bit(self, width_results):
        """values_i: [NumSrc-1:0][Width-1:0] (外层 = 32)."""
        r = width_results["values_i"]
        assert r is not None and r == (32, 31, 0), f"values_i: got {r}, expected (32, 31, 0)"

    def test_valid_i_1d_32bit(self, width_results):
        """valid_i: [NumSrc-1:0] = 32-bit."""
        r = width_results["valid_i"]
        assert r is not None and r == (32, 31, 0), f"valid_i: got {r}, expected (32, 31, 0)"

    def test_clk_i_1bit(self, width_results):
        """clk_i: 1-bit scalar."""
        r = width_results["clk_i"]
        assert r is not None and r == (1, 0, 0), f"clk_i: got {r}, expected (1, 0, 0)"


# ============================================================================
# 测试 4: NaplesPU 工业 IP (4-level chained include)
# ============================================================================
class TestNaplesPULogger:
    """[Gold] NaplesPU npu_core_logger: 4 层链式 include + typedef package."""

    @pytest.fixture(scope="class")
    def width_results(self, naplespu_logger_filelist, parse_pyslang_width):
        return {
            sig: parse_pyslang_width(sig, filelist=str(naplespu_logger_filelist))
            for sig in ["events_counter", "core_current_elem", "mem_current_elem",
                        "mc_address_i", "clk", "reset"]
        }

    def test_events_counter_32bit(self, width_results):
        """events_counter: logic [31:0]."""
        r = width_results["events_counter"]
        assert r is not None and r == (32, 31, 0), f"got {r}"

    def test_mc_address_i_32bit_input(self, width_results):
        """mc_address_i: 32-bit input port."""
        r = width_results["mc_address_i"]
        assert r is not None and r == (32, 31, 0), f"got {r}"

    def test_clk_1bit(self, width_results):
        """clk: 1-bit scalar."""
        r = width_results["clk"]
        assert r is not None and r == (1, 0, 0), f"got {r}"


# ============================================================================
# 测试 5: PicoRV32 工业 RISC-V CPU
# ============================================================================
class TestPicoRV32:
    """[Gold] PicoRV32: 3049 行 Verilog, 真实工业 RISC-V CPU."""

    @pytest.fixture(scope="class")
    def width_results(self, picorv32_filelist, parse_pyslang_width):
        return {
            sig: parse_pyslang_width(sig, filelist=str(picorv32_filelist))
            for sig in ["mem_addr", "mem_wdata", "mem_wstrb", "mem_valid",
                        "pcpi_insn", "trap", "irq", "mem_ready", "clk"]
        }

    def test_mem_addr_32bit(self, width_results):
        """mem_addr: output reg [31:0]."""
        r = width_results["mem_addr"]
        assert r is not None and r == (32, 31, 0), f"got {r}"

    def test_mem_wdata_32bit(self, width_results):
        """mem_wdata: output reg [31:0]."""
        r = width_results["mem_wdata"]
        assert r is not None and r == (32, 31, 0), f"got {r}"

    def test_mem_wstrb_4bit(self, width_results):
        """mem_wstrb: output reg [3:0]."""
        r = width_results["mem_wstrb"]
        assert r is not None and r == (4, 3, 0), f"got {r}"

    def test_mem_valid_1bit(self, width_results):
        """mem_valid: 1-bit VLD-style."""
        r = width_results["mem_valid"]
        assert r is not None and r == (1, 0, 0), f"got {r}"

    def test_pcpi_insn_32bit(self, width_results):
        """pcpi_insn: output reg [31:0]."""
        r = width_results["pcpi_insn"]
        assert r is not None and r == (32, 31, 0), f"got {r}"

    def test_trap_1bit(self, width_results):
        """trap: 1-bit output reg."""
        r = width_results["trap"]
        assert r is not None and r == (1, 0, 0), f"got {r}"

    def test_irq_32bit_input(self, width_results):
        """irq: input [31:0]."""
        r = width_results["irq"]
        assert r is not None and r == (32, 31, 0), f"got {r}"

    def test_mem_ready_1bit(self, width_results):
        """mem_ready: 1-bit input."""
        r = width_results["mem_ready"]
        assert r is not None and r == (1, 0, 0), f"got {r}"


# ============================================================================
# 测试 6: 跨 module hierarchical lookup (Phase 2 #4)
# ============================================================================
class TestCrossModuleHierarchical:
    """[Phase 2 2026-06-24] 测 _hierarchical_find + parse_width_from_pyslang 跨 module.

    Fixture: sim/tests/pyslang_type_fixtures/cross_module_hier.sv
      - top_hier (top)
        └─ middle (u_middle)
             └─ sub (u_sub) — 2 层嵌套
    """

    def test_top_level_signal(self, parse_pyslang_width, type_taxonomy_sv):
        """顶层 port: din (32-bit DATA_WIDTH=32)."""
        f = "sim/tests/pyslang_type_fixtures/cross_module_hier.sv"
        r = parse_pyslang_width("din", file=f)
        assert r is not None and r == (32, 31, 0), f"got {r}"

    def test_top_level_1bit(self, parse_pyslang_width):
        """顶层 1-bit port: clk."""
        f = "sim/tests/pyslang_type_fixtures/cross_module_hier.sv"
        r = parse_pyslang_width("clk", file=f)
        assert r is not None and r == (1, 0, 0), f"got {r}"

    def test_top_level_internal_state(self, parse_pyslang_width):
        """顶层 internal FSM: state_q (typedef enum, 2-bit)."""
        f = "sim/tests/pyslang_type_fixtures/cross_module_hier.sv"
        r = parse_pyslang_width("state_q", file=f)
        assert r is not None and r == (2, 1, 0), f"got {r}"

    def test_submodule_1level(self, parse_pyslang_width):
        """1 层 submodule: u_middle.pipe_q (32-bit via parameter)."""
        f = "sim/tests/pyslang_type_fixtures/cross_module_hier.sv"
        r = parse_pyslang_width("u_middle.pipe_q", file=f)
        assert r is not None and r == (32, 31, 0), f"got {r}"

    def test_submodule_2level_data(self, parse_pyslang_width):
        """2 层 nested submodule: u_middle.u_sub.data_o (32-bit)."""
        f = "sim/tests/pyslang_type_fixtures/cross_module_hier.sv"
        r = parse_pyslang_width("u_middle.u_sub.data_o", file=f)
        assert r is not None and r == (32, 31, 0), f"got {r}"

    def test_submodule_2level_clog2(self, parse_pyslang_width):
        """2 层 nested + $clog2 derived: u_middle.u_sub.depth_idx_o (2-bit)."""
        f = "sim/tests/pyslang_type_fixtures/cross_module_hier.sv"
        r = parse_pyslang_width("u_middle.u_sub.depth_idx_o", file=f)
        assert r is not None and r == (2, 1, 0), f"got {r}"

    def test_nonexistent_submodule_returns_none(self, parse_pyslang_width):
        """不存在的 submodule path → None (不 crash)."""
        f = "sim/tests/pyslang_type_fixtures/cross_module_hier.sv"
        r = parse_pyslang_width("u_nonexistent.signal", file=f)
        assert r is None, f"expected None, got {r}"

    def test_submodule_signal_nonexistent(self, parse_pyslang_width):
        """Submodule 存在但 signal 不存在 → None."""
        f = "sim/tests/pyslang_type_fixtures/cross_module_hier.sv"
        r = parse_pyslang_width("u_middle.nonexistent_signal", file=f)
        assert r is None, f"expected None, got {r}"


# ============================================================================
# 测试 7: Multi-package typedef chain + import * pattern (Phase 2 #5)
# ============================================================================
class TestMultiPackageTypedefChain:
    """[Phase 2 2026-06-24] 测 pkg::type_t + typedef 链 + import pkg::*

    Fixture: sim/tests/pyslang_type_fixtures/a_pkg.f (3 packages)
      - types_a_pkg::word_t (logic[31:0])
      - types_b_pkg::b_word_t → types_a_pkg::word_t (跨包链 1 层)
      - types_c_pkg::c_word_t → types_b_pkg::b_word_t → types_a_pkg::word_t (3 层)
    Module top_import_pattern 用 `import pkg::*;` 把 typedef 注入 namespace.
    """

    @pytest.fixture(scope="class")
    def multi_pkg_filelist(self):
        """a_pkg.f 路径 (Pytest 跳过如果不存在)."""
        p = Path(PROJECT_ROOT) / "sim/tests/pyslang_type_fixtures/a_pkg.f"
        if not p.exists():
            pytest.skip(f"Multi-package fixture not found: {p}")
        return str(p)

    def test_1level_typedef(self, multi_pkg_filelist, parse_pyslang_width):
        """1 层 typedef: types_a_pkg::word_t → 32-bit."""
        r = parse_pyslang_width("in_a", filelist=multi_pkg_filelist)
        assert r is not None and r == (32, 31, 0), f"got {r}"

    def test_2level_typedef_chain(self, multi_pkg_filelist, parse_pyslang_width):
        """2 层 typedef 链: types_b_pkg::b_word_t → types_a_pkg::word_t → 32-bit."""
        r = parse_pyslang_width("in_b", filelist=multi_pkg_filelist)
        assert r is not None and r == (32, 31, 0), f"got {r}"

    def test_3level_typedef_chain(self, multi_pkg_filelist, parse_pyslang_width):
        """3 层 typedef 链: types_c_pkg::c_word_t → types_b_pkg → types_a_pkg → 32-bit."""
        r = parse_pyslang_width("in_c", filelist=multi_pkg_filelist)
        assert r is not None and r == (32, 31, 0), f"got {r}"

    def test_import_star_pattern(self, multi_pkg_filelist, parse_pyslang_width):
        """`import pkg::*;` 把 typedef 注入 namespace, 裸用 word_t → 32-bit."""
        # top_import_pattern 用 `import types_a_pkg::*;` 后裸用 word_t
        r = parse_pyslang_width("out_a", filelist=multi_pkg_filelist)
        assert r is not None and r == (32, 31, 0), f"got {r}"

    def test_mixed_with_parameter(self, multi_pkg_filelist, parse_pyslang_width):
        """混合 parameterized 1D + typedef: data_in (logic[WIDTH-1:0] with WIDTH=32)."""
        r = parse_pyslang_width("data_in", filelist=multi_pkg_filelist)
        assert r is not None and r == (32, 31, 0), f"got {r}"
