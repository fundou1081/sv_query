"""test_query_perf_harness.py — [iter_369 / PLAN P67.1] 性能 harness 结构自检。"""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "tools" / "benchmark"))
import query_perf  # noqa: E402


def test_cases_have_real_queries():
    cases = {c["name"]: c for c in query_perf._cases()}
    assert {"picorv32", "verilog-axi", "serv"} <= set(cases)
    for name in ("picorv32", "verilog-axi", "serv"):
        assert cases[name]["queries"], name
        assert all(q["cmd"] in ("fanin", "fanout") for q in cases[name]["queries"])


def test_missing_source_is_explicitly_skipped():
    row = query_perf._in_process({"name": "missing", "path": None, "queries": []})
    assert row["status"] == "skipped"
    assert "missing" in row["reason"]
