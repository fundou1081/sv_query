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


FUNC_IF = """
module top(input [7:0] a,b,c, output reg [7:0] y);
  function automatic bit f(input [7:0] x); f = x[0]; endfunction
  always_comb begin
    if (f(a)) y = b; else y = c;
  end
endmodule
"""

FUNC_IF_CMP = """
module top(input [7:0] a,b,c, output reg [7:0] y);
  function automatic [7:0] f(input [7:0] x); f = x + 1; endfunction
  always_comb begin
    if (f(a) > 0) y = b; else y = c;
  end
endmodule
"""

FUNC_TERNARY = """
module top(input [7:0] a,b,c, output [7:0] y);
  function automatic bit f(input [7:0] x); f = x[0]; endfunction
  assign y = f(a) ? b : c;
endmodule
"""

FUNC_CASE = """
module top(input [7:0] a,b,c, output reg [7:0] y);
  function automatic [1:0] f(input [7:0] x); f = x[1:0]; endfunction
  always_comb case (f(a))
    2'd0: y = b;
    default: y = c;
  endcase
endmodule
"""

FUNC_CLOCK = """
module top(input [7:0] a,d, output reg [7:0] q);
  function automatic bit f(input [7:0] x); f = x[0]; endfunction
  always_ff @(posedge f(a)) q <= d;
endmodule
"""

FUNC_NAME_COLLISION = """
module sub(input [7:0] x, output [7:0] q);
  function automatic [7:0] f(input [7:0] v); f = v; endfunction
  assign q = f(x);
endmodule
module top(input [7:0] f, output reg [7:0] y);
  wire [7:0] w;
  sub u(.x(f), .q(w));
  always_comb begin
    if (f) y = f; else y = 8'd0;
  end
endmodule
"""


class TestFunctionInCondition:
    """[iter_315 / PLAN P19.1] 函数只在条件里、图上无结果节点也要标。"""

    def test_if_condition(self, tmp_path):
        s = _run("fanin", "top.y", FUNC_IF, tmp_path)
        assert s["precision"] == "unknown"
        assert s["function_call"] is True
        # 条件函数没有结果节点；drivers 只有 b/c
        assert [x["id"] for x in s["drivers"]] == ["top.b", "top.c"]

    def test_if_comparison(self, tmp_path):
        s = _run("fanin", "top.y", FUNC_IF_CMP, tmp_path)
        assert s["precision"] == "unknown"
        assert s["function_call"] is True

    def test_ternary_condition(self, tmp_path):
        s = _run("fanin", "top.y", FUNC_TERNARY, tmp_path)
        assert s["precision"] == "unknown"
        assert s["function_call"] is True

    def test_case_condition(self, tmp_path):
        s = _run("fanin", "top.y", FUNC_CASE, tmp_path)
        assert s["precision"] == "unknown"
        assert s["function_call"] is True

    def test_function_as_clock(self, tmp_path):
        s = _run("fanin", "top.q", FUNC_CLOCK, tmp_path)
        assert s["precision"] == "unknown"
        assert s["function_call"] is True

    def test_same_name_real_signal_not_misreported(self, tmp_path):
        """其它 module 有函数 f；top 的 f 是真实输入信号 → 不误报。"""
        s = _run("fanin", "top.y", FUNC_NAME_COLLISION, tmp_path)
        assert s["function_call"] is False
        assert s["precision"] == "bus"


FUNC_PACKAGE = """
package p;
  function automatic bit f(input [7:0] x); f = x[0]; endfunction
endpackage
module top(input [7:0] a,b,c, output reg [7:0] y);
  import p::*;
  always_comb begin
    if (f(a)) y = b; else y = c;
  end
endmodule
"""


class TestPackageFunctionCondition:
    def test_package_function_in_condition(self, tmp_path):
        s = _run("fanin", "top.y", FUNC_PACKAGE, tmp_path)
        assert s["precision"] == "unknown"
        assert s["function_call"] is True


FUNC_MACRO_ALIAS = """
`define FN f
module top(input [7:0] a,b,c, output reg [7:0] y);
  function automatic bit f(input [7:0] x); f = x[0]; endfunction
  always_comb begin
    if (`FN(a)) y = b; else y = c;
  end
endmodule
"""

FUNC_MACRO_CALL = """
`define CALL(x) f(x)
module top(input [7:0] a,b,c, output reg [7:0] y);
  function automatic bit f(input [7:0] x); f = x[0]; endfunction
  always_comb begin
    if (`CALL(a)) y = b; else y = c;
  end
endmodule
"""

FUNC_MACRO_PASTE = """
`define DECL(name) function automatic bit name(input [7:0] x); name = x[0]; endfunction
module top(input [7:0] a,b,c, output reg [7:0] y);
  `DECL(f)
  always_comb begin
    if (f(a)) y = b; else y = c;
  end
endmodule
"""

FUNC_IFDEF = """
`define USE_F
module top(input [7:0] a,b,c, output reg [7:0] y);
`ifdef USE_F
  function automatic bit f(input [7:0] x); f = x[0]; endfunction
`else
  function automatic bit g(input [7:0] x); g = x[0]; endfunction
`endif
  always_comb begin
    if (f(a)) y = b; else y = c;
  end
endmodule
"""

FUNC_DPI = """
import "DPI-C" function int f(input int x);
module top(input int a,b,c, output reg [7:0] y);
  always_comb begin
    if (f(a)) y = b; else y = c;
  end
endmodule
"""


class TestMacroAndExternalFunctions:
    """[iter_316 / PLAN P20.1] 宏展开/令牌拼接/ifdef/DPI 函数条件。"""

    def test_macro_alias(self, tmp_path):
        s = _run("fanin", "top.y", FUNC_MACRO_ALIAS, tmp_path)
        assert s["function_call"] is True
        assert s["precision"] == "unknown"

    def test_macro_call_wrapper(self, tmp_path):
        s = _run("fanin", "top.y", FUNC_MACRO_CALL, tmp_path)
        assert s["function_call"] is True
        assert s["precision"] == "unknown"

    def test_macro_token_paste_declaration(self, tmp_path):
        s = _run("fanin", "top.y", FUNC_MACRO_PASTE, tmp_path)
        assert s["function_call"] is True
        assert s["precision"] == "unknown"

    def test_ifdef_selected_function(self, tmp_path):
        s = _run("fanin", "top.y", FUNC_IFDEF, tmp_path)
        assert s["function_call"] is True
        assert s["precision"] == "unknown"

    def test_dpi_import_function(self, tmp_path):
        """DPI 函数没有 module/package body；从 compilation unit 收集。"""
        s = _run("fanin", "top.y", FUNC_DPI, tmp_path)
        assert s["function_call"] is True
        assert s["precision"] == "unknown"


FUNC_INTERFACE = """
interface ifc(input [7:0] x);
  function automatic bit f(input [7:0] v); f = v[0]; endfunction
endinterface
module top(ifc i, input [7:0] a,b,c, output reg [7:0] y);
  always_comb begin
    if (i.f(a)) y = b; else y = c;
  end
endmodule
"""


class TestInterfaceFunctionCondition:
    def test_interface_function_in_condition(self, tmp_path):
        s = _run("fanin", "top.y", FUNC_INTERFACE, tmp_path)
        assert s["function_call"] is True
        assert s["precision"] == "unknown"
