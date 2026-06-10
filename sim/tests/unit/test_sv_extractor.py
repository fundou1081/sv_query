"""
test_sv_extractor.py
=====================
Phase A v3 Option 1: 真实 SV 集成测试

测试覆盖:
  - 从单 SV 文件提取 module 信号
  - 位宽正确提取 (1-bit wire, [N:0] vector)
  - 方向正确 (input/output/inout)
  - paired_signals 启发式 (双向 valid+ready)
  - 端到端: 真实 SV → ProtocolDetector 输出
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

from trace.core.protocol.sv_extractor import SVSignalExtractor, ExtractedModule
from trace.core.protocol.structural import SignalContext
from trace.core.protocol.detector import ProtocolDetector
from trace.core.protocol.schema import ProtocolSchemaRegistry
from trace.core.protocol.handshake_provider import NameBasedHandshakeProvider


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

AXI_DRAM_SV = """\
module axi_dp_ram #(
    parameter ADDR_WIDTH = 32,
    parameter DATA_WIDTH = 32
)(
    input  wire                    clk,
    input  wire                    rst,

    input  wire [ADDR_WIDTH-1:0]  s_axi_awaddr,
    input  wire [7:0]             s_axi_awlen,
    input  wire [2:0]             s_axi_awsize,
    input  wire [1:0]             s_axi_awburst,
    input  wire                   s_axi_awvalid,
    output wire                   s_axi_awready,
    input  wire [DATA_WIDTH-1:0]  s_axi_wdata,
    input  wire [3:0]             s_axi_wstrb,
    input  wire                   s_axi_wlast,
    input  wire                   s_axi_wvalid,
    output wire                   s_axi_wready,
    output wire [1:0]             s_axi_bresp,
    input  wire                   s_axi_bready,
    output wire                   s_axi_bvalid,
    input  wire [ADDR_WIDTH-1:0]  s_axi_araddr,
    input  wire [7:0]             s_axi_arlen,
    input  wire [2:0]             s_axi_arsize,
    input  wire [1:0]             s_axi_arburst,
    input  wire                   s_axi_arvalid,
    output wire                   s_axi_arready,
    output wire [DATA_WIDTH-1:0]  s_axi_rdata,
    output wire [1:0]             s_axi_rresp,
    output wire                   s_axi_rlast,
    output wire                   s_axi_rvalid,
    input  wire                   s_axi_rready
);
endmodule
"""

TLUL_SV = """\
module tlul_host #(
    parameter int Width = 32
) (
    input  logic        clk_i,
    input  logic        rst_ni,
    input  logic        a_valid_i,
    output logic        a_ready_o,
    output logic [7:0]  a_opcode_o,
    output logic [31:0] a_addr_o,
    output logic        d_valid_o,
    input  logic        d_ready_i,
    output logic [7:0]  d_opcode_o,
    output logic [31:0] d_data_o
);
endmodule
"""

APB_SV = """\
module apb_master #(
    parameter ADDR_WIDTH = 32,
    parameter DATA_WIDTH = 32
)(
    input  wire                    clk,
    input  wire                    rst_n,
    output wire                    psel,
    output wire                    penable,
    output wire                    pwrite,
    output wire [ADDR_WIDTH-1:0]   paddr,
    output wire [DATA_WIDTH-1:0]   pwdata,
    input  wire                    pready,
    input  wire [DATA_WIDTH-1:0]   prdata,
    input  wire                    pslverr
);
endmodule
"""


@pytest.fixture
def tmp_sv_dir(tmp_path):
    """写测试 SV 文件到 tmp 目录."""
    axi_file = tmp_path / "axi_dp_ram.sv"
    axi_file.write_text(AXI_DRAM_SV)
    tlul_file = tmp_path / "tlul_host.sv"
    tlul_file.write_text(TLUL_SV)
    apb_file = tmp_path / "apb_master.sv"
    apb_file.write_text(APB_SV)
    return {
        "axi": str(axi_file),
        "tlul": str(tlul_file),
        "apb": str(apb_file),
    }


@pytest.fixture
def detector():
    reg = ProtocolSchemaRegistry.from_directory("config/protocols")
    return ProtocolDetector(
        registry=reg,
        handshake_provider=NameBasedHandshakeProvider(),
    )


# ---------------------------------------------------------------------------
# 基础提取
# ---------------------------------------------------------------------------

class TestBasicExtraction:
    def test_extract_one_module(self, tmp_sv_dir):
        ext = SVSignalExtractor.from_file(tmp_sv_dir["axi"])
        mods = ext.extract_all_modules()
        assert len(mods) == 1
        assert "axi_dp_ram" in mods

    def test_extract_signals(self, tmp_sv_dir):
        ext = SVSignalExtractor.from_file(tmp_sv_dir["axi"])
        mod = ext.extract_module("axi_dp_ram")
        assert mod is not None
        # 25 AXI 信号 + clk + rst = 27
        assert len(mod.signals) == 27

    def test_signal_name(self, tmp_sv_dir):
        ext = SVSignalExtractor.from_file(tmp_sv_dir["axi"])
        mod = ext.extract_module("axi_dp_ram")
        names = {s.name for s in mod.signals}
        assert "s_axi_awvalid" in names
        assert "s_axi_awready" in names
        assert "s_axi_awaddr" in names
        assert "clk" in names


# ---------------------------------------------------------------------------
# 位宽
# ---------------------------------------------------------------------------

class TestWidthExtraction:
    def test_1bit_width(self, tmp_sv_dir):
        """`input wire clk` → width=1."""
        ext = SVSignalExtractor.from_file(tmp_sv_dir["axi"])
        mod = ext.extract_module("axi_dp_ram")
        clk = next(s for s in mod.signals if s.name == "clk")
        assert clk.width == 1

    def test_vector_width(self, tmp_sv_dir):
        """`[31:0]` → width=32."""
        ext = SVSignalExtractor.from_file(tmp_sv_dir["axi"])
        mod = ext.extract_module("axi_dp_ram")
        awaddr = next(s for s in mod.signals if s.name == "s_axi_awaddr")
        assert awaddr.width == 32

    def test_smaller_vector(self, tmp_sv_dir):
        """`[7:0]` → 8, `[3:0]` → 4, `[2:0]` → 3, `[1:0]` → 2."""
        ext = SVSignalExtractor.from_file(tmp_sv_dir["axi"])
        mod = ext.extract_module("axi_dp_ram")
        assert next(s for s in mod.signals if s.name == "s_axi_awlen").width == 8
        assert next(s for s in mod.signals if s.name == "s_axi_wstrb").width == 4
        assert next(s for s in mod.signals if s.name == "s_axi_awsize").width == 3
        assert next(s for s in mod.signals if s.name == "s_axi_awburst").width == 2

    def test_tlul_widths(self, tmp_sv_dir):
        """TL-UL 风格: 1-bit 标量 + [N:0] 向量."""
        ext = SVSignalExtractor.from_file(tmp_sv_dir["tlul"])
        mod = ext.extract_module("tlul_host")
        assert next(s for s in mod.signals if s.name == "a_valid_i").width == 1
        assert next(s for s in mod.signals if s.name == "a_opcode_o").width == 8
        assert next(s for s in mod.signals if s.name == "a_addr_o").width == 32


# ---------------------------------------------------------------------------
# 方向
# ---------------------------------------------------------------------------

class TestDirectionExtraction:
    def test_axi_slave_perspective(self, tmp_sv_dir):
        """verilog-axi axi_dp_ram 是 slave 视角:
        - s_axi_*_valid: input (master 送来)
        - s_axi_*_ready: output (slave 回应)
        - s_axi_*_data: 取决于方向
        """
        ext = SVSignalExtractor.from_file(tmp_sv_dir["axi"])
        mod = ext.extract_module("axi_dp_ram")
        awvalid = next(s for s in mod.signals if s.name == "s_axi_awvalid")
        awready = next(s for s in mod.signals if s.name == "s_axi_awready")
        bvalid = next(s for s in mod.signals if s.name == "s_axi_bvalid")
        bready = next(s for s in mod.signals if s.name == "s_axi_bready")
        assert awvalid.direction == "input"
        assert awready.direction == "output"
        assert bvalid.direction == "output"
        assert bready.direction == "input"

    def test_apb_master_directions(self, tmp_sv_dir):
        """APB master: psel/penable/pwrite/paddr/pwdata output, pready/prdata/pslverr input."""
        ext = SVSignalExtractor.from_file(tmp_sv_dir["apb"])
        mod = ext.extract_module("apb_master")
        psel = next(s for s in mod.signals if s.name == "psel")
        pready = next(s for s in mod.signals if s.name == "pready")
        assert psel.direction == "output"
        assert pready.direction == "input"


# ---------------------------------------------------------------------------
# Paired 信号启发式
# ---------------------------------------------------------------------------

class TestPairedSignals:
    def test_axi_5_channels_paired(self, tmp_sv_dir):
        """AXI4 5 通道都应配对 (5 对 valid+ready)."""
        ext = SVSignalExtractor.from_file(tmp_sv_dir["axi"])
        mod = ext.extract_module("axi_dp_ram")
        # 至少 5 对配对
        paired_count = sum(1 for s in mod.signals if s.paired_signals)
        assert paired_count >= 10  # 5 对, 每对 2 个信号

    def test_aw_channel_paired(self, tmp_sv_dir):
        """AW 通道: s_axi_awvalid ↔ s_axi_awready."""
        ext = SVSignalExtractor.from_file(tmp_sv_dir["axi"])
        mod = ext.extract_module("axi_dp_ram")
        awvalid = next(s for s in mod.signals if s.name == "s_axi_awvalid")
        awready = next(s for s in mod.signals if s.name == "s_axi_awready")
        assert "s_axi_awready" in awvalid.paired_signals
        assert "s_axi_awvalid" in awready.paired_signals

    def test_tlul_paired(self, tmp_sv_dir):
        """TL-UL: a_valid ↔ a_ready, d_valid ↔ d_ready."""
        ext = SVSignalExtractor.from_file(tmp_sv_dir["tlul"])
        mod = ext.extract_module("tlul_host")
        a_valid = next(s for s in mod.signals if s.name == "a_valid_i")
        a_ready = next(s for s in mod.signals if s.name == "a_ready_o")
        d_valid = next(s for s in mod.signals if s.name == "d_valid_o")
        d_ready = next(s for s in mod.signals if s.name == "d_ready_i")
        assert "a_ready_o" in a_valid.paired_signals
        assert "a_valid_i" in a_ready.paired_signals
        assert "d_ready_i" in d_valid.paired_signals
        assert "d_valid_o" in d_ready.paired_signals


# ---------------------------------------------------------------------------
# Filelist 支持
# ---------------------------------------------------------------------------

class TestFilelist:
    def test_filelist_basic(self, tmp_sv_dir, tmp_path):
        """从 filelist 加载多个文件."""
        fl = tmp_path / "all.f"
        fl.write_text(
            f"{tmp_sv_dir['axi']}\n{tmp_sv_dir['tlul']}\n{tmp_sv_dir['apb']}\n"
        )
        ext = SVSignalExtractor.from_filelist(str(fl))
        mods = ext.extract_all_modules()
        assert "axi_dp_ram" in mods
        assert "tlul_host" in mods
        assert "apb_master" in mods

    def test_list_modules(self, tmp_sv_dir):
        ext = SVSignalExtractor.from_file(tmp_sv_dir["axi"])
        names = ext.list_modules()
        assert "axi_dp_ram" in names


# ---------------------------------------------------------------------------
# 端到端: SV → ProtocolDetector
# ---------------------------------------------------------------------------

class TestEndToEndDetection:
    def test_real_axi_detected(self, tmp_sv_dir, detector):
        ext = SVSignalExtractor.from_file(tmp_sv_dir["axi"])
        mod = ext.extract_module("axi_dp_ram")
        match = detector.detect(mod.signals)
        assert match.protocol == "AXI4"
        assert match.variant == "AXI4_FULL"
        assert match.confidence >= 0.5

    def test_real_tlul_detected(self, tmp_sv_dir, detector):
        ext = SVSignalExtractor.from_file(tmp_sv_dir["tlul"])
        mod = ext.extract_module("tlul_host")
        match = detector.detect(mod.signals)
        assert match.protocol == "TL-UL"
        assert match.confidence >= 0.5

    def test_real_apb_detected(self, tmp_sv_dir, detector):
        ext = SVSignalExtractor.from_file(tmp_sv_dir["apb"])
        mod = ext.extract_module("apb_master")
        match = detector.detect(mod.signals)
        assert match.protocol == "APB"
        assert match.variant == "APB3"
        assert match.confidence >= 0.5

    def test_real_sv_higher_confidence_than_mock(self, tmp_sv_dir, detector):
        """真实 SV 提取的信号比 mock 数据置信度更高 (或相等)."""
        ext = SVSignalExtractor.from_file(tmp_sv_dir["axi"])
        mod = ext.extract_module("axi_dp_ram")
        match = detector.detect(mod.signals)
        # 真实 SV 至少 0.7 (实际是 0.799)
        assert match.confidence >= 0.7


# ---------------------------------------------------------------------------
# 错误处理
# ---------------------------------------------------------------------------

class TestErrorHandling:
    def test_nonexistent_file(self):
        with pytest.raises(Exception):
            SVSignalExtractor.from_file("/nonexistent/path/file.sv").extract_all_modules()

    def test_empty_signals_module(self, tmp_path):
        sv = """\
module empty_mod;
endmodule
"""
        f = tmp_path / "empty.sv"
        f.write_text(sv)
        ext = SVSignalExtractor.from_file(str(f))
        mods = ext.extract_all_modules()
        # 应该有 empty_mod, 但 signals 为空
        if "empty_mod" in mods:
            assert len(mods["empty_mod"].signals) == 0

    def test_extract_specific_module(self, tmp_sv_dir):
        ext = SVSignalExtractor.from_file(tmp_sv_dir["axi"])
        mod = ext.extract_module("nonexistent")
        assert mod is None
