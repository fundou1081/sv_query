"""[iter_313 / PLAN P18.2] 函数调用诚实标记（不 inline）。

图上函数调用是伪信号：`a --(expr="f(a)")--> f --(expr="f")--> y`。
`f` 不能伪装成普通总线：
  - node.function_call = true / precision=unknown
  - 调用结果及下游（含位查询）function_call=true / precision=unknown
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _run(cmd: str, sig: str, src: str, tmp_path: Path,
         *extra: str) -> dict:
    p = tmp_path / "t.sv"
    p.write_text(src)
    r = subprocess.run(
        ["sv_query", "trace", cmd, sig, "--file", str(p), "--json", "--no-cache", *extra],
        capture_output=True, text=True, timeout=60, cwd=str(PROJECT_ROOT),
    )
    assert r.returncode == 0, r.stderr[-300:]
    return json.loads(r.stdout)["result"]["signals"][0]


FUNC = """
module top(input [7:0] a, output [7:0] y, output z);
  function automatic [7:0] f(input [7:0] x);
    f = x + 8'd1;
  endfunction
  assign y = f(a);
  assign z = y[3];
endmodule
"""

FUNC_NOARG = """
module top(input [7:0] a, output [7:0] y);
  function automatic [7:0] f();
    f = 8'd7;
  endfunction
  assign y = f() + a;
endmodule
"""

STATIC = """
module top(input [7:0] a, output [7:0] y);
  assign y = a;
endmodule
"""


class TestFunctionCallHonesty:
    def test_fanin_marks_function(self, tmp_path):
        s = _run("fanin", "top.y", FUNC, tmp_path)
        assert s["precision"] == "unknown"
        assert s["function_call"] is True
        f = next(x for x in s["drivers"] if x["id"] == "top.f")
        assert f["function_call"] is True
        assert f["precision"] == "unknown"

    def test_bit_query_propagates(self, tmp_path):
        """z=y[3] 本身不是函数节点，但 y/y[3] 已标记 → 仍 unknown。"""
        s = _run("fanin", "top.z", FUNC, tmp_path)
        assert s["precision"] == "unknown"
        assert s["function_call"] is True
        assert all(x["function_call"] for x in s["drivers"]
                   if x["id"] in ("top.y[3]", "top.f"))

    def test_fanout_marks_function(self, tmp_path):
        s = _run("fanout", "top.a", FUNC, tmp_path)
        assert s["precision"] == "unknown"
        assert s["function_call"] is True
        assert any(x["id"] == "top.f" and x["function_call"] for x in s["loads"])

    def test_noarg_function(self, tmp_path):
        s = _run("fanin", "top.y", FUNC_NOARG, tmp_path)
        assert s["function_call"] is True
        assert s["precision"] == "unknown"

    def test_static_signal_not_function(self, tmp_path):
        s = _run("fanin", "top.y", STATIC, tmp_path)
        assert s["function_call"] is False
        assert s["precision"] == "bus"
