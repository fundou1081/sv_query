"""
[iter_112] 门级原语 xor16 1:1 truth (真实工业门级 RTL)

1:1 truth 金标准: KoggeStone-BrentKung/BrentKung/xor16.v (golden_dataflow_40,
拷自 openrtl) — 16 个 xor 门直接驱动输出端口 S[0..15] 的纯门级模块。
iter_112 前该结构完全无法表达: xor 门被当"模块实例"展开 (connection 无限递归
`xor0.xor0...` ×21), 且 S 位无任何 DRIVER ("谁驱动 S[0]" 无答案)。

1:1 预期 (iter_112 修复后实测):
- S[0..15] 每 bit 恰好被 {A[i], B[i]} 两个 DRIVER 源驱动 (leaf cell 语义:
  门输入端子 → 输出, 与 assign 二元操作数约定一致) → 全图 DRIVER 边集合 ==
  {(xor16.A[i], xor16.S[i]), (xor16.B[i], xor16.S[i]) : i in 0..15} (32 条)
- 无递归假实例节点 (无 'xor16.xor0.xor0...' 链) — 原语不再当模块实例
- 无 '?' 占位; 门不产生独立实例节点 (leaf cell, 输出落宿主作用域)
"""
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "src"))

import unittest  # noqa: E402

from trace.unified_tracer import UnifiedTracer  # noqa: E402

FIXTURE = _REPO_ROOT / "sim" / "tests" / "fixtures" / "golden_mini" / "golden_dataflow_40_xor16_gate.v"


def _build_graph():
    tracer = UnifiedTracer(sources={str(FIXTURE): FIXTURE.read_text()}, log_level="ERROR")
    return tracer.build_graph(use_cache=False)


class TestXor16GateTruth(unittest.TestCase):
    """[1:1 truth] xor16 门级原语: S[i] ← A[i], B[i] (32 条 DRIVER 精确集)"""

    @classmethod
    def setUpClass(cls):
        cls.g = _build_graph()

    def _driver_set(self):
        """全图 DRIVER 边 (src, dst) 集合."""
        out = set()
        for s, d in self.g.edges():
            for e in self.g._edge_data.get((s, d), []):
                if e.kind.name == "DRIVER":
                    out.add((s, d))
        return out

    def test_driver_edge_set_exact(self):
        """DRIVER 边集合 == 32 条门驱动 (S[i]←A[i]/B[i]), 不多不少."""
        expected = set()
        for i in range(16):
            expected.add((f"xor16.A[{i}]", f"xor16.S[{i}]"))
            expected.add((f"xor16.B[{i}]", f"xor16.S[{i}]"))
        self.assertEqual(self._driver_set(), expected,
                         "全图 DRIVER 边应精确等于 32 条门驱动边")

    def test_all_S_bits_driven(self):
        """S[0..15] 全部可达驱动 (修复前 16 bit 全无驱动)."""
        drivers = self._driver_set()
        driven = {d for _, d in drivers}
        for i in range(16):
            self.assertIn(f"xor16.S[{i}]", driven, f"S[{i}] 应被驱动")

    def test_no_recursive_gate_instances(self):
        """无递归假实例节点 (原语不再当模块实例展开)."""
        for n in self.g.nodes():
            self.assertNotIn("xor0.xor0", n, f"不应有递归原语节点: {n}")

    def test_no_placeholder(self):
        """无 '?' 占位节点."""
        for n in self.g.nodes():
            self.assertNotIn("?", n, f"占位节点不应存在: {n}")

    def test_gate_is_leaf_no_instance_node(self):
        """门不产生独立模块实例节点 (leaf cell): xor16.xor0 等不应在图里."""
        for i in range(16):
            self.assertIsNone(self.g.get_node(f"xor16.xor{i}"),
                              f"门实例 xor{i} 不应作为模块实例节点存在")
        self.assertIsNotNone(self.g.get_node("xor16.S"), "输出端口 S 应存在")

    def test_graph_scale(self):
        """图规模 sanity: S 端口 17 节点 (S + 16 bit), DRIVER=32."""
        s_nodes = [n for n in self.g.nodes() if n.startswith("xor16.S")]
        self.assertEqual(len(s_nodes), 17, "S + S[0..15] 共 17 节点")
        self.assertEqual(len(self._driver_set()), 32)


if __name__ == "__main__":
    unittest.main()
