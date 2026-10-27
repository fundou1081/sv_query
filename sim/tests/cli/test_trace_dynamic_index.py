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


def _run(cmd: str, sig: str, src: str, tmp_path: Path) -> dict:
    p = tmp_path / "t.sv"
    p.write_text(src)
    r = subprocess.run(
        ["sv_query", "trace", cmd, sig, "--file", str(p), "--json", "--no-cache"],
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
