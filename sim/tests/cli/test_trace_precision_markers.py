"""[iter_303 / PLAN P13.2] trace JSON 的粒度标记 + 粗粒度回退标注。

每个结果节点带 `precision: bit|bus|constant`；每个 signal 条目带
`precision: bit|bus|unknown` 与 `coarse_fallback`。

约定：
  - 位查询且结果全是位 → bit
  - 位查询但回落/混入总线 → bus + coarse_fallback=true
  - 位查询空结果 → unknown
  - 总线/切片查询 → bus（查询本身就是总线粒度，不算回退）
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _write(tmp_path: Path, name: str, src: str) -> str:
    p = tmp_path / name
    p.write_text(src)
    return str(p)


def _run(*args) -> dict:
    r = subprocess.run(
        ["sv_query", "trace", *args, "--json", "--no-cache"],
        capture_output=True, text=True, timeout=60, cwd=str(PROJECT_ROOT),
    )
    assert r.returncode == 0, r.stderr[-500:]
    return json.loads(r.stdout)


SLICE = """
module top(input [7:0] a, output [7:0] y);
  assign y[7:4] = a;
endmodule
"""

BUS = """
module sub(input [7:0] a, output [7:0] y); assign y = a; endmodule
module top(input [7:0] a, output [7:0] y); sub u(.a(a), .y(y)); endmodule
"""


def _signal(data: dict, idx: int = 0) -> dict:
    return data["result"]["signals"][idx]


class TestPrecisionMarkers:
    def test_bit_query_precise(self, tmp_path):
        f = _write(tmp_path, "slice.sv", SLICE)
        data = _run("fanin", "top.y[5]", "--file", f)
        sig = _signal(data)
        assert data["ok"] is True
        assert sig["precision"] == "bit"
        assert sig["coarse_fallback"] is False
        assert [(d["id"], d["precision"]) for d in sig["drivers"]] == [
            ("top.a[1]", "bit")]

    def test_bit_query_coarse_fallback(self, tmp_path):
        """纯总线 one 模式：位查询回落到总线 → precision=bus + coarse=true。"""
        f = _write(tmp_path, "bus.sv", BUS)
        data = _run("fanin", "top.y[3]", "--file", f)
        sig = _signal(data)
        assert data["ok"] is True
        assert sig["precision"] == "bus"
        assert sig["coarse_fallback"] is True
        assert [(d["id"], d["precision"]) for d in sig["drivers"]] == [
            ("top.u.y", "bus")]

    def test_bus_query_not_marked_coarse(self, tmp_path):
        f = _write(tmp_path, "bus.sv", BUS)
        data = _run("fanin", "top.y", "--file", f)
        sig = _signal(data)
        assert sig["precision"] == "bus"
        assert sig["coarse_fallback"] is False
        assert sig["drivers"][0]["precision"] == "bus"

    def test_empty_bit_query_unknown(self, tmp_path):
        f = _write(tmp_path, "slice.sv", SLICE)
        data = _run("fanin", "top.y[1]", "--file", f)
        sig = _signal(data)
        assert data["ok"] is True
        assert sig["precision"] == "unknown"
        assert sig["coarse_fallback"] is False
        assert sig["drivers"] == []

    def test_fanout_bit_precise(self, tmp_path):
        f = _write(tmp_path, "slice.sv", SLICE)
        data = _run("fanout", "top.a[1]", "--file", f)
        sig = _signal(data)
        assert sig["precision"] == "bit"
        assert sig["coarse_fallback"] is False
        assert [(d["id"], d["precision"]) for d in sig["loads"]] == [
            ("top.y[5]", "bit")]

    def test_node_metadata_exposed(self, tmp_path):
        """[iter_304 / P13.3] 节点输出带 is_signed/parent/bit_range。"""
        f = _write(tmp_path, "slice.sv", SLICE)
        d = _run("fanin", "top.y[5]", "--file", f)["result"]["signals"][0]["drivers"][0]
        assert d["is_signed"] is False
        assert d["parent"] == "top.a"
        assert d["bit_range"] == "[1]"

    def test_signed_metadata_exposed(self, tmp_path):
        f = _write(tmp_path, "signed.sv", """
module top(input logic signed [7:0] a, output [7:0] y);
  assign y[7:4] = a;
endmodule""")
        d = _run("fanin", "top.y[5]", "--file", f)["result"]["signals"][0]["drivers"][0]
        assert d["is_signed"] is True

    def test_filters_do_not_hide_coarse_fallback(self, tmp_path):
        """过滤掉总线节点后，coarse_fallback 仍应为 true（判定在过滤前）。"""
        f = _write(tmp_path, "bus.sv", BUS)
        data = _run("fanin", "top.y[3]", "--file", f,
                    "--exclude", "top.u.y")
        sig = _signal(data)
        assert sig["count"] == 0
        assert sig["precision"] == "bus"
        assert sig["coarse_fallback"] is True
