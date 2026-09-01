"""
[iter_094] T8: alias 方向语义 1:1 truth

1:1 truth 金标准: alias 的**方向语义** — SV 规范 alias LHS = target, RHS = source,
驱动方向 source → target。方向反了是静默错误, 必须锁定。

Fixture: golden_dataflow_34_alias.sv (alias_demo)
    alias x = a;  alias y = b;  alias t = b;  alias z = t;

1:1 预期 (实测于 iter_094):
- 6 节点: a, b, t, x, y, z
- 4 条 DRIVER 边: a→x, b→y, b→t, t→z (alias 链 b→t→z)
"""
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "src"))

import unittest  # noqa: E402

from trace.unified_tracer import UnifiedTracer  # noqa: E402

FIXTURE_DIR = _REPO_ROOT / "sim" / "tests" / "fixtures" / "golden_mini"


def _build_graph(fn: str):
    path = FIXTURE_DIR / fn
    tracer = UnifiedTracer(sources={str(path): path.read_text()}, log_level="ERROR")
    return tracer.build_graph(use_cache=False)


class TestAliasTruth(unittest.TestCase):
    """[1:1 truth] golden_dataflow_34_alias: alias 方向语义"""

    @classmethod
    def setUpClass(cls):
        cls.g = _build_graph("golden_dataflow_34_alias.sv")
        cls.m = "alias_demo"

    def test_node_set_exact(self):
        """节点集精确: a, b, t, x, y, z."""
        expected = {f"{self.m}.a", f"{self.m}.b", f"{self.m}.t",
                    f"{self.m}.x", f"{self.m}.y", f"{self.m}.z"}
        self.assertEqual(set(self.g.nodes()), expected, "alias_demo 节点集偏离")

    def test_alias_direction(self):
        """方向精确: alias LHS=target ← RHS=source (source → target 驱动)."""
        m = self.m
        expected = {
            (f"{m}.a", f"{m}.x", "DRIVER"),   # alias x = a → a 驱动 x
            (f"{m}.b", f"{m}.y", "DRIVER"),   # alias y = b → b 驱动 y
            (f"{m}.b", f"{m}.t", "DRIVER"),   # alias t = b → b 驱动 t
            (f"{m}.t", f"{m}.z", "DRIVER"),   # alias z = t → t 驱动 z (链)
        }
        actual = set()
        for s, d in self.g.edges():
            for e in self.g._edge_data.get((s, d), []):
                actual.add((s, d, e.kind.name))
        self.assertEqual(actual, expected, "alias 方向偏离 (source→target)")

    def test_no_reverse_edges(self):
        """无反向边: 不存在 x→a / y→b / z→t (方向反 = 静默错误)."""
        m = self.m
        reverse_pairs = {(f"{m}.x", f"{m}.a"), (f"{m}.y", f"{m}.b"),
                         (f"{m}.t", f"{m}.b"), (f"{m}.z", f"{m}.t")}
        actual = set(self.g.edges())
        self.assertEqual(actual & reverse_pairs, set(),
                         "alias 反向边不应存在 (LHS 不是源)")


if __name__ == "__main__":
    unittest.main()
