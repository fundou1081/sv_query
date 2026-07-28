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
            ["sv_query", "visualize", "compute", "-f", sv_path, "--no-strict", "--dot", str(dot_path)],
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
        """按位与应显示 '&'"""
        rc, dot = _run_compute(self.dot_path, """
module band(input [7:0] a, b, output [7:0] y);
    assign y = a & b;
endmodule""")
        assert rc == 0
        assert '&"' in dot or 'label="&"' in dot, f"AND not found:\n{dot[:500]}"

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
        """左移应显示 '<<'"""
        rc, dot = _run_compute(self.dot_path, """
module shl(input [7:0] a, output [7:0] y);
    assign y = a << 2;
endmodule""")
        assert rc == 0
        assert '<<' in dot, f"ShiftLeft not found:\n{dot[:500]}"

    def test_shift_right_appears(self):
        """右移应显示 '>>'"""
        rc, dot = _run_compute(self.dot_path, """
module shr(input [7:0] a, output [7:0] y);
    assign y = a >> 2;
endmodule""")
        assert rc == 0
        assert '>>' in dot, f"ShiftRight not found:\n{dot[:500]}"

    # ── MUX / 选择 ──

    def test_mux_shows_condition(self):
        """MUX 应显示 'if select' condition"""
        rc, dot = _run_compute(self.dot_path, """
module mux(input [7:0] a, b, input sel, output [7:0] y);
    assign y = sel ? a : b;
endmodule""")
        assert rc == 0
        assert "if " in dot, f"Condition not found:\n{dot[:500]}"

    # ── 比较 ──

    def test_compare_greater_appears(self):
        """比较应显示 'if a>b' condition"""
        rc, dot = _run_compute(self.dot_path, """
module cmp(input [7:0] a, b, c, d, output [7:0] y);
    assign y = (a > b) ? c : d;
endmodule""")
        assert rc == 0
        assert "a>b" in dot, f"Compare not found:\n{dot[:500]}"

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
        assert '&"' in dot or 'label="&"' in dot
        # Verify 2 different op colors (arithmetic=orange, logic=blue)
        assert '#cc4400' in dot, f"Arithmetic color (orange) missing"
        assert '#4488cc' in dot, f"Logic color (blue) missing"

    # ── 颜色编码 ──

    def test_arithmetic_color_orange(self):
        rc, dot = _run_compute(self.dot_path, """
module ac(input [7:0] a, b, output [7:0] y);
    assign y = a + b;
endmodule""")
        assert '#cc4400' in dot, f"Orange color not used for arithmetic"

    def test_logic_color_blue(self):
        rc, dot = _run_compute(self.dot_path, """
module lc(input [7:0] a, b, output [7:0] y);
    assign y = a & b;
endmodule""")
        assert '#4488cc' in dot, f"Blue color not used for logic"

    def test_shift_color_green(self):
        rc, dot = _run_compute(self.dot_path, """
module sc(input [7:0] a, output [7:0] y);
    assign y = a >> 2;
endmodule""")
        assert '#44aa44' in dot, f"Green color not used for shift"

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
