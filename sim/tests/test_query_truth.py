"""
[iter_098] T12: trace 查询精确 driver 集 1:1 truth

1:1 truth 金标准: 固定 fixture 上 trace_fanin / trace_fanout 的**精确结果集**
(不是 ≥N 下界) — "谁驱动这个信号" 的核心产品承诺。任何图构建或查询遍历逻辑
变化导致 driver/load 集合偏离时此测试失败。

Fixtures:
- golden_dataflow_5_combined.sv (combined): wire 链 + 位选
- golden_dataflow_9_case.sv (with_case): case 多分支

1:1 预期 (实测于 iter_098):
- fanin(combined.y) = {combined.prod[15:8]} — y 的唯一直接驱动 (8'd128 常量无节点)
- fanin(combined.sum) = {combined.a, combined.b}
- fanout(combined.a) = {combined.sum, combined.prod} — 经 sum 透传
- fanin(with_case.y) = {a, b, c, d} — case 全分支源 (去重)
"""
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "src"))

import unittest  # noqa: E402

from trace.unified_tracer import UnifiedTracer  # noqa: E402

FIXTURE_DIR = _REPO_ROOT / "sim" / "tests" / "fixtures" / "golden_mini"


def _tracer(fn: str):
    path = FIXTURE_DIR / fn
    t = UnifiedTracer(sources={str(path): path.read_text()}, log_level="ERROR")
    t.build_graph(use_cache=False)
    return t


def _ids(nodes) -> set[str]:
    return {getattr(n, "id", n) for n in nodes}


class TestCombinedQueryTruth(unittest.TestCase):
    """[1:1 truth] combined: fanin/fanout 精确集"""

    @classmethod
    def setUpClass(cls):
        cls.t = _tracer("golden_dataflow_5_combined.sv")

    def test_fanin_y_exact(self):
        """fanin(combined.y) 精确 = {combined.prod[15:8]} (8'd128 常量无节点)."""
        self.assertEqual(
            _ids(self.t.trace_fanin("combined.y", depth=None)),
            {"combined.prod[15:8]"},
            "y 的直接驱动集偏离")

    def test_fanin_sum_exact(self):
        """fanin(combined.sum) 精确 = {a, b} (wire sum = a + b)."""
        self.assertEqual(
            _ids(self.t.trace_fanin("combined.sum", depth=None)),
            {"combined.a", "combined.b"},
            "sum 的驱动集偏离")

    def test_fanout_a_exact(self):
        """fanout(combined.a) 精确 = {sum, prod} (a→sum→prod 链)."""
        self.assertEqual(
            _ids(self.t.trace_fanout("combined.a", depth=None)),
            {"combined.sum", "combined.prod"},
            "a 的负载集偏离")

    def test_fanin_bit_select_boundary(self):
        """位选边界: prod[15:8] 无 DRIVER 驱动 (BIT_SELECT 回边不产生 fanin 源)."""
        self.assertEqual(
            _ids(self.t.trace_fanin("combined.prod[15:8]", depth=None)),
            set(),
            "位选节点无驱动源 (深度语义锁定)")

    def test_fanin_y_no_transitive(self):
        """fanin(y) 不透传到 prod/sum (默认深度 = 直接驱动)."""
        r = _ids(self.t.trace_fanin("combined.y", depth=None))
        self.assertNotIn("combined.prod", r)
        self.assertNotIn("combined.sum", r)


class TestWithCaseQueryTruth(unittest.TestCase):
    """[1:1 truth] with_case: case 多分支 fanin 精确集"""

    @classmethod
    def setUpClass(cls):
        cls.t = _tracer("golden_dataflow_9_case.sv")

    def test_fanin_y_exact(self):
        """fanin(with_case.y) 精确 = {a, b, c, d} (case 全分支源, 去重)."""
        self.assertEqual(
            _ids(self.t.trace_fanin("with_case.y", depth=None)),
            {"with_case.a", "with_case.b", "with_case.c", "with_case.d"},
            "case 分支驱动集偏离")

    def test_fanin_y_no_sel(self):
        """sel 不是 y 的驱动 (sel 是分支选择, 不是数据源)."""
        self.assertNotIn("with_case.sel",
                         _ids(self.t.trace_fanin("with_case.y", depth=None)),
                         "sel 不应出现在 y 的驱动集")

    def test_fanin_sel_exact(self):
        """fanin(with_case.sel) = {} (sel 无驱动, 是输入端口)."""
        self.assertEqual(_ids(self.t.trace_fanin("with_case.sel", depth=None)),
                         set(), "sel 输入端口无驱动")


if __name__ == "__main__":
    unittest.main()
