"""
[iter_097] T11: L4 SVG 布局 1:1 truth (非 generate)

1:1 truth 金标准: 非 generate 数据流的 **SVG 渲染结构** — 端口/信号/op 标签
齐全, op/信号节点分类渲染 (fill 颜色), case 标签与条件边标签。任何渲染层逻辑
变化 (V100 SVG / 标签生成 / 节点分类) 导致偏离时此测试失败。

Fixtures:
- golden_dataflow_5_combined.sv (combined): wire 链 + assign 位选 (+, ×, 8'd128)
- golden_dataflow_9_case.sv (with_case): case 多分支 (case 标签 + 条件边标签)

1:1 预期 (实测于 iter_097):
- combined: 端口 a/b/c/y + 信号 sum/prod + op '+'/'×' + 常量 8'd128;
  op fill #fff3e0 ×5, 信号 fill #fff9c4 ×5
- with_case: 'case (2, b0, b1, b10, default, sel)' 标签 + 4 条条件边标签
  (sel==2'b0 / 2'b1 / 2'b10 / default) + 端口 6 个 + '+' op
"""
import re
import sys
import unittest
import subprocess
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "src"))

FIXTURE_DIR = _REPO_ROOT / "sim" / "tests" / "fixtures" / "golden_mini"


def _render_svg(fixture: str, module: str) -> str:
    """通过 run_cli.py 渲染 SVG (真实端到端路径)."""
    svg_path = Path(f"/tmp/t11_{fixture}.svg")
    proc = subprocess.run(
        [sys.executable, "run_cli.py", "visualize", "dataflow",
         "--file", str(FIXTURE_DIR / fixture),
         "--module", module,
         "--svg", str(svg_path)],
        cwd=_REPO_ROOT, capture_output=True, text=True, timeout=120,
    )
    if not svg_path.exists():
        raise RuntimeError(f"{fixture} SVG render failed: {proc.stderr[-500:]}")
    return svg_path.read_text()


def _labels(svg: str) -> list[str]:
    return [m.strip() for m in re.findall(r"<text[^>]*>([^<]+)</text>", svg)]


def _fill_count(svg: str, fill: str) -> int:
    return len(re.findall(rf'fill="{fill}"', svg))


class TestCombinedLayoutTruth(unittest.TestCase):
    """[1:1 truth] golden_dataflow_5_combined: wire 链 + 位选 SVG 结构"""

    @classmethod
    def setUpClass(cls):
        cls.svg = _render_svg("golden_dataflow_5_combined.sv", "combined")
        cls.labels = _labels(cls.svg)

    def test_svg_root(self):
        """SVG 根 + 标题."""
        self.assertIn("<svg", self.svg)
        self.assertIn("Dataflow: combined", self.labels)

    def test_port_labels(self):
        """端口标签齐全."""
        for p in ("a", "b", "c", "y"):
            self.assertIn(p, self.labels, f"端口 {p} 标签应在")

    def test_signal_labels(self):
        """中间信号标签 (sum/prod)."""
        for s in ("sum", "prod"):
            self.assertIn(s, self.labels, f"信号 {s} 标签应在")

    def test_op_labels(self):
        """op 标签: '+' (add) 和 '×' (mul) 都渲染."""
        self.assertIn("+", self.labels, "加法 op 应渲染")
        self.assertIn("×", self.labels, "乘法 op 应渲染")
        self.assertIn("8'd128", self.labels, "常量 8'd128 应渲染")

    def test_op_signal_fill_counts(self):
        """分类渲染: op 橙 #fff3e0 ×5, 信号黄 #fff9c4 ×5 (结构检查)."""
        self.assertEqual(_fill_count(self.svg, "#fff3e0"), 5, "op 节点数偏离")
        self.assertEqual(_fill_count(self.svg, "#fff9c4"), 5, "信号节点数偏离")


class TestWithCaseLayoutTruth(unittest.TestCase):
    """[1:1 truth] golden_dataflow_9_case: case 分支 SVG 结构"""

    @classmethod
    def setUpClass(cls):
        cls.svg = _render_svg("golden_dataflow_9_case.sv", "with_case")
        cls.labels = _labels(cls.svg)

    def test_case_op_label(self):
        """case op 标签含 'case (' 和分支列表 (排除标题 'Dataflow: ...case')."""
        case_labels = [l for l in self.labels if l.startswith("case (")]
        self.assertTrue(case_labels, "case op 标签应渲染")
        self.assertIn("sel", case_labels[0], "case 标签应含 sel")

    def test_condition_edge_labels(self):
        """4 条条件边标签精确 (分支条件渲染在边上)."""
        for cond in ("sel==2'b0", "sel==2'b1", "sel==2'b10", "sel==default"):
            self.assertIn(cond, self.labels, f"条件边标签 {cond} 应在")

    def test_port_labels(self):
        """端口标签齐全 (含 sel)."""
        for p in ("a", "b", "c", "d", "y", "sel"):
            self.assertIn(p, self.labels, f"端口 {p} 标签应在")

    def test_add_op_in_branch(self):
        """分支 'y = a + b' 的 '+' op 渲染."""
        self.assertIn("+", self.labels, "case 分支加法 op 应渲染")


if __name__ == "__main__":
    unittest.main()
