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
        assert s["condition_truncated"] is False


PATH_CHAIN = """
module top(input c1, c2, input [7:0] a,d, output [7:0] y);
  reg [7:0] t;
  always_comb if (c1) t = a; else t = 8'd0;
  assign y = c2 ? t : d;
endmodule
"""


class TestPathConditionComposition:
    """[iter_319 / PLAN P23.1] depth>1 沿最短路径组合条件。"""

    def test_deep_fanin_composes(self, tmp_path):
        s = _run("fanin", "top.y", PATH_CHAIN, tmp_path)
        a = next(d for d in s["drivers"] if d["id"] == "top.a")
        assert a["condition"] == "(c1) && (c2)"
        assert a["condition_path"] == ["c1", "c2"]
        assert a["conditions"] == ["(c1) && (c2)"]

    def test_deep_fanout_composes(self, tmp_path):
        s = _run("fanout", "top.a", PATH_CHAIN, tmp_path)
        y = next(d for d in s["loads"] if d["id"] == "top.y")
        assert y["condition"] == "(c1) && (c2)"
        assert y["condition_path"] == ["c1", "c2"]

    def test_direct_still_uses_direct_condition(self, tmp_path):
        s = _run("fanin", "top.y", PATH_CHAIN, tmp_path)
        d = next(d for d in s["drivers"] if d["id"] == "top.d")
        assert d["condition"] == "!(c2)"
        assert d["conditions"] == ["!(c2)"]


MULTIPATH = """
module top(input c1,c2,c3, input [7:0] a,b,d, output [7:0] y);
  reg [7:0] t;
  always_comb if (c1) t = a; else t = b;
  assign y = c2 ? t : (c3 ? a : d);
endmodule
"""

DIRECT_MULTI = """
module top(input c1, input [7:0] a,b, output [7:0] y);
  assign y = a;
  assign y = c1 ? a : b;
endmodule
"""


class TestMultiPathOr:
    """[iter_320 / PLAN P24.1] 多路径条件 OR，保留每路径原始条件。"""

    def test_fanin_multi_path_or(self, tmp_path):
        s = _run("fanin", "top.y", MULTIPATH, tmp_path)
        a = next(d for d in s["drivers"] if d["id"] == "top.a")
        # 两条路径：直接分支 + 经 t
        assert len(a["condition_paths"]) == 2
        assert len(a["conditions"]) == 2
        assert "||" in a["condition"]
        assert "!(c2) && c3" in a["condition"]
        assert "(c1) && (c2)" in a["condition"]
        raw_paths = [set(p["path"]) for p in a["condition_paths"]]
        assert {"!(c2) && c3"} in raw_paths
        assert {"c1", "c2"} in raw_paths

    def test_fanout_multi_path_or(self, tmp_path):
        s = _run("fanout", "top.a", MULTIPATH, tmp_path)
        y = next(d for d in s["loads"] if d["id"] == "top.y")
        assert len(y["condition_paths"]) == 2
        assert "||" in y["condition"]

    def test_depth1_does_not_compose(self, tmp_path):
        p = tmp_path / "t.sv"
        p.write_text(MULTIPATH)
        r = subprocess.run(
            ["sv_query", "trace", "fanin", "top.y", "--depth", "1",
             "--file", str(p), "--json", "--no-cache"],
            capture_output=True, text=True, timeout=60, cwd=str(PROJECT_ROOT),
        )
        s = json.loads(r.stdout)["result"]["signals"][0]
        a = next(d for d in s["drivers"] if d["id"] == "top.a")
        assert a["condition"] == "!(c2) && c3"
        assert len(a["condition_paths"]) == 1

    def test_unconditional_path_wins(self, tmp_path):
        s = _run("fanin", "top.y", DIRECT_MULTI, tmp_path)
        a = next(d for d in s["drivers"] if d["id"] == "top.a")
        assert a["condition"] == ""
        assert a["condition_unconditional"] is True
        assert "c1" in a["conditions"]
