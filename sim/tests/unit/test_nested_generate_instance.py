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


if __name__ == '__main__':
    unittest.main()
