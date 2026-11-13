"""[iter_357 / PLAN P56] generate if/case 嵌套在 generate-for 中。"""
from __future__ import annotations

from pathlib import Path

from sv_query.trace.unified_tracer import UnifiedTracer

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "generate_nested_if_case.sv"


def _build(target: str):
    tr = UnifiedTracer(sources={"t.sv": FIXTURE.read_text()}, log_level="ERROR")
    return tr.build_graph(use_cache=False, target_module=target)


def test_nested_if_inside_for_widths():
    g = _build("top_nested_if")
    expected = {
        "top_nested_if.blk[0].even.u.i": (1, 0),
        "top_nested_if.blk[1].odd.u.i": (4, 0),
        "top_nested_if.blk[2].even.u.i": (3, 0),
        "top_nested_if.blk[3].odd.u.i": (6, 0),
    }
    for nid, width in expected.items():
        assert g.get_node(nid).width == width, nid
        assert g.get_node(nid.replace(".i", ".r")).width == width, nid
    # 每个 iteration 只保留 active 分支
    assert "top_nested_if.blk[0].odd.u.i" not in g.nodes()
    assert "top_nested_if.blk[1].even.u.i" not in g.nodes()


def test_nested_case_inside_for_widths():
    g = _build("top_nested_case")
    expected = {
        "top_nested_case.blk[0].c0.u.i": (1, 0),
        "top_nested_case.blk[1].c1.u.i": (3, 0),
        "top_nested_case.blk[2].cd.u.i": (7, 0),
    }
    for nid, width in expected.items():
        assert g.get_node(nid).width == width, nid
        assert g.get_node(nid.replace(".i", ".r")).width == width, nid
    assert "top_nested_case.blk[0].c1.u.i" not in g.nodes()
    assert "top_nested_case.blk[1].cd.u.i" not in g.nodes()
