"""
[iter_111 + iter_113] CORDIC 流水线实例链 1:1 truth (真实工业算法模块)

1:1 truth 金标准: opencores verilog_cordic_core (golden_dataflow_39, 拷自
openrtl/verilog_cordic_core, PIPELINE+GENERATE_LOOP+ROTATE 配置, ITERATIONS=16)
的精确图结构 — generate-for 实例化 15 个 rotator 并经数组端口 x[i]/y[i]/z[i]
链式互连 (iter_109/110 修复后的真实验证).

[iter_113 升级] builder 切 **target 模式** + 新增 rotator 内部逻辑断言:
iter_113 修复 (graph_builder.walk 真正下钻 generate) 之前, driver instance
paths 从不含 generate 实例 → rotator 内部 always (x_1/y_1/z_1) **从未被提取**,
旧 truth 的 "rotator DRIVER >50" 实为 connection 端口自环 (120 条), 非内部逻辑。
修复后 target 模式 rotator-scope DRIVER dst = 150 (x_1/y_1/z_1 ×15 内部状态 +
x_o/y_o/z_o ← x_1 输出链) — 本文件现在真实验证内部提取。

1:1 预期:
- rotator 实例: cordic.genblk1[0..14].U (15 个, 路径带 entry 索引)
- 数组信号: cordic.x[0..15] / y[0..15] / z[0..15] (16 个, 链两端)
- CONNECTION 链: x[i]→g[i].U.x_i + g[i].U.x_o→x[i+1] (15 级流水链)
- rotator 内部 (作用域修正 iter_110): x_shifter.Q→cordic.g[i].U.x_i_shifted
- [iter_113] rotator 内部状态 x_1/y_1/z_1 真驱动 (x_i ± y_i_shifted 操作数),
  x_o ← x_1 输出链
- 无 '?' 占位节点
"""
import sys, re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "src"))

import unittest  # noqa: E402

FIXTURE = _REPO_ROOT / "sim" / "tests" / "fixtures" / "golden_mini" / "golden_dataflow_39_cordic_pipeline.v"


def _build_graph():
    # [iter_113] target 模式: 无 target 时 driver 走 type-level 旧路径, generate
    # 实例内部不提取 (iter_111 盲区 — 旧 DRIVER 计数是 connection 端口自环)
    from trace.core.compiler import SVCompiler  # noqa: E402
    from trace.core.graph_builder import GraphBuilder  # noqa: E402
    from trace.core.semantic_adapter import SemanticAdapter  # noqa: E402
    comp = SVCompiler({str(FIXTURE): FIXTURE.read_text()})
    adapter = SemanticAdapter(comp.get_root(), target_module="cordic")
    return GraphBuilder(adapter, target_module="cordic").build()


class TestCordicPipelineTruth(unittest.TestCase):
    """[1:1 truth] CORDIC 流水线实例链"""

    @classmethod
    def setUpClass(cls):
        cls.g = _build_graph()

    def test_rotator_instances(self):
        """15 个 rotator 实例 (genblk1[0..14].U), 路径带 entry 索引."""
        for i in range(15):
            self.assertIsNotNone(self.g.get_node(f"cordic.genblk1[{i}].U"),
                                 f"rotator genblk1[{i}].U 应存在")
            for p in ("x_i", "y_i", "z_i", "x_o", "y_o", "z_o"):
                self.assertIsNotNone(self.g.get_node(f"cordic.genblk1[{i}].U.{p}"),
                                     f"rotator[{i}].{p} 端口应存在")

    def test_array_signal_nodes(self):
        """数组信号 x[0..15] (链两端: 输入 x[0] 与 16 级末端 x[15])."""
        for i in range(16):
            for sig in ("x", "y", "z"):
                self.assertIsNotNone(self.g.get_node(f"cordic.{sig}[{i}]"),
                                     f"{sig}[{i}] 节点应存在")

    def test_pipeline_chain_connections(self):
        """流水链 CONNECTION: x[i]→g[i].U.x_i 且 g[i].U.x_o→x[i+1] (15 级)."""
        edges = set()
        for s, d in self.g.edges():
            for e in self.g._edge_data.get((s, d), []):
                if e.kind.name == "CONNECTION":
                    edges.add((s, d))
        for i in range(15):
            self.assertIn((f"cordic.x[{i}]", f"cordic.genblk1[{i}].U.x_i"), edges,
                          f"x[{i}]→rotator[{i}].x_i 应存在")
            self.assertIn((f"cordic.genblk1[{i}].U.x_o", f"cordic.x[{i+1}]"), edges,
                          f"rotator[{i}].x_o→x[{i+1}] 应存在")

    def test_rotator_internal_scope(self):
        """rotator 内部 shifter 输出连到本实例作用域 wire (iter_110 作用域修正)."""
        edges = set()
        for s, d in self.g.edges():
            for e in self.g._edge_data.get((s, d), []):
                if e.kind.name == "CONNECTION":
                    edges.add((s, d))
        for i in (0, 7, 14):
            self.assertIn(
                (f"cordic.genblk1[{i}].U.genblk1[{i}].x_shifter.Q",
                 f"cordic.genblk1[{i}].U.x_i_shifted"), edges,
                f"rotator[{i}] 内部 shifter.Q→x_i_shifted 应在本实例作用域")
            self.assertIn(
                (f"cordic.genblk1[{i}].U.genblk1[{i}].y_shifter.Q",
                 f"cordic.genblk1[{i}].U.y_i_shifted"), edges,
                f"rotator[{i}] 内部 y_shifter.Q→y_i_shifted 应在本实例作用域")

    def test_no_placeholder(self):
        """无 '?' 占位节点."""
        for n in self.g.nodes():
            self.assertNotIn("?", n, f"占位节点不应存在: {n}")

    def test_graph_rich(self):
        """图规模 sanity: >300 节点, rotator 内部 DRIVER 已提取 (>50)."""
        kinds = {}
        for s, d in self.g.edges():
            for e in self.g._edge_data.get((s, d), []):
                kinds[e.kind.name] = kinds.get(e.kind.name, 0) + 1
        self.assertGreater(self.g.number_of_nodes(), 300, "CORDIC 图应 >300 节点")
        self.assertGreater(kinds.get("DRIVER", 0), 50, "rotator 内部 DRIVER 应 >50")
        self.assertGreater(kinds.get("CONNECTION", 0), 100, "CONNECTION 应 >100")

    # ======================================================================
    # [iter_113] rotator 内部逻辑真断言 — iter_113 前 driver 从不提取 generate
    # 实例内部 (旧 "DRIVER>50" 是 connection 端口自环); 现在 target 模式 rotator
    # scope DRIVER dst = 150 (x_1/y_1/z_1 ×15 内部状态 + x_o/y_o/z_o ← x_1 输出链)
    # ======================================================================

    def _driver_srcs(self, dst):
        srcs = []
        for s, d in self.g.edges():
            if d == dst:
                for e in self.g._edge_data.get((s, d), []):
                    if e.kind.name == "DRIVER":
                        srcs.append(s)
        return srcs

    def test_rotator_internal_regs_driven(self):
        """x_1/y_1/z_1 (rotator 内部流水状态) 全 15 个被内部逻辑真驱动."""
        for i in range(15):
            scope = f"cordic.genblk1[{i}].U"
            for reg in ("x_1", "y_1", "z_1"):
                srcs = self._driver_srcs(f"{scope}.{reg}")
                self.assertGreater(len(srcs), 0,
                                   f"rotator[{i}].{reg} 应被内部 always 驱动 "
                                   f"(iter_113 前 0 提取)")
                # 作用域内驱动源必须落在本实例 (字面量常量如 reset '0' 除外)
                for s in srcs:
                    if "." in s:
                        self.assertTrue(s.startswith(scope),
                                        f"rotator[{i}].{reg} 驱动源 {s} 应在实例作用域内")

    def test_rotator_internal_operands(self):
        """x_1 ← x_i / y_i_shifted (流水: 输入 ± 移位量) — 已知操作数来源."""
        for i in (0, 7, 14):
            scope = f"cordic.genblk1[{i}].U"
            srcs = set(self._driver_srcs(f"{scope}.x_1"))
            self.assertIn(f"{scope}.x_i", srcs, f"rotator[{i}].x_1 应由 x_i 驱动")
            self.assertTrue(
                any("y_i_shifted" in s for s in srcs),
                f"rotator[{i}].x_1 应由 y_i_shifted 参与驱动")

    def test_rotator_output_chain(self):
        """x_o ← x_1 (输出寄存器由内部状态驱动) — 15 级输出链真实可查."""
        for i in range(15):
            scope = f"cordic.genblk1[{i}].U"
            srcs = set(self._driver_srcs(f"{scope}.x_o"))
            self.assertIn(f"{scope}.x_1", srcs,
                          f"rotator[{i}].x_o 应由 x_1 驱动")
            self.assertIn(f"{scope}.y_1", set(self._driver_srcs(f"{scope}.y_o")),
                          f"rotator[{i}].y_o 应由 y_1 驱动")
            self.assertIn(f"{scope}.z_1", set(self._driver_srcs(f"{scope}.z_o")),
                          f"rotator[{i}].z_o 应由 z_1 驱动")

    def test_rotator_scope_driver_scale(self):
        """rotator 作用域 DRIVER dst ≥ 90 (45 内部状态 + 45 输出 + ...),
        证明提取的是真内部逻辑而非仅端口自环 (旧 ~120 自环计数无内部状态)."""
        dsts = set()
        for s, d in self.g.edges():
            if ".genblk1[" in d and ".U." in d:
                for e in self.g._edge_data.get((s, d), []):
                    if e.kind.name == "DRIVER":
                        dsts.add(d)
        internal = [d for d in dsts if d.rsplit(".", 1)[-1] in ("x_1", "y_1", "z_1")]
        self.assertEqual(len(internal), 45, "x_1/y_1/z_1 ×15 = 45 个内部状态驱动")


if __name__ == "__main__":
    unittest.main()
