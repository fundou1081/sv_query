"""
[iter_111] CORDIC 流水线实例链 1:1 truth (真实工业算法模块)

1:1 truth 金标准: opencores verilog_cordic_core (golden_dataflow_39, 拷自
openrtl/verilog_cordic_core, PIPELINE+GENERATE_LOOP+ROTATE 配置, ITERATIONS=16)
的精确图结构 — generate-for 实例化 15 个 rotator 并经数组端口 x[i]/y[i]/z[i]
链式互连 (iter_109/110 修复后的真实验证).

1:1 预期 (实测于 iter_111):
- rotator 实例: cordic.genblk1[0..14].U (15 个, 路径带 entry 索引)
- 数组信号: cordic.x[0..15] / y[0..15] / z[0..15] (16 个, 链两端)
- CONNECTION 链: x[i]→g[i].U.x_i + g[i].U.x_o→x[i+1] (15 级流水链)
- rotator 内部 (作用域修正 iter_110): x_shifter.Q→cordic.g[i].U.x_i_shifted
- 无 '?' 占位节点
"""
import sys, re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "src"))

import unittest  # noqa: E402

from trace.unified_tracer import UnifiedTracer  # noqa: E402

FIXTURE = _REPO_ROOT / "sim" / "tests" / "fixtures" / "golden_mini" / "golden_dataflow_39_cordic_pipeline.v"


def _build_graph():
    tracer = UnifiedTracer(sources={str(FIXTURE): FIXTURE.read_text()}, log_level="ERROR")
    return tracer.build_graph(use_cache=False)


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


if __name__ == "__main__":
    unittest.main()
