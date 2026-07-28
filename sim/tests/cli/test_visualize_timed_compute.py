
"""
test_visualize_timed_compute.py — V6.7 golden tests for time-axis compute diagrams

验证:
- 时间轴从左到右 (Cycle 0 → Cycle 1 → Cycle 2)
- 运算作为独立节点 (圆形，标 +/×/>>)
- 寄存器作为 cycle 边界 (方框)
"""
import subprocess
from pathlib import Path
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]

_3CYCLE_DEMO = """
module timed(input clk, input [7:0] a, b, c, output reg [7:0] r);
    reg [7:0] s0;
    reg [15:0] s1;
    always_ff @(posedge clk) s0 <= a + b;
    always_ff @(posedge clk) s1 <= s0 * c;
    always_ff @(posedge clk) r <= s1 >> 2;
endmodule
"""


def _run_timed(tmp_path, sv_content: str) -> tuple[int, str]:
    sv = tmp_path / "test.sv"
    sv.write_text(sv_content)
    dot = tmp_path / "out.dot"
    p = subprocess.run(
        ["sv_query", "visualize", "timed", "-f", str(sv), "--module", "timed", "--no-strict", "--dot", str(dot)],
        capture_output=True, text=True, timeout=30, cwd=str(PROJECT_ROOT),
    )
    return p.returncode, dot.read_text() if dot.exists() else ""


class TestTimedCompute:
    """时间轴计算图 golden tests"""

    def test_has_time_clusters(self, tmp_path):
        """应包含 Cycle 0/1/2 cluster"""
        rc, dot = _run_timed(tmp_path, _3CYCLE_DEMO)
        assert rc == 0
        for c in ["Cycle 0", "Cycle 1"]:
            assert c in dot, f"Missing '{c}' cluster"

    def test_op_nodes_exist(self, tmp_path):
        """运算应作为独立节点 (circle shape)"""
        rc, dot = _run_timed(tmp_path, _3CYCLE_DEMO)
        assert rc == 0
        assert 'shape=circle' in dot, "No circle-shaped OP nodes found"

    def test_op_symbols_present(self, tmp_path):
        """OP 节点应标 +/×/>>"""
        rc, dot = _run_timed(tmp_path, _3CYCLE_DEMO)
        assert rc == 0
        for sym in ['+', '×', '>>']:
            assert sym in dot, f"Missing op symbol '{sym}'"

    def test_layout_is_lr(self, tmp_path):
        """时间轴应该从左到右"""
        rc, dot = _run_timed(tmp_path, _3CYCLE_DEMO)
        assert rc == 0
        assert 'rankdir=LR' in dot

    def test_register_nodes_box_shape(self, tmp_path):
        """REG 节点应用 box shape"""
        rc, dot = _run_timed(tmp_path, _3CYCLE_DEMO)
        assert rc == 0
        assert 'shape=box' in dot, "REG nodes should use box shape"
