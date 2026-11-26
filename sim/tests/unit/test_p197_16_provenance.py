"""P197.16 — depth, confidence provenance, cache env."""
from __future__ import annotations

from pathlib import Path

from sv_query.trace.core.query.architecture import instance_within_depth


def test_instance_depth_is_relative_to_root():
    assert instance_within_depth("top", None, 1)
    assert instance_within_depth("top.u", None, 1)
    assert not instance_within_depth("top.u.v", None, 1)
    assert instance_within_depth("top.u", "top", 1)
    assert not instance_within_depth("top.u.v", "top", 1)


def test_bit_query_with_parent_bus_driver_is_low_confidence(tmp_path):
    from sv_query.trace.unified_tracer import UnifiedTracer
    sv = tmp_path / "conf.sv"
    sv.write_text(
        "module top(input logic [7:0] a, output logic [7:0] y);\n"
        "  assign y = a;\n"
        "  assign y[3] = 1'b0;\n"
        "endmodule\n")
    tracer = UnifiedTracer(sources={str(sv): sv.read_text()}, log_level="ERROR")
    tracer.build_graph()
    assert tracer.trace_detailed("top.y[3]").confidence == "low"
    assert tracer.trace_detailed("top.y").confidence == "high"


def test_cache_singleton_rebuilds_on_env_change(tmp_path, monkeypatch):
    from sv_query.trace.core.cache import ast_cache as ac
    old = ac._global_cache
    old_env = ac._global_cache_env
    try:
        monkeypatch.setenv("SVQ_CACHE_DIR", str(tmp_path / "a"))
        first = ac.get_cache()
        monkeypatch.setenv("SVQ_CACHE_DIR", str(tmp_path / "b"))
        second = ac.get_cache()
        assert first is not second
        assert second.cache_dir == tmp_path / "b"
    finally:
        ac._global_cache = old
        ac._global_cache_env = old_env


def test_precise_bit_and_literal_are_high_confidence(tmp_path):
    from sv_query.trace.unified_tracer import UnifiedTracer
    sv = tmp_path / "precise.sv"
    sv.write_text(
        "module top(input logic [7:0] a, output logic [7:0] y);\n"
        "  assign y[3] = a[3];\n"
        "  assign y[2] = 1'b0;\n"
        "endmodule\n")
    tracer = UnifiedTracer(sources={str(sv): sv.read_text()}, log_level="ERROR")
    tracer.build_graph()
    assert tracer.trace_detailed("top.y[3]").confidence == "high"
    assert tracer.trace_detailed("top.y[2]").confidence == "high"


def test_manual_cache_stays_pinned(tmp_path, monkeypatch):
    from sv_query.trace.core.cache import ast_cache as ac
    manual = ac.ASTCache(cache_dir=str(tmp_path / "manual"))
    old, old_env = ac._global_cache, ac._global_cache_env
    try:
        ac._global_cache = manual
        monkeypatch.setenv("SVQ_CACHE_DIR", str(tmp_path / "other"))
        assert ac.get_cache() is manual
    finally:
        ac._global_cache, ac._global_cache_env = old, old_env


def test_cli_and_session_depth_agree(tmp_path):
    import json
    import subprocess
    import sys

    from sv_query.graph_session import GraphSession
    sv = tmp_path / "hier.sv"
    sv.write_text(
        "module leaf; endmodule\n"
        "module mid; leaf u_leaf(); endmodule\n"
        "module top; mid u_mid(); endmodule\n")
    proc = subprocess.run(
        [sys.executable, "run_cli.py", "instances", "-f", str(sv),
         "--depth", "1", "--json"],
        cwd=Path(__file__).resolve().parents[3], capture_output=True,
        text=True, timeout=120)
    assert proc.returncode == 0, proc.stderr[-300:]
    cli = {r["full_path"] for r in json.loads(proc.stdout)["instances"]}
    session = {r["full_path"] for r in
               GraphSession(file=str(sv)).instances(depth=1)["instances"]}
    assert cli == session
    assert "top.u_mid" in cli and "top.u_mid.u_leaf" not in cli
