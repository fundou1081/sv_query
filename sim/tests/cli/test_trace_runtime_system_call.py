"""[iter_322 / PLAN P26.2] 运行期系统调用诚实标记（$random 等）。

- 结果/条件里出现 $random/$urandom... -> runtime_system_call=true + precision=unknown
- $clog2/$bits 等常量内建不标
- 节点 id 必须是稳定名字（不能是 SystemCallInfo 对象 repr）
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _run(sig: str, src: str, tmp_path: Path, *extra: str) -> dict:
    p = tmp_path / "t.sv"
    p.write_text(src)
    r = subprocess.run(
        ["sv_query", "trace", "fanin", sig, "--file", str(p), "--json", "--no-cache", *extra],
        capture_output=True, text=True, timeout=60, cwd=str(PROJECT_ROOT),
    )
    assert r.returncode == 0, r.stderr[-300:]
    return json.loads(r.stdout)["result"]["signals"][0]


RANDOM = """
module top(input [7:0] a,b, output [7:0] y, output [7:0] z, output reg [7:0] q);
  assign y = $random;
  assign z = y[3];
  always_comb if ($random) q = a; else q = b;
endmodule
"""

CLOG2 = """
module top(input [7:0] a, output [7:0] y);
  assign y = $clog2(a);
endmodule
"""

URANDOM = """
module top(input [7:0] a, output [7:0] y);
  assign y = $urandom_range(8'd10, 8'd1);
endmodule
"""


class TestRuntimeSystemCall:
    def test_random_expression(self, tmp_path):
        s = _run("top.y", RANDOM, tmp_path)
        assert s["precision"] == "unknown"
        assert s["runtime_system_call"] is True
        ids = [d["id"] for d in s["drivers"]]
        assert "$random" in ids
        assert not any("SystemCallInfo" in i for i in ids)

    def test_random_condition(self, tmp_path):
        s = _run("top.q", RANDOM, tmp_path)
        assert s["precision"] == "unknown"
        assert s["runtime_system_call"] is True

    def test_propagates_to_bit(self, tmp_path):
        s = _run("top.z", RANDOM, tmp_path)
        assert s["precision"] == "unknown"
        assert s["runtime_system_call"] is True

    def test_clog2_not_runtime(self, tmp_path):
        s = _run("top.y", CLOG2, tmp_path)
        assert s["runtime_system_call"] is False

    def test_urandom_range(self, tmp_path):
        s = _run("top.y", URANDOM, tmp_path)
        assert s["runtime_system_call"] is True
        assert s["precision"] == "unknown"
