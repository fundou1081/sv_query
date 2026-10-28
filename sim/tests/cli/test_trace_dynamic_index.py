"""[iter_308 / PLAN P14.1] 动态索引（`mem[i]`）显式 unknown 标记。

动态 memory 读的图表示是 `mem --(expr="mem[i]")--> y`（目标节点仍是数组），
查询只能给出"可能来源"，不应被当作位/总线精确答案：
  - signal.precision = "unknown"
  - signal.dynamic_index = true
  - 节点若本身是动态索引（mem[i]）precision=unknown
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _run(cmd: str, sig: str, src: str, tmp_path: Path, *extra: str) -> dict:
    p = tmp_path / "t.sv"
    p.write_text(src)
    r = subprocess.run(
        ["sv_query", "trace", cmd, sig, "--file", str(p), "--json", "--no-cache", *extra],
        capture_output=True, text=True, timeout=60, cwd=str(PROJECT_ROOT),
    )
    assert r.returncode == 0, r.stderr[-300:]
    return json.loads(r.stdout)["result"]["signals"][0]


DYN = """
module top(input [7:0] d, input [1:0] i, output [7:0] y, output z);
  logic [7:0] mem [0:3];
  assign mem[1] = d;
  assign y = mem[i];
  assign z = y[3];
endmodule
"""

STATIC = """
module top(input [7:0] d, output [7:0] y, output z);
  logic [7:0] mem [0:3];
  assign mem[1] = d;
  assign y = mem[1];
  assign z = y[3];
endmodule
"""


class TestDynamicIndex:
    def test_dynamic_read_fanin_unknown(self, tmp_path):
        s = _run("fanin", "top.y", DYN, tmp_path)
        assert s["ok"] if "ok" in s else True
        assert s["precision"] == "unknown"
        assert s["dynamic_index"] is True

    def test_dynamic_bit_query_unknown(self, tmp_path):
        s = _run("fanin", "top.y[3]", DYN, tmp_path)
        assert s["precision"] == "unknown"
        assert s["dynamic_index"] is True

    def test_dynamic_read_fanout_unknown(self, tmp_path):
        s = _run("fanout", "top.mem", DYN, tmp_path)
        assert s["precision"] == "unknown"
        assert s["dynamic_index"] is True
        assert [x["id"] for x in s["loads"]] == ["top.y"]

    def test_dynamic_element_node_precision(self, tmp_path):
        s = _run("fanin", "top.mem[i]", DYN, tmp_path)
        assert s["precision"] == "unknown"
        assert s["dynamic_index"] is True

    def test_static_memory_not_marked_dynamic(self, tmp_path):
        s = _run("fanin", "top.z", STATIC, tmp_path)
        assert s["dynamic_index"] is False
        assert s["precision"] == "bus"  # 标量总线查询（非位查询）
        b = _run("fanin", "top.y[3]", STATIC, tmp_path)
        assert b["dynamic_index"] is False
        assert b["precision"] == "bit"


DEEP = """
module top(input [7:0] d, input [1:0] i, output [7:0] y, output [7:0] z);
  logic [7:0] mem [0:3];
  logic [7:0] t;
  assign mem[1] = d;
  assign t = mem[i];
  assign y = t + 8'd1;
  assign z = y;
endmodule
"""

DYN_WRITE = """
module top(input [7:0] d, input [1:0] i, output [7:0] y, output z);
  logic [7:0] mem [0:3];
  always_comb mem[i] = d;
  assign y = mem[1];
  assign z = y[3];
endmodule
"""

PARAM_COLLISION = """
module sub(input [7:0] P, output [7:0] q);
  assign q = P;
endmodule
module top #(parameter int P = 4) (input [7:0] a, output [7:0] y);
  logic [7:0] s;
  sub u(.P(s), .q());
  assign y = a[P-1:0];
endmodule
"""


class TestDeepDynamicProvenance:
    """[iter_310 / PLAN P16] 动态索引沿数据流递归传播（不只查询根直接边）。"""

    def test_deep_chain_fanin_all(self, tmp_path):
        s = _run("fanin", "top.y", DEEP, tmp_path)
        assert s["precision"] == "unknown"
        assert s["dynamic_index"] is True
        assert any(d["dynamic_index"] for d in s["drivers"])

    def test_deep_chain_depth1(self, tmp_path):
        """depth=1 只返回 t，但 t 是动态派生 → 仍要标 unknown。"""
        s = _run("fanin", "top.y", DEEP, tmp_path, "--depth", "1")
        assert [d["id"] for d in s["drivers"]] == ["top.t"]
        assert s["precision"] == "unknown"
        assert s["dynamic_index"] is True

    def test_deep_fanout(self, tmp_path):
        s = _run("fanout", "top.mem", DEEP, tmp_path)
        assert s["precision"] == "unknown"
        assert s["dynamic_index"] is True
        assert all(x["dynamic_index"] for x in s["loads"])

    def test_dynamic_write_taints_static_read(self, tmp_path):
        """always_comb mem[i]=d 之后，静态读 mem[1] 也不能算精确。"""
        s = _run("fanin", "top.z", DYN_WRITE, tmp_path)
        assert s["precision"] == "unknown"
        assert s["dynamic_index"] is True
        assert all(d["dynamic_index"] for d in s["drivers"])

    def test_parameter_name_collision_not_dynamic(self, tmp_path):
        """参数 P 与其它模块端口同名时不能误判为动态索引。"""
        s = _run("fanin", "top.y", PARAM_COLLISION, tmp_path)
        assert s["dynamic_index"] is False
        assert s["precision"] == "bus"
