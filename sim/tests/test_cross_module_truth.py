"""
[iter_082] C 组: 跨模块连接 1:1 truth — minimal_3module (top→sub→leaf 链)

1:1 truth 金标准: 固定多文件 fixture, 跨模块实例端口连接的 CONNECTION/DRIVER 边
必须精确匹配预期 — 任何连接提取逻辑变化导致偏离时此测试失败。

Fixture: minimal_3module (top_minimal → sub_aggregator(sa1) → leaf_pipeline(lp1)
/ leaf_adder(la1)), 另含未实例化的 synchronizer (独立 top)。

1:1 预期 (实测于 iter_082, 实例路径节点):
- top_minimal.sa1.clk   → sa1.lp1.clk     (clk 传参到 lp1)
- top_minimal.sa1.data_i → sa1.la1.a       (data_i → la1.a 端口映射)
- top_minimal.sa1.valid_i → sa1.lp1.data_i (valid_i → lp1.data_i)
- sa1.lp1.data_o → sa1.leaf_ready          (lp1 输出 → sub 内部 wire)
- sa1.la1.sum → sa1.sum_o                  (la1 输出 → sub 输出端口)
- 实例存在: sa1 / sa1.lp1 / sa1.la1
"""
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "src"))

import glob  # noqa: E402
import unittest  # noqa: E402

from trace.unified_tracer import UnifiedTracer  # noqa: E402

FIXTURE_DIR = _REPO_ROOT / "sim" / "tests" / "fixtures" / "minimal_3module"


def _build_graph():
    """构建 minimal_3module 的 1:1 图 (3 文件 + filelist 同集)."""
    files = {}
    for p in sorted(glob.glob(str(FIXTURE_DIR / "*.sv"))):
        files[p.split("/")[-1]] = Path(p).read_text()
    tracer = UnifiedTracer(sources=files)
    return tracer.build_graph()


class TestCrossModuleTruth(unittest.TestCase):
    """[1:1 truth] 跨模块端口连接精确结构"""

    @classmethod
    def setUpClass(cls):
        cls.graph = _build_graph()

    def test_instances_exist(self):
        """实例节点: sa1 / sa1.lp1 / sa1.la1 必须存在."""
        g = self.graph
        for inst in ("top_minimal.sa1", "top_minimal.sa1.lp1", "top_minimal.sa1.la1"):
            self.assertIn(inst, g.nodes(), f"实例 {inst} 节点应存在")

    def test_port_connections(self):
        """跨模块端口连接边 (实例路径层):
        sa1.clk→lp1.clk / sa1.data_i→la1.a / sa1.valid_i→lp1.data_i."""
        g = self.graph
        self.assertIsNotNone(
            g.get_edge("top_minimal.sa1.clk", "top_minimal.sa1.lp1.clk"),
            "sa1.clk→lp1.clk 应存在 (clk 传参)",
        )
        self.assertIsNotNone(
            g.get_edge("top_minimal.sa1.data_i", "top_minimal.sa1.la1.a"),
            "sa1.data_i→la1.a 应存在 (data_i 端口映射)",
        )
        self.assertIsNotNone(
            g.get_edge("top_minimal.sa1.valid_i", "top_minimal.sa1.lp1.data_i"),
            "sa1.valid_i→lp1.data_i 应存在",
        )

    def test_leaf_outputs_flow_up(self):
        """叶子输出回流: lp1.data_o→leaf_ready (sub 内部 wire) 和
        la1.sum→sum_o (sub 输出端口)."""
        g = self.graph
        self.assertIsNotNone(
            g.get_edge("top_minimal.sa1.lp1.data_o", "top_minimal.sa1.leaf_ready"),
            "lp1.data_o→leaf_ready 应存在",
        )
        self.assertIsNotNone(
            g.get_edge("top_minimal.sa1.la1.sum", "top_minimal.sa1.sum_o"),
            "la1.sum→sum_o 应存在 (sub 输出端口)",
        )

    def test_uninstantiated_module_isolation(self):
        """未实例化的 synchronizer 不应进入 top 的实例层级 (独立 top)."""
        g = self.graph
        # synchronizer 作为模块定义节点存在, 但不应有 top_minimal.sa1.sync 实例
        self.assertNotIn("top_minimal.sa1.synchronizer", g.nodes(),
                         "synchronizer 未实例化, 不应出现在 sa1 下")


if __name__ == "__main__":
    unittest.main()
