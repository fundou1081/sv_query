"""P197.16 — depth, confidence provenance, cache env."""
from __future__ import annotations

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
