"""
[iter_113] 两级实例嵌套 generate-for 提取 — unit 测试

覆盖 (修复 iter_113, hardware cpa carry_lookahead_adder 摸底缺口):
- driver instance paths 现在真正下钻 generate 块 (graph_builder.walk 用 hp 路径)
  → 嵌套实例内 (top.u_cla.generators[i].u_cell4) 的 always_comb 按实例作用域提取
- connection inst_module_name 启发式: 实例名 == 类型名 (cell4 cell4) 时不再
  回落 parent_module → get_path 自环递归清零
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

from trace.core.compiler import SVCompiler  # noqa: E402
from trace.core.graph_builder import GraphBuilder  # noqa: E402
from trace.core.semantic_adapter import SemanticAdapter  # noqa: E402


def _src(inst_style):
    inst = "cell4 cell4 (" if inst_style == 'same' else "cell4 u_cell4 ("
    return f'''module cell4 (input logic [3:0] p, g, input logic cin,
                output logic [2:0] cout, output logic pg, gg);
  always_comb begin
    pg = &p; gg = g[3];
    cout[0] = g[0] | (cin & p[0]);
    cout[1] = g[1] | (g[0] & p[1]);
    cout[2] = g[2] | (g[1] & p[2]);
  end
endmodule
module cla (input logic [15:0] p, g, input logic cin, output logic [2:0] cout);
  genvar i;
  generate
    for (i=0; i<3; i=i+1) begin : generators
      {inst}.p(p[i*4+:4]), .g(g[i*4+:4]), .cin(cin), .cout(cout[i]), .pg(), .gg());
    end
  endgenerate
endmodule
module toplevel (input logic [15:0] p, g, input logic cin, output logic [2:0] cout);
  cla u_cla (.p(p), .g(g), .cin(cin), .cout(cout));
endmodule
'''


def _graph(src, target='toplevel'):
    comp = SVCompiler({'t.sv': src})
    adapter = SemanticAdapter(comp.get_root(), target_module=target)
    return GraphBuilder(adapter, target_module=target).build()


def _driver_dsts(graph):
    """DRIVER 边 dst 集合."""
    out = set()
    for s, d in graph.edges():
        for e in graph._edge_data.get((s, d), []):
            if e.kind.name == 'DRIVER':
                out.add(d)
    return out


class TestNestedGenerateExtraction(unittest.TestCase):
    """两级实例嵌套 generate: 内部逻辑按 generators[i] 作用域提取."""

    def test_internals_extracted_distinct_inst_name(self):
        """u_cell4: cell4 内部输出在本实例作用域有驱动 (cout[0]←g[0]/cin/p[0])."""
        g = _graph(_src('diff'))
        dsts = _driver_dsts(g)
        scope = "toplevel.u_cla.generators[0].u_cell4"
        self.assertIn(f"{scope}.cout[0]", dsts,
                      "generators[0] 内 cell4.cout[0] 应被内部驱动 (iter_113 前 0 提取)")
        self.assertIn(f"{scope}.pg", dsts)
        self.assertIn(f"{scope}.gg", dsts)

    def test_internals_extracted_inst_name_equals_type(self):
        """cell4 cell4 (inst==type, 摸底真实形态): 同样提取且无递归."""
        g = _graph(_src('same'))
        dsts = _driver_dsts(g)
        scope = "toplevel.u_cla.generators[1].cell4"
        self.assertIn(f"{scope}.cout[0]", dsts,
                      "inst==type 时 cell4.cout[0] 应被驱动")
        self.assertIn(f"{scope}.gg", dsts)

    def test_no_recursive_nodes_inst_equals_type(self):
        """inst==type 曾触发 connection get_path 自环 → 递归假节点清零."""
        g = _graph(_src('same'))
        for n in g.nodes():
            self.assertNotIn("cell4.cell4", n, f"递归假节点不应存在: {n[:100]}")

    def test_three_generator_scopes_present(self):
        """3 个 generate entry 各自作用域都有内部信号节点."""
        g = _graph(_src('same'))
        for i in range(3):
            prefix = f"toplevel.u_cla.generators[{i}].cell4"
            hit = [n for n in g.nodes() if n.startswith(prefix)]
            self.assertGreater(len(hit), 0, f"{prefix}.* 节点应存在")
            # 且无 'generators[i].cell4.generators' 再度嵌套
            self.assertFalse(
                [n for n in g.nodes() if f"{prefix}.generators" in n],
                "不应出现 generate 再度嵌套的假路径")


NESTED_GEN_UNDER_INSTANCE = '''module cellm (input a, output y);
  assign y = a;
endmodule
module longm (input [15:0] a, output [15:0] y);
  genvar i;
  generate
    begin : STAGES
      if (1) begin : FOR
        for (i=0;i<4;i=i+1) begin : GENSTAGES
          cellm genmpy (.a(a[i]), .y(y[i]));
        end
      end
    end
  endgenerate
endmodule
module midm (input [15:0] a, output [15:0] y);
  longm p3 (.a(a), .y(y));
endmodule
module top (input [15:0] a, output [15:0] y);
  midm u_bfly (.a(a), .y(y));
endmodule
'''


def _doubled_segment(n):
    """索引段相邻重复 (iter_116 aes ROM[4].ROM[4] / dblclockfft GENSTAGES[0].GENSTAGES[0])."""
    segs = n.split('.')
    return any(segs[i] and segs[i] == segs[i + 1] and '[' in segs[i]
               for i in range(len(segs) - 1))


class TestIndexSegmentDoubling(unittest.TestCase):
    """[iter_117] 索引段加倍假节点修复 — 实例内嵌套 generate / 数组实例.

    触发: connection get_path 在父路径已含 generate 索引段 (如 ...GENSTAGES[0])
    时, _get_generate_block_name (hp 正则) 又取一次同段拼上 → 双段假节点.
    genfor/CLA 曾被 legacy 族同 key 覆盖掩盖; 无 legacy 族 (generate 在嵌套
    实例内) 即暴露 — aes (84) / dblclockfft (63/模块) 真实复现.
    """

    def test_no_doubled_segments_nested_gen(self):
        """实例内嵌套 gen (STAGES→FOR→GENSTAGES): 无 GENSTAGES[i].GENSTAGES[i]."""
        g = _graph(NESTED_GEN_UNDER_INSTANCE, target='top')
        bad = [n for n in g.nodes() if _doubled_segment(n)]
        self.assertEqual(bad, [], f"索引段加倍假节点不应存在: "
                                  f"{bad[0][:90] if bad else ''}")

    def test_single_indexed_paths_present(self):
        """genmpy 内部信号落在单索引路径 top.u_bfly.p3.STAGES.FOR.GENSTAGES[i]."""
        g = _graph(NESTED_GEN_UNDER_INSTANCE, target='top')
        for i in range(4):
            prefix = f"top.u_bfly.p3.STAGES.FOR.GENSTAGES[{i}].genmpy"
            hit = [n for n in g.nodes() if n.startswith(prefix)]
            self.assertGreater(len(hit), 0,
                               f"{prefix}.* 节点应存在 (单索引)")
            for n in hit:
                self.assertEqual(n.count("GENSTAGES"), 1,
                                 f"{prefix} 内不应重复 GENSTAGES: {n[:90]}")
            self.assertFalse(
                [n for n in g.nodes()
                 if n.startswith(prefix) and f"GENSTAGES[{i}]" in n.split(".")[n.split(".").index("GENSTAGES[" + str(i) + "]") + 1:]],
                f"不应有 GENSTAGES 二次拼接")

    def test_legacy_single_level_still_fine(self):
        """顶层 gen (genfor 形态) 路径仍单索引 — 修复不改顶层行为."""
        src = '''module rot(input [7:0] x, output [7:0] xo);
  assign xo = x;
endmodule
module top(input [7:0] a, output [7:0] out);
  wire [7:0] arr [0:2];
  genvar i;
  generate for (i=0;i<2;i=i+1) begin : g
    rot U (.x(arr[i]), .xo(arr[i+1]));
  end endgenerate
  assign arr[0] = a; assign out = arr[2];
endmodule
'''
        g = _graph(src, target='top')
        bad = [n for n in g.nodes() if _doubled_segment(n)]
        self.assertEqual(bad, [], "顶层 gen 不应加倍")
        for i in range(2):
            self.assertIsNotNone(g.get_node(f"top.g[{i}].U"),
                                 f"top.g[{i}].U 应存在")


if __name__ == '__main__':
    unittest.main()


GEN_ASSIGN_RHS_INDEX = '''module top (input a, output y);
  wire [14:0] x;
  assign x[0] = a;
  genvar i;
  generate for (i=1;i<15;i=i+1) begin : CH
    assign x[i] = x[i-1];
  end endgenerate
  assign y = x[14];
endmodule
'''


class TestGenerateAssignRhsIndex(unittest.TestCase):
    """[iter_118] generate-for 内 assign 的 RHS 位选按 entry 索引求值.

    iter_118 极端场景 (S8 深 fanin 链) 发现: entry 内 `assign x[i] = x[i-1]`
    的 RHS x[i-1] 被解析成整总线 'x' (selector 是 NamedValue i / BinaryOp i-1,
    旧逻辑非 Literal/Parameter 直接 fallback base) → fanin 链死端.
    case27 (iter_035 起) 的 acc[i] RHS 同病, 从未被图级断言捕获.
    """

    def _chain_ok(self, g):
        """x[i] 的 DRIVER 源 = x[i-1] (除 x[0]←a)."""
        for i in range(1, 15):
            dst = f"top.x[{i}]"
            srcs = set()
            for s, d in g.edges():
                if d == dst:
                    for e in g._edge_data.get((s, d), []):
                        if e.kind.name == 'DRIVER':
                            srcs.add(s)
            self.assertIn(f"top.x[{i-1}]", srcs,
                          f"x[{i}] 应由 x[{i-1}] 驱动 (RHS 索引求值)")

    def test_rhs_index_per_entry(self):
        g = _graph(GEN_ASSIGN_RHS_INDEX, target='top')
        self._chain_ok(g)

    def test_fanin_reaches_input(self):
        """x[14] 沿 DRIVER 回溯 14 跳可达 a (深链非死端)."""
        g = _graph(GEN_ASSIGN_RHS_INDEX, target='top')
        cur, seen, ok = 'top.x[14]', set(), False
        while cur not in seen:
            seen.add(cur)
            srcs = set()
            for s, d in g.edges():
                if d == cur:
                    for e in g._edge_data.get((s, d), []):
                        if e.kind.name == 'DRIVER':
                            srcs.add(s)
            if 'top.a' in srcs:
                ok = True
                break
            nxt = [s for s in srcs if s.startswith('top.x')]
            if not nxt:
                break
            cur = nxt[0]
        self.assertTrue(ok, "fanin 应可达 a")

    def test_no_bus_fallback_src(self):
        """无整总线 'top.x' 作为位驱动源 (修复前 RHS 落总线)."""
        g = _graph(GEN_ASSIGN_RHS_INDEX, target='top')
        for s, d in g.edges():
            for e in g._edge_data.get((s, d), []):
                if e.kind.name == 'DRIVER' and d.startswith('top.x['):
                    self.assertNotEqual(s, 'top.x',
                                        f"{d} 不应由整总线 top.x 驱动")
