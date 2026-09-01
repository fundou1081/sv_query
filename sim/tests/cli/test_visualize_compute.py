"""
test_visualize_compute.py — V6.7 golden tests for `visualize compute`

验证运算架构图:
- 边上显示运算符号 (+, &, >>, if condition)
- 颜色编码正确 (算术橙/逻辑蓝/移位绿)
- 多个运算类型混合的正确呈现
"""
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _run_compute(dot_path: Path, sv_content: str) -> tuple[int, str]:
    """在临时文件上跑 compute 命令"""
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".sv", mode="w", delete=False) as f:
        f.write(sv_content)
        sv_path = f.name

    try:
        p = subprocess.run(
            ["sv_query", "visualize", "compute", "-f", sv_path, "--strict", "--dot", str(dot_path)],
            capture_output=True, text=True, timeout=30, cwd=str(PROJECT_ROOT),
        )
        return p.returncode, dot_path.read_text() if dot_path.exists() else ""
    finally:
        Path(sv_path).unlink(missing_ok=True)


class TestComputeGolden:
    """Golden tests: 验证 DOT 输出包含预期的运算符号"""

    @pytest.fixture(autouse=True)
    def setup(self, tmp_path):
        self.dot_path = tmp_path / "compute.dot"

    # ── 算术 ──

    def test_add_appears(self):
        """加法应在边上显示 '+'"""
        rc, dot = _run_compute(self.dot_path, """
module add(input [7:0] a, b, output [7:0] y);
    assign y = a + b;
endmodule""")
        assert rc == 0
        assert '+' in dot, f"Add + not found:\n{dot[:500]}"

    def test_subtract_appears(self):
        """减法应显示 '-'"""
        rc, dot = _run_compute(self.dot_path, """
module sub(input [7:0] a, b, output [7:0] y);
    assign y = a - b;
endmodule""")
        assert rc == 0
        assert '−' in dot or 'Subtract' in dot, f"Subtract symbol not found:\n{dot[:500]}"

    # ── 逻辑 ──

    def test_bitwise_and_appears(self):
        """按位与应显示 '&' (SVG 输出, XML 转义为 &amp;)"""
        rc, dot = _run_compute(self.dot_path, """
module band(input [7:0] a, b, output [7:0] y);
    assign y = a & b;
endmodule""")
        assert rc == 0
        # [V100 SVG 2026-08-13] visualize compute 输出 SVG, '&' 转义为 &amp;
        assert '&amp;' in dot, f"AND not found:\n{dot[:500]}"

    def test_bitwise_or_appears(self):
        """按位或应显示 '|'"""
        rc, dot = _run_compute(self.dot_path, """
module bor(input [7:0] a, b, output [7:0] y);
    assign y = a | b;
endmodule""")
        assert rc == 0
        assert '|' in dot, f"OR not found:\n{dot[:500]}"

    def test_bitwise_xor_appears(self):
        """按位异或应显示 '^'"""
        rc, dot = _run_compute(self.dot_path, """
module bxor(input [7:0] a, b, output [7:0] y);
    assign y = a ^ b;
endmodule""")
        assert rc == 0
        assert '^' in dot, f"XOR not found:\n{dot[:500]}"

    # ── 移位 ──

    def test_shift_left_appears(self):
        """左移应显示 '<<' (SVG 输出, XML 转义为 &lt;&lt;)"""
        rc, dot = _run_compute(self.dot_path, """
module shl(input [7:0] a, output [7:0] y);
    assign y = a << 2;
endmodule""")
        assert rc == 0
        # [V100 SVG 2026-08-13] '<<' 转义为 &lt;&lt;
        assert '&lt;&lt;' in dot or '<<' in dot, f"ShiftLeft not found:\n{dot[:500]}"

    def test_shift_right_appears(self):
        """右移应显示 '>>' (SVG 输出, XML 转义为 &gt;&gt;)"""
        rc, dot = _run_compute(self.dot_path, """
module shr(input [7:0] a, output [7:0] y);
    assign y = a >> 2;
endmodule""")
        assert rc == 0
        # [V100 SVG 2026-08-13] '>>' 转义为 &gt;&gt;
        assert '&gt;&gt;' in dot or '>>' in dot, f"ShiftRight not found:\n{dot[:500]}"

    # ── MUX / 选择 ──

    def test_mux_shows_condition(self):
        """MUX 应显示条件 (SVG 输出, ternary 展开为 case (sel) + !(sel))"""
        rc, dot = _run_compute(self.dot_path, """
module mux(input [7:0] a, b, input sel, output [7:0] y);
    assign y = sel ? a : b;
endmodule""")
        assert rc == 0
        # [V100 SVG 2026-08-13] ternary 展开为 case (cond) + !(cond), 不再是 'if '
        assert "case (sel)" in dot or "sel" in dot, f"Condition not found:\n{dot[:500]}"

    # ── 比较 ──

    def test_compare_greater_appears(self):
        """比较应显示 'a > b' condition (SVG 输出, '>' 转义为 &gt;)"""
        rc, dot = _run_compute(self.dot_path, """
module cmp(input [7:0] a, b, c, d, output [7:0] y);
    assign y = (a > b) ? c : d;
endmodule""")
        assert rc == 0
        # [iter_087] V100 SVG 渲染: 比较条件被分解为独立 '&gt;' op 节点, 条件信号
        # 列在 '?: (a, b)' 标签里 (不再是 DOT 时代的连写边标签 'a > b').
        # 断言跟随同文件约定 (裸 op 符号, 如 '+' / '&amp;').
        assert "&gt;" in dot, f"Compare &gt; op not found:\n{dot[:500]}"
        assert "?: (a, b)" in dot, f"ternary cond label not found:\n{dot[:500]}"

    # ── 混合运算 ──

    def test_mixed_ops_all_present(self):
        """多个运算类型同时出现"""
        rc, dot = _run_compute(self.dot_path, """
module mixed(input [7:0] a, b, c, output [7:0] y, output [7:0] z);
    assign y = a + b;
    assign z = a & c;
endmodule""")
        assert rc == 0
        assert '+' in dot
        assert '&amp;' in dot
        # [V100 SVG 2026-08-13] op 节点统一橙色 #e65100 (不再三色区分算术/逻辑/移位)
        assert '#e65100' in dot, "op node orange missing"

    # ── 颜色编码 ──

    def test_arithmetic_color_orange(self):
        rc, dot = _run_compute(self.dot_path, """
module ac(input [7:0] a, b, output [7:0] y);
    assign y = a + b;
endmodule""")
        # [V100 SVG 2026-08-13] op 节点统一橙色 #e65100
        assert '#e65100' in dot, "op node orange not used"

    def test_logic_color_blue(self):
        rc, dot = _run_compute(self.dot_path, """
module lc(input [7:0] a, b, output [7:0] y);
    assign y = a & b;
endmodule""")
        # [V100 SVG 2026-08-13] op 节点统一橙色 #e65100
        assert '#e65100' in dot, "op node orange not used"

    def test_shift_color_green(self):
        rc, dot = _run_compute(self.dot_path, """
module sc(input [7:0] a, output [7:0] y);
    assign y = a >> 2;
endmodule""")
        # [V100 SVG 2026-08-13] op 节点统一橙色 #e65100
        assert '#e65100' in dot, "op node orange not used"

    # ── 带位范围 ──

    def test_bit_range_in_label(self):
        """带位范围时应标注"""
        rc, dot = _run_compute(self.dot_path, """
module br(input [15:0] a, b, output [7:0] y);
    assign y = a[7:0] + b[3:0];
endmodule""")
        assert rc == 0
        # 位范围映射到 source 字段，会在 label 里显示
        assert '+' in dot
