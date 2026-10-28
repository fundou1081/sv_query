"""[iter_309 / PLAN P15] `--bits` 位级端点归一化（paths/dataflow/impact）。

行为约定：
  - 位节点存在 → resolved=signal[bit]，precision=bit
  - 位节点缺失但总线存在 → resolved=总线，precision=bus，coarse_fallback=true
  - --bits 数量与端点不匹配 / 信号已带位索引 → 命令失败（exit 2/1）
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
SLICE = """
module top(input [7:0] a, output [7:0] y);
  assign y[7:4] = a;
endmodule
"""


def _run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(["sv_query", *args], capture_output=True, text=True,
                          timeout=60, cwd=str(PROJECT_ROOT))


def _json(r: subprocess.CompletedProcess) -> dict:
    assert r.returncode == 0, r.stderr[-400:]
    return json.loads(r.stdout)


def _file(tmp_path: Path) -> str:
    p = tmp_path / "t.sv"
    p.write_text(SLICE)
    return str(p)


class TestPathsBits:
    def test_bit_endpoint_path(self, tmp_path):
        d = _json(_run(["paths", "top.a", "top.y", "--bits", "1,5",
                        "--directed", "--file", _file(tmp_path), "--json"]))
        assert d["ok"] is True
        assert d["src_resolved"] == "top.a[1]"
        assert d["dst_resolved"] == "top.y[5]"
        assert d["bits"]["src"]["precision"] == "bit"
        assert d["bits"]["dst"]["precision"] == "bit"
        assert d["found"] is True
        assert d["path"] == ["top.a[1]", "top.y[5]"]

    def test_missing_bit_falls_back_to_bus(self, tmp_path):
        d = _json(_run(["paths", "top.a", "top.y", "--bits", "1,3",
                        "--directed", "--file", _file(tmp_path), "--json"]))
        assert d["src_resolved"] == "top.a[1]"
        assert d["dst_resolved"] == "top.y"
        assert d["bits"]["dst"]["precision"] == "bus"
        assert d["bits"]["coarse_fallback"] is True

    def test_bits_count_mismatch_fails(self, tmp_path):
        r = _run(["paths", "top.a", "top.y", "--bits", "1",
                  "--file", _file(tmp_path), "--json"])
        assert r.returncode != 0
        assert not r.stdout.strip() or json.loads(r.stdout).get("ok") is False

    def test_bits_on_bit_signal_fails(self, tmp_path):
        r = _run(["paths", "top.a[1]", "top.y", "--bits", "1,5",
                  "--file", _file(tmp_path), "--json"])
        assert r.returncode != 0


class TestDataflowBits:
    def test_bit_endpoints_reachable(self, tmp_path):
        d = _json(_run(["dataflow", "analyze", "top.a", "top.y",
                        "--bits", "1,5", "--file", _file(tmp_path), "--json"]))
        r = d["result"]
        assert d["ok"] is True
        assert r["from_resolved"] == "top.a[1]"
        assert r["to_resolved"] == "top.y[5]"
        assert r["bits"]["src"]["precision"] == "bit"
        assert r["is_reachable"] is True
        assert r["paths_count"] >= 1


class TestImpactBits:
    def test_impact_bit_signal(self, tmp_path):
        d = _json(_run(["trace", "impact", "top.a", "--bits", "1",
                        "--file", _file(tmp_path), "--json", "--no-cache"]))
        s = d["result"]["signals"][0]
        assert s["resolved_signal"] == "top.a[1]"
        assert s["precision"] == "bit"
        assert s["coarse_fallback"] is False
        assert s["total_paths"] >= 1

    def test_impact_batch_bits_align(self, tmp_path):
        d = _json(_run(["trace", "impact", "--batch", "top.a,top.y",
                        "--bits", "1,5", "--file", _file(tmp_path), "--json", "--no-cache"]))
        sigs = d["result"]["signals"]
        assert [s["resolved_signal"] for s in sigs] == ["top.a[1]", "top.y[5]"]
        assert all(s["precision"] == "bit" for s in sigs)
