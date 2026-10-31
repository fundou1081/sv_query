"""[iter_310 / PLAN P16] 动态索引传播标记必须随图缓存序列化/反序列化保留。"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "src"))

from trace.core.graph.models import SignalGraph  # noqa: E402
from trace.unified_tracer import UnifiedTracer  # noqa: E402

SRC = """
module top(input [7:0] d, input [1:0] i, output [7:0] y);
  logic [7:0] mem [0:3];
  assign mem[1] = d;
  assign y = mem[i];
endmodule
"""


def test_dynamic_flags_survive_roundtrip():
    t = UnifiedTracer(sources={"t.sv": SRC}, log_level="ERROR")
    g = t.build_graph()
    assert g.get_node("top.y").extra.get("dynamic") is True
    g2 = SignalGraph.from_dict(g.to_dict())
    assert g2.get_node("top.y").extra.get("dynamic") is True
    assert "top.y" in g2._dynamic_nodes


def test_function_flags_survive_roundtrip():
    t = UnifiedTracer(sources={"t.sv": """
module top(input [7:0] a, output [7:0] y);
  function automatic [7:0] f(input [7:0] x);
    f = x;
  endfunction
  assign y = f(a);
endmodule"""}, log_level="ERROR")
    g = t.build_graph()
    assert g.get_node("top.f").extra.get("function_call") is True
    assert g.get_node("top.y").extra.get("function_call") is True
    g2 = SignalGraph.from_dict(g.to_dict())
    assert g2.get_node("top.f").extra.get("function_call") is True
    assert "top.f" in g2._function_nodes


def test_static_signal_not_marked():
    t = UnifiedTracer(sources={"t.sv": """
module top(input [7:0] d, output [7:0] y);
  logic [7:0] mem [0:3];
  assign mem[1] = d;
  assign y = mem[1];
endmodule"""}, log_level="ERROR")
    g = t.build_graph()
    assert not (g.get_node("top.y").extra or {}).get("dynamic")
    assert g._dynamic_nodes == set()


def test_runtime_system_flags_survive_roundtrip():
    t = UnifiedTracer(sources={"t.sv": """
module top(output [7:0] y);
  assign y = $random;
endmodule"""}, log_level="ERROR")
    g = t.build_graph()
    assert g.get_node("top.y").extra.get("runtime_system_call") is True
    g2 = SignalGraph.from_dict(g.to_dict())
    assert g2.get_node("top.y").extra.get("runtime_system_call") is True
    assert "top.y" in g2._runtime_system_nodes
