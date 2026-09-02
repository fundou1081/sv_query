"""
[iter_112] 门级原语 (GatePrimitiveInstance) 提取 — unit 测试

覆盖 (leaf cell 建模, 方豆拍板方案 A):
- get_module_instances 不再把门原语当模块实例枚举 (native 与 recursive parity 对齐)
- DriverExtractor 为门输出生成 DRIVER 边: 每个输入端子 → 输出
  (嵌套实例作用域: top.u1.a0 ← top.u1.A[0]/B[0]; 顶层端口: xor16.S[i])
- get_primitive_instances 下钻 generate 块 (generate-for 内的门)
- 无 `and0.and0...` 递归假节点 (connection 自环根因修复)
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

from trace.core.compiler import SVCompiler  # noqa: E402
from trace.core.graph_builder import GraphBuilder  # noqa: E402
from trace.core.semantic_adapter import SemanticAdapter  # noqa: E402


def _graph(source, target='top'):
    comp = SVCompiler({'test.sv': source})
    adapter = SemanticAdapter(comp.get_root(), target_module=target)
    return adapter, GraphBuilder(adapter, target_module=target).build()


def _driver_edges(graph):
    """全图 DRIVER 边 (src, dst) 集合."""
    out = set()
    for s, d in graph.edges():
        for e in graph._edge_data.get((s, d), []):
            if e.kind.name == 'DRIVER':
                out.add((s, d))
    return out


PG2_TOP = '''module pg2 (input [1:0] A, B, output [1:0] P, Q);
  wire a0, x0, a1, x1;
  and and0(a0, A[0], B[0]);
  xor xor0(x0, A[0], B[0]);
  and and1(a1, A[1], B[1]);
  xor xor1(x1, A[1], B[1]);
  assign P[0] = a0; assign P[1] = a1;
  assign Q[0] = x0; assign Q[1] = x1;
endmodule
module top (input [1:0] A, B, output [1:0] S);
  wire [1:0] p, q;
  pg2 u1(.A(A), .B(B), .P(p), .Q(q));
  assign S[0] = q[0];
  assign S[1] = p[1] ^ q[1];
endmodule
'''

XOR_TOP = '''module xor16 (input [1:0] A, B, output [1:0] S);
xor xor0(S[0], A[0], B[0]);
xor xor1(S[1], A[1], B[1]);
endmodule
'''

GEN_GATES = '''module top (input [3:0] A, B, output [3:0] Y);
  genvar i;
  generate
    for (i = 0; i < 4; i = i + 1) begin : g
      and and_i (Y[i], A[i], B[i]);
    end
  endgenerate
endmodule
'''


class TestInstanceEnumerationFilters(unittest.TestCase):
    """原语不再当模块实例枚举 (native 过滤, recursive parity 对齐)."""

    def test_module_instances_exclude_primitives(self):
        """pg2+top: 只枚举 u1, 不再枚举 and0/xor0/and1/xor1."""
        comp = SVCompiler({'t.sv': PG2_TOP})
        adapter = SemanticAdapter(comp.get_root(), target_module='top')
        names = [w.name for w in adapter.get_module_instances()]
        self.assertEqual(names, ['u1'], f"应只剩 u1, 实际 {names}")

    def test_top_module_direct_gates_not_enumerated(self):
        """xor16 顶层: xor0/xor1 不进模块实例列表."""
        comp = SVCompiler({'t.sv': XOR_TOP})
        adapter = SemanticAdapter(comp.get_root(), target_module='xor16')
        names = [w.name for w in adapter.get_module_instances()]
        self.assertEqual(names, [], f"门不是模块实例, 实际 {names}")


class TestPrimitiveDriverEdges(unittest.TestCase):
    """门输出 DRIVER 边 (leaf cell: 输入端子 → 输出)."""

    def test_nested_instance_scope_gate_drives_wire(self):
        """top.u1.a0 ← A[0]/B[0] (and0), top.u1.x0 ← A[0]/B[0] (xor0)."""
        _, g = _graph(PG2_TOP)
        drv = _driver_edges(g)
        for wire, inputs in (('top.u1.a0', ('top.u1.A[0]', 'top.u1.B[0]')),
                             ('top.u1.x0', ('top.u1.A[0]', 'top.u1.B[0]')),
                             ('top.u1.a1', ('top.u1.A[1]', 'top.u1.B[1]')),
                             ('top.u1.x1', ('top.u1.A[1]', 'top.u1.B[1]'))):
            for src in inputs:
                self.assertIn((src, wire), drv, f"{src} 应驱动 {wire}")

    def test_top_level_port_bits_driven(self):
        """xor16.S[0]/S[1] ← A[i]/B[i]; assign 不受影响."""
        _, g = _graph(XOR_TOP, target='xor16')
        drv = _driver_edges(g)
        self.assertIn(('xor16.A[0]', 'xor16.S[0]'), drv)
        self.assertIn(('xor16.B[0]', 'xor16.S[0]'), drv)
        self.assertIn(('xor16.A[1]', 'xor16.S[1]'), drv)
        self.assertIn(('xor16.B[1]', 'xor16.S[1]'), drv)
        # 全图 DRIVER 恰好这 4 条 (xor16 无其他逻辑)
        self.assertEqual(len(drv), 4, f"应恰 4 条 DRIVER, 实际 {drv}")

    def test_assign_edges_unchanged(self):
        """assign P[0]=a0 等原 assign 边仍在 (leaf cell 边是新增, 不覆盖)."""
        _, g = _graph(PG2_TOP)
        drv = _driver_edges(g)
        self.assertIn(('top.u1.a0', 'top.u1.P[0]'), drv, "assign P[0]=a0 边应保留")


class TestGeneratePrimitives(unittest.TestCase):
    """get_primitive_instances 下钻 generate-for, 门边按 entry 输出."""

    def test_generate_for_gates_collected(self):
        comp = SVCompiler({'t.sv': GEN_GATES})
        adapter = SemanticAdapter(comp.get_root(), target_module='top')
        prims = adapter.get_primitive_instances(
            comp.get_root().topInstances[0])
        self.assertEqual(len(prims), 4, "generate-for 4 个 entry 各 1 门")
        fn = {str(getattr(getattr(p, 'primitiveType', None), 'name', ''))
              for p in prims}
        self.assertEqual(fn, {'and'})

    def test_generate_gate_driver_edges(self):
        """generate 内门: Y[i] ← A[i]/B[i] (按 entry 展开, 无 genvar 泄漏)."""
        _, g = _graph(GEN_GATES)
        drv = _driver_edges(g)
        for i in range(4):
            self.assertIn((f'top.A[{i}]', f'top.Y[{i}]'), drv,
                          f"Y[{i}] 应由 A[{i}] 驱动")
            self.assertIn((f'top.B[{i}]', f'top.Y[{i}]'), drv,
                          f"Y[{i}] 应由 B[{i}] 驱动")
        self.assertEqual(len(drv), 8, f"应恰 8 条, 实际 {drv}")


class TestNoRecursiveGateNodes(unittest.TestCase):
    """connection 自环根因修复: 无 `and0.and0...` 递归假节点."""

    def test_no_recursive_instance_chain(self):
        _, g = _graph(PG2_TOP)
        for n in g.nodes():
            self.assertNotIn('and0.and0', n, f"递归假节点不应存在: {n}")
            self.assertNotIn('xor0.xor0', n, f"递归假节点不应存在: {n}")


if __name__ == '__main__':
    unittest.main()
