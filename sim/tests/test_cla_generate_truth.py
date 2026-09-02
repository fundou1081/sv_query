"""
[iter_113] carry_lookahead_adder 嵌套 generate 1:1 truth (真实硬件 RTL)

1:1 truth 金标准: supranational/hardware rtl/cpa (golden_dataflow_41 =
lookahead_generator_x4.sv + carry_lookahead_adder.sv 原样拼接, BIT_LEN=16).
真实 RTL 正是 iter_113 修复的两种病态形态:
- generate-for 在模块内: carry_lookahead_adder.generators[0..3] 各实例化一个
  lookahead_generator_x4 (实例名 == 类型名 'lookahead_generator_x4')
- 另有直接实例 lookahead_generator_x4 (顶层 inst==type)

iter_113 前: generators[i] 内信号 0 提取 (纯 comb 的 lookahead_generator_x4
内部 always_comb 无 DRIVER); inst==type 触发 connection get_path 自环 →
'lookahead_generator_x4.generators[0].lookahead_generator_x4...' 无限递归假节点。

1:1 预期 (iter_113 修复后实测):
- 无递归假节点; generators[0..3].lookahead_generator_x4 实例节点在位
- 每个 generator 内部 always_comb 输出 (cout/g_group/p_group) 在本实例作用域
  被内部逻辑驱动 (p_group ← p[0..3]; g_group ← g[3]/p[3] 等组合操作数)
- 直接实例 carry_lookahead_adder.lookahead_generator_x4 同样有内部驱动
"""
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "src"))

import unittest  # noqa: E402

from trace.unified_tracer import UnifiedTracer  # noqa: E402

FIXTURE = _REPO_ROOT / "sim" / "tests" / "fixtures" / "golden_mini" / "golden_dataflow_41_cla_nested_generate.v"


def _build_graph():
    # [iter_113] 必须 target 模式 (instance-path driver): 无 target 时 driver 走
    # type-level 旧路径, generate 实例内部不提取 (cordic truth 亦同 — 其断言
    # 只到 connection 层). CLA truth 断言的是 driver 内部逻辑 → target 必须.
    from trace.core.compiler import SVCompiler  # noqa: E402
    from trace.core.graph_builder import GraphBuilder  # noqa: E402
    from trace.core.semantic_adapter import SemanticAdapter  # noqa: E402
    comp = SVCompiler({str(FIXTURE): FIXTURE.read_text()})
    adapter = SemanticAdapter(comp.get_root(), target_module="carry_lookahead_adder")
    return GraphBuilder(adapter, target_module="carry_lookahead_adder").build()


class TestClaNestedGenerateTruth(unittest.TestCase):
    """[1:1 truth] CLA 嵌套 generate (inst==type): 内部逻辑按实例作用域提取"""

    @classmethod
    def setUpClass(cls):
        cls.g = _build_graph()

    def _drivers(self):
        """dst → [src...] (DRIVER 边)."""
        out = {}
        for s, d in self.g.edges():
            for e in self.g._edge_data.get((s, d), []):
                if e.kind.name == "DRIVER":
                    out.setdefault(d, []).append(s)
        return out

    def test_no_recursive_fake_nodes(self):
        """无递归假节点 (inst==type 曾触发 get_path 自环)."""
        for n in self.g.nodes():
            self.assertNotIn(
                "lookahead_generator_x4.lookahead_generator_x4", n,
                f"递归假节点不应存在: {n[:120]}")

    def test_generator_instances_exist(self):
        """generators[0..3].lookahead_generator_x4 实例节点在位 (NUM_GROUPS-1=4)."""
        for i in range(4):
            self.assertIsNotNone(
                self.g.get_node(f"carry_lookahead_adder.generators[{i}].lookahead_generator_x4"),
                f"generators[{i}] 实例节点应存在")

    def test_generator_internal_outputs_driven(self):
        """generator 内部 always_comb 输出在本实例作用域被驱动 (iter_113 前 0 提取)."""
        drv = self._drivers()
        for i in range(4):
            scope = f"carry_lookahead_adder.generators[{i}].lookahead_generator_x4"
            for sig in ("p_group", "g_group", "cout[0]", "cout[2]"):
                dst = f"{scope}.{sig}"
                srcs = drv.get(dst, [])
                self.assertGreater(len(srcs), 0, f"{dst} 应被内部逻辑驱动")
                # 驱动源必须在本实例作用域内 (非别处串扰)
                for s in srcs:
                    self.assertTrue(s.startswith(scope),
                                    f"{dst} 的驱动源 {s} 应在同一实例作用域")

    def test_p_group_driven_by_reduction_operand(self):
        """p_group = &p → 由总线 p (归约操作数) 驱动."""
        drv = self._drivers()
        scope = "carry_lookahead_adder.generators[0].lookahead_generator_x4"
        srcs = set(drv.get(f"{scope}.p_group", []))
        self.assertIn(f"{scope}.p", srcs, "p_group 应由 &p 的总线 p 驱动")

    def test_g_group_driven_by_comb_operands(self):
        """g_group = g[3] | (g[2]&p[3]) | ... → 含 g[3]/g[2]/p[3] 等操作数位."""
        drv = self._drivers()
        scope = "carry_lookahead_adder.generators[0].lookahead_generator_x4"
        srcs = set(drv.get(f"{scope}.g_group", []))
        for sig in ("g[3]", "g[2]", "p[3]"):
            self.assertIn(f"{scope}.{sig}", srcs, f"g_group 应由 {sig} 参与驱动")

    def test_direct_instance_internals_driven(self):
        """直接实例 (非 generate) carry_lookahead_adder.lookahead_generator_x4 同样驱动."""
        drv = self._drivers()
        dst = "carry_lookahead_adder.lookahead_generator_x4.g_group"
        self.assertGreater(len(drv.get(dst, [])), 0,
                           "直接实例 g_group 应被内部驱动 (inst==type 顶层形态)")
        self.assertIsNotNone(self.g.get_node("carry_lookahead_adder.lookahead_generator_x4"),
                             "直接实例节点应存在")


if __name__ == "__main__":
    unittest.main()
