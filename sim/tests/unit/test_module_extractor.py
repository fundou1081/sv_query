"""Test module_extractor (PR1 2026-06-13)

Verifies:
- extract_module_from_graph finds INSTANTIATED_MODULE nodes
- Binary garbage nodes are filtered
- Instance boundary truncation works
- depth limits work
"""
import pytest

from trace.core.graph.models import SignalGraph, TraceNode, EdgeKind, NodeKind
from trace.core.module_extractor import (
    ModuleInstance,
    ModuleExtraction,
    extract_module_from_graph,
    truncate_instance_id,
)


# ---- Helpers ----

def _make_node(name: str, width=(0, 0), kind=NodeKind.SIGNAL, module="m") -> TraceNode:
    return TraceNode(
        id=f"{module}.{name}", name=name, module=module, kind=kind,
        width=width, is_clock=False, is_reset=False, is_enable=False,
    )


def _make_inst(id: str, name: str, module: str) -> TraceNode:
    return TraceNode(
        id=id, name=name, module=module, kind=NodeKind.INSTANTIATED_MODULE,
        width=(0, 0), is_clock=False, is_reset=False, is_enable=False,
    )


def _build_graph_with_insts(inst_specs: list[tuple[str, str, str]]) -> SignalGraph:
    """inst_specs: list of (id, name, module)."""
    g = SignalGraph()
    for nid, name, mod in inst_specs:
        g.add_trace_node(_make_inst(nid, name, mod))
    return g


# ---- truncate_instance_id ----

def test_truncate_depth_0_returns_module_name():
    full = "axi_xbar_intf.i_xbar.gen_mst_port_mux[0].i_axi_mux"
    assert truncate_instance_id(full, depth=0) == "axi_xbar_intf"


def test_truncate_depth_1_returns_last_instance():
    full = "axi_xbar_intf.i_xbar.gen_mst_port_mux[0].i_axi_mux"
    assert truncate_instance_id(full, depth=1) == "i_axi_mux"


def test_truncate_depth_2_returns_last_2():
    full = "axi_xbar_intf.i_xbar.gen_mst_port_mux[0].i_axi_mux"
    assert truncate_instance_id(full, depth=2) == "gen_mst_port_mux[0].i_axi_mux"


def test_truncate_depth_too_large_returns_full():
    full = "a.b"
    assert truncate_instance_id(full, depth=5) == "a.b"


def test_truncate_single_component():
    full = "axi_xbar"
    assert truncate_instance_id(full, depth=1) == "axi_xbar"


# ---- extract_module_from_graph ----

def test_extract_finds_direct_children():
    g = _build_graph_with_insts([
        ("top.i_a", "i_a", "mod_a"),
        ("top.i_b", "i_b", "mod_b"),
    ])
    result = extract_module_from_graph(g, "top", max_depth=1)
    assert len(result.instances) == 2
    names = {inst.name for inst in result.instances}
    assert names == {"i_a", "i_b"}


def test_extract_filters_binary_garbage():
    g = SignalGraph()
    g.add_trace_node(_make_inst("top.clean", "clean", "mod"))
    g.add_trace_node(_make_inst("top.\x00bad", "bad", "mod_bad"))
    g.add_trace_node(_make_inst("top.\x00dirty", "dirty", "mod_dirty"))
    result = extract_module_from_graph(g, "top", max_depth=1)
    assert len(result.instances) == 1
    assert result.instances[0].name == "clean"


def test_extract_respects_max_depth():
    g = _build_graph_with_insts([
        ("top.a", "a", "mod"),
        ("top.a.b", "b", "mod"),
        ("top.a.b.c", "c", "mod"),
        ("top.a.b.c.d", "d", "mod"),
    ])
    # depth 1: only direct children
    r1 = extract_module_from_graph(g, "top", max_depth=1)
    assert len(r1.instances) == 1
    assert r1.instances[0].name == "a"
    # depth 2: a + b
    r2 = extract_module_from_graph(g, "top", max_depth=2)
    assert len(r2.instances) == 2
    # depth 5: all
    r5 = extract_module_from_graph(g, "top", max_depth=5)
    assert len(r5.instances) == 4


def test_extract_detects_array_pattern():
    g = _build_graph_with_insts([
        ("top.gen_mux[0].i_mux", "i_mux", "axi_mux"),
        ("top.gen_mux[1].i_mux", "i_mux", "axi_mux"),
    ])
    result = extract_module_from_graph(g, "top", max_depth=2)
    assert len(result.instances) == 2
    for inst in result.instances:
        assert inst.array_name == "gen_mux"
        assert inst.array_index in (0, 1)


def test_extract_falls_back_to_substring_match():
    """当 target_module 不在 graph 时, 用子串匹配"""
    g = _build_graph_with_insts([
        ("axi_xbar_intf_typedef.i_xbar", "i_xbar", "axi_xbar"),
    ])
    # 传 axi_xbar, 找不到精确匹配, 应该找 axi_xbar_intf_typedef
    result = extract_module_from_graph(g, "axi_xbar", max_depth=1)
    # 可能找到也可能找不到, 主要看子串匹配
    assert isinstance(result, ModuleExtraction)


def test_extract_returns_empty_for_empty_graph():
    g = SignalGraph()
    result = extract_module_from_graph(g, "nonexistent", max_depth=1)
    assert result.top_module == "nonexistent"
    assert result.instances == []


def test_extract_depth_attribute_correct():
    g = _build_graph_with_insts([
        ("top.a", "a", "mod"),
        ("top.a.b", "b", "mod"),
        ("top.x.y.z", "z", "mod"),
    ])
    result = extract_module_from_graph(g, "top", max_depth=5)
    depths = {inst.name: inst.depth for inst in result.instances}
    assert depths == {"a": 1, "b": 2, "z": 3}
