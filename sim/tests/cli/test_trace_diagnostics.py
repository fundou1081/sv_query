"""[iter_321 / PLAN P26.1] fanin/fanout 遍历完整性元数据。

- truncated_by_depth: depth 边界节点仍有未展开边
- cycles_detected: reachable 子图在遍历方向上有环（capped 三态）
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from cli.core.semantic.trace_common import detect_cycles  # noqa: E402


def _run(cmd: str, sig: str, src: str, tmp_path: Path, *extra: str) -> dict:
    p = tmp_path / "t.sv"
    p.write_text(src)
    r = subprocess.run(
        ["sv_query", "trace", cmd, sig, "--file", str(p), "--json", "--no-cache", *extra],
        capture_output=True, text=True, timeout=60, cwd=str(PROJECT_ROOT),
    )
    assert r.returncode == 0, r.stderr[-300:]
    return json.loads(r.stdout)["result"]["signals"][0]


CYCLE = """
module top(input [7:0] a, output [7:0] y, output [7:0] z);
  wire [7:0] t;
  assign t = y;
  assign y = a ^ t;
  assign z = t;
endmodule
"""

CHAIN = """
module top(input [7:0] a, output [7:0] y);
  wire [7:0] t;
  assign t = a;
  assign y = t;
endmodule
"""

PLAIN = """
module top(input [7:0] a, output [7:0] y);
  assign y = a;
endmodule
"""


class TestTraversalDiagnostics:
    def test_cycle_detected(self, tmp_path):
        s = _run("fanin", "top.y", CYCLE, tmp_path)
        assert s["cycles_detected"] is True
        assert s["truncated_by_depth"] is False

    def test_acyclic(self, tmp_path):
        s = _run("fanin", "top.y", PLAIN, tmp_path)
        assert s["cycles_detected"] is False
        assert s["truncated_by_depth"] is False

    def test_depth_truncation(self, tmp_path):
        s1 = _run("fanin", "top.y", CHAIN, tmp_path, "--depth", "1")
        assert s1["truncated_by_depth"] is True
        s2 = _run("fanin", "top.y", CHAIN, tmp_path, "--depth", "2")
        assert s2["truncated_by_depth"] is False

    def test_fanout_fields(self, tmp_path):
        s = _run("fanout", "top.t", CHAIN, tmp_path)
        assert "truncated_by_depth" in s
        assert s["cycles_detected"] is False

    def test_cycle_cap_returns_none(self):
        """capped 三态：预算不足返回 None，不静默当 False。"""
        from trace.unified_tracer import UnifiedTracer
        t = UnifiedTracer(sources={"t.sv": CHAIN}, log_level="ERROR")
        g = t.build_graph()
        assert detect_cycles(g, "top.y", reverse=True, max_nodes=1) is None
