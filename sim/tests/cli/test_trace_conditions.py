"""[iter_318 / PLAN P22.1] fanin/fanout 输出直接边条件。

- signal.conditions: 查询端点直接边条件并集（去重）
- node.condition: 该结果节点直接边的条件（多条边用 " | " 连接）
- node.conditions: 原始列表
- 无条件的普通连接: 字段存在且为空
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


IF_ELSE = """
module top(input sel, input [7:0] a,b, output reg [7:0] y);
  always_comb if (sel) y = a; else y = b;
endmodule
"""

TERNARY = """
module top(input sel, input [7:0] a,b, output [7:0] y);
  assign y = sel ? a : b;
endmodule
"""

PLAIN = """
module top(input [7:0] a, output [7:0] y);
  assign y = a;
endmodule
"""

FANOUT = """
module top(input sel, input [7:0] a, output reg [7:0] x);
  always_comb if (sel) x = a; else x = 8'd0;
endmodule
"""

NESTED = """
module top(input c1, c2, input [7:0] a, output reg [7:0] y);
  always_comb begin
    if (c1)
      if (c2) y = a;
      else y = 8'd0;
    else y = 8'd1;
  end
endmodule
"""


class TestTraceConditions:
    def test_fanin_if_else(self, tmp_path):
        s = _run("fanin", "top.y", IF_ELSE, tmp_path)
        assert set(s["conditions"]) == {"sel", "!sel"}
        by_id = {d["id"]: d for d in s["drivers"]}
        assert by_id["top.a"]["condition"] == "sel"
        assert by_id["top.b"]["condition"] == "!sel"
        assert by_id["top.a"]["conditions"] == ["sel"]

    def test_fanin_ternary(self, tmp_path):
        s = _run("fanin", "top.y", TERNARY, tmp_path)
        by_id = {d["id"]: d for d in s["drivers"]}
        assert by_id["top.a"]["conditions"] == ["sel"]
        assert by_id["top.b"]["conditions"] == ["!(sel)"]

    def test_fanout_condition(self, tmp_path):
        s = _run("fanout", "top.a", FANOUT, tmp_path)
        assert s["conditions"] == ["sel"]
        assert s["loads"][0]["condition"] == "sel"

    def test_nested_condition_chain(self, tmp_path):
        s = _run("fanin", "top.y", NESTED, tmp_path)
        a = next(d for d in s["drivers"] if d["id"] == "top.a")
        assert "c1" in a["condition"] and "c2" in a["condition"]

    def test_no_condition_fields_present(self, tmp_path):
        s = _run("fanin", "top.y", PLAIN, tmp_path)
        assert s["conditions"] == []
        assert s["drivers"][0]["condition"] == ""
        assert s["drivers"][0]["conditions"] == []
