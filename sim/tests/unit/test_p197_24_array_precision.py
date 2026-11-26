"""P197.24 — array element precision and warm-cache metadata."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _fixture(tmp_path: Path) -> Path:
    sv = tmp_path / "array.sv"
    sv.write_text(
        "module sub(output logic [31:0] o [0:3]);\n"
        "  assign o[0] = 32'h1;\n"
        "endmodule\n"
        "module top(output logic [31:0] mem [0:3]);\n"
        "  sub u1(.o(mem));\n"
        "endmodule\n")
    return sv


def test_array_element_cli_precision_is_not_coarse(tmp_path):
    proc = subprocess.run(
        [sys.executable, "run_cli.py", "drivers", "top.mem[0]",
         "--file", str(_fixture(tmp_path)), "--json", "--no-cache"],
        cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, proc.stderr[-300:]
    row = json.loads(proc.stdout)["result"]["signals"][0]
    assert row["precision"] == "bus"
    assert row["coarse_fallback"] is False
    assert row["count"] >= 1
    rel = subprocess.run(
        [sys.executable, "run_cli.py", "drivers", "mem[0]",
         "--file", str(_fixture(tmp_path)), "--json", "--no-cache"],
        cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert rel.returncode == 0, rel.stderr[-300:]
    rel_row = json.loads(rel.stdout)["result"]["signals"][0]
    assert rel_row["precision"] == "bus"
    assert rel_row["coarse_fallback"] is False


def test_warm_cache_restores_instance_array_metadata(tmp_path, monkeypatch):
    from sv_query.trace.core.cache import ast_cache as ac
    from sv_query.trace.unified_tracer import UnifiedTracer
    cache = ac.ASTCache(cache_dir=str(tmp_path / "cache"))
    monkeypatch.setattr(ac, "_global_cache", cache)
    sv = _fixture(tmp_path)
    first = UnifiedTracer(sources={str(sv): sv.read_text()}, log_level="ERROR")
    first.build_graph(use_cache=True)
    assert first._cache_status == "miss"
    ac._global_cache = ac.ASTCache(cache_dir=str(tmp_path / "cache"))
    second = UnifiedTracer(sources={str(sv): sv.read_text()}, log_level="ERROR")
    graph = second.build_graph(use_cache=True)
    assert second._cache_status == "hit"
    base = graph.get_node("top.mem")
    assert (base.extra or {}).get("is_array") is True
    element = graph.get_node("top.mem[0]")
    assert (element.extra or {}).get("array_element") is True
