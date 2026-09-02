# test_connection_extractor.py - ConnectionExtractor 单元测试
# [iter_072 2026-08-29] 补 signal graph 底层测试缺口:
# connection_extractor 此前 **0 直接测试** (仅跨模块行为间接覆盖)。
#
# 覆盖核心逻辑:
# 1. 命名端口连接 → CONNECTION 边
# 2. port_to_internal / port_to_module_type 映射
# 3. 跨模块内部驱动 (实例输出端口)
# 4. generate 展开实例的端口连接
# 5. 缺模块警告
"""
ConnectionExtractor 单元测试 (iter_072 补充)

底层技术: 实例端口 ↔ 模块内部信号的连接提取 (signal graph 的跨模块边来源).
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

from trace.core.compiler import SVCompiler
from trace.core.connection_extractor import ConnectionExtractor
from trace.core.graph.models import EdgeKind
from trace.core.semantic_adapter import SemanticAdapter


def _extract(source, root_module='top'):
    """构造 ConnectionExtractor 并提取 (直接测试底层)."""
    comp = SVCompiler({'test.sv': source})
    adapter = SemanticAdapter(comp.get_root())
    ext = ConnectionExtractor(adapter, root_module_name=root_module)
    return ext.extract()


class TestConnectionExtractorBasic(unittest.TestCase):
    """基本端口连接提取"""

    def test_named_port_connection_edges(self):
        """[Golden] 命名端口连接 → CONNECTION 边

        金标准: top.clk → top.u_dut.clk (实例端口被外部信号驱动)
        """
        source = '''module dut(input clk, input logic [7:0] data, output logic [7:0] out);
    assign out = data;
endmodule
module top;
    logic clk;
    logic [7:0] data, out;
    dut u_dut(.clk(clk), .data(data), .out(out));
endmodule'''
        r = _extract(source)
        edges = {(e.src, e.dst): e.kind for e in r.edges}
        self.assertEqual(edges.get(('top.clk', 'top.u_dut.clk')), EdgeKind.CONNECTION,
                         "外部信号应 CONNECTION 到实例端口")
        self.assertEqual(edges.get(('top.data', 'top.u_dut.data')), EdgeKind.CONNECTION,
                         "data 连接应存在")

    def test_output_port_driven_by_module(self):
        """[Golden] 实例输出端口被模块内部驱动 (DRIVER) + 连到外部 (CONNECTION)

        金标准: dut 内部 out = data → top.u_dut.out 有 DRIVER 边;
        且 top.u_dut.out → top.out CONNECTION.
        """
        source = '''module dut(input logic [7:0] data, output logic [7:0] out);
    assign out = data;
endmodule
module top;
    logic [7:0] data, out;
    dut u_dut(.data(data), .out(out));
endmodule'''
        r = _extract(source)
        edges = {(e.src, e.dst): e.kind for e in r.edges}
        self.assertEqual(edges.get(('top.u_dut.out', 'top.out')), EdgeKind.CONNECTION,
                         "实例输出端口应 CONNECTION 到外部信号")
        # 内部驱动边 (模块内 assign out = data → 实例端口视角)
        self.assertTrue(
            any(s == 'top.u_dut.out' and k == EdgeKind.DRIVER
                for (s, d), k in edges.items()),
            "实例输出端口应有 DRIVER 边 (模块内部驱动)",
        )

    def test_port_to_internal_mapping(self):
        """[Golden] port_to_internal 映射 (实例端口 → 内部信号路径)"""
        source = '''module dut(input clk);
endmodule
module top;
    logic clk;
    dut u_dut(.clk(clk));
endmodule'''
        r = _extract(source)
        self.assertIn('top.u_dut.clk', r.port_to_internal,
                      "实例端口应进入 port_to_internal")

    def test_port_to_module_type_mapping(self):
        """[Golden] port_to_module_type 映射 (实例端口 → 模块.端口)"""
        source = '''module dut(input clk);
endmodule
module top;
    logic clk;
    dut u_dut(.clk(clk));
endmodule'''
        r = _extract(source)
        self.assertEqual(r.port_to_module_type.get('top.u_dut.clk'), 'dut.clk',
                         "实例端口应映射到 模块.端口 短名")

    def test_multi_instance_same_module(self):
        """[Golden] 同模块多实例 — 端口映射区分实例"""
        source = '''module dut(input clk);
endmodule
module top;
    logic clk;
    dut u_a(.clk(clk));
    dut u_b(.clk(clk));
endmodule'''
        r = _extract(source)
        self.assertIn('top.u_a.clk', r.port_to_module_type)
        self.assertIn('top.u_b.clk', r.port_to_module_type)
        self.assertEqual(r.port_to_module_type['top.u_a.clk'], 'dut.clk')
        self.assertEqual(r.port_to_module_type['top.u_b.clk'], 'dut.clk')


class TestConnectionExtractorGenerate(unittest.TestCase):
    """generate 展开实例的端口连接"""

    def test_generate_instance_connections(self):
        """[Golden] generate-for 展开实例有端口 CONNECTION 边

        gen_b[0].u_b / gen_b[1].u_b 展开实例应被连接, 实例路径带 entry 索引
        (top.en → top.gen_b[i].u_b.en).

        [iter_072] 注意: generate-only 实例化 (无直接实例) 的模块, pyslang
        semantic 树不保留其端口定义 → get_modules 收集不到 (EXTRACTION_COVERAGE #45).
        测试用 u0 直接实例化 + gen_b 生成实例 (真实模式: 生成模块通常也有直接实例).
        [iter_109] 路径从折叠的 top.gen_b.u_b 改为带索引 top.gen_b[i].u_b
        (多 entry 实例可区分); 连接信号解析到声明作用域 top.en (原 top.gen_b.en
        引用不存在的作用域)."""
        source = '''module bufio(input wire en, input wire data);
endmodule
module top;
    genvar i;
    wire en, data;
    bufio u0(.en(en), .data(data));
    for (i = 0; i < 2; i++) begin : gen_b
        bufio u_b(.en(en), .data(data));
    end
endmodule'''
        r = _extract(source)
        edges = {(e.src, e.dst) for e in r.edges}
        for i in range(2):
            self.assertIn((f'top.en', f'top.gen_b[{i}].u_b.en'), edges,
                          f"generate 展开实例 top.gen_b[{i}].u_b.en 应有端口连接")
            self.assertIn((f'top.data', f'top.gen_b[{i}].u_b.data'), edges,
                          f"generate 展开实例 top.gen_b[{i}].u_b.data 应有端口连接")

    def test_generate_instance_port_module_type(self):
        """[Golden] generate 内实例的 port_to_module_type

        [iter_072] 同 test_generate_instance_connections: 模块需有直接实例
        才能被 get_modules 收集端口 (见 EXTRACTION_COVERAGE #45).
        """
        source = '''module bufio(input wire en);
endmodule
module top;
    genvar i;
    wire en;
    bufio u0(.en(en));
    for (i = 0; i < 2; i++) begin : gen_b
        bufio u_b(.en(en));
    end
endmodule'''
        r = _extract(source)
        hits = {k: v for k, v in r.port_to_module_type.items() if 'u_b' in k}
        self.assertGreaterEqual(len(hits), 1, "generate 实例端口应映射到模块端口")
        self.assertTrue(all(v == 'bufio.en' for v in hits.values()))


class TestConnectionExtractorWarnings(unittest.TestCase):
    """缺模块警告"""

    def test_missing_module_strict_raises(self):
        """[Golden] 实例引用未定义模块 → strict 编译显式报错 (纪律 #1)

        未定义模块是真实错误, 不应静默容错 (AGENTS.md 禁 --no-strict).
        """
        source = '''module top;
    logic clk;
    missing_mod u_x(.clk(clk));
endmodule'''
        with self.assertRaises(Exception) as ctx:
            _extract(source)
        self.assertIn("missing_mod", str(ctx.exception),
                      "错误应指明未定义模块名")


class TestConnectionExtractorAdvanced(unittest.TestCase):
    """[iter_074] 边界场景: 参数化/位置端口/interface/三态"""

    def test_parameterized_instance(self):
        """[Golden] 参数化实例 #(.W(16)) 端口映射正常"""
        source = '''module sub #(parameter W = 8) (input logic [W-1:0] d, output logic [W-1:0] q);
    assign q = d;
endmodule
module top;
    logic [15:0] d16, q16;
    sub #(.W(16)) u16(.d(d16), .q(q16));
endmodule'''
        r = _extract(source)
        self.assertEqual(r.port_to_module_type.get('top.u16.d'), 'sub.d',
                         "参数化实例端口应映射到模块端口")
        self.assertEqual(r.port_to_module_type.get('top.u16.q'), 'sub.q')
        edges = {(e.src, e.dst) for e in r.edges}
        self.assertIn(('top.d16', 'top.u16.d'), edges, "参数化实例应有连接边")

    def test_positional_port_connection(self):
        """[Golden] 位置端口连接 (sub u_pos(d8, q8)) 也能提取"""
        source = '''module sub(input logic [7:0] d, output logic [7:0] q);
    assign q = d;
endmodule
module top;
    logic [7:0] d8, q8;
    sub u_pos(d8, q8);
endmodule'''
        r = _extract(source)
        # 位置端口: 实例端口名是 sub 的端口名 (d/q)
        self.assertEqual(r.port_to_module_type.get('top.u_pos.d'), 'sub.d',
                         "位置端口应映射到模块端口名")
        edges = {(e.src, e.dst) for e in r.edges}
        self.assertIn(('top.d8', 'top.u_pos.d'), edges, "位置端口应有连接边")

    def test_interface_port(self):
        """[Golden] interface 实例端口映射"""
        source = '''interface bus_if(input logic clk);
    logic req, gnt;
endinterface
module top(input logic clk);
    bus_if ifc(.clk(clk));
endmodule'''
        r = _extract(source)
        self.assertEqual(r.port_to_module_type.get('top.ifc.clk'), 'bus_if.clk',
                         "interface 端口应映射到 interface 端口")

    def test_tri_state_inout_no_connection(self):
        """[Golden] 三态 inout 端口: 无 CONNECTION 边 (tri-state 方向特殊)"""
        source = '''module bufio(inout wire bidir, input wire en, input wire data);
    assign bidir = en ? data : 1'bz;
endmodule
module top;
    wire bidir, en, data;
    bufio u_buf(.bidir(bidir), .en(en), .data(data));
endmodule'''
        r = _extract(source)
        edges = {(e.src, e.dst) for e in r.edges}
        # 普通 input 端口有 CONNECTION
        self.assertIn(('top.en', 'top.u_buf.en'), edges)
        self.assertIn(('top.data', 'top.u_buf.data'), edges)
        # inout bidir 无 CONNECTION 边 (三态, 由 BRANCH 逻辑表达)
        self.assertNotIn(('top.bidir', 'top.u_buf.bidir'), edges,
                         "inout 三态不应有普通 CONNECTION 边")

    def test_port_to_internal_value_semantics(self):
        """[Golden] port_to_internal 值语义: 实例端口映射到同路径 (self 映射)"""
        source = '''module dut(input logic clk);
endmodule
module top;
    logic clk;
    dut u_dut(.clk(clk));
endmodule'''
        r = _extract(source)
        internal = r.port_to_internal.get('top.u_dut.clk')
        self.assertIsNotNone(internal, "port_to_internal 应有该键")
        # 当前实现: 实例端口 → 自身 (self-loop 语义, 跳过自环边但保留映射)
        self.assertEqual(internal, 'top.u_dut.clk',
                         "port_to_internal 当前语义: 实例端口映射到自身")


if __name__ == '__main__':
    unittest.main(verbosity=2)
