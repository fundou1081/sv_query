"""Test _classify_node and dataflow_viz handle non-2-tuple widths.

[Bug-fix 2026-06-13] 实际跑 OpenTitan 时发现:
  sram2tlul.tl_o → width = (1, 0, 0)  # 3-tuple!
原因: pyslang 在某些 elaboration 失败场景下, width 返回多余的尾巴
防御: 只取前 2 个值
"""
import pytest


def test_classify_node_handles_2tuple_width():
    """正常 2-tuple 不受影响"""
    from trace.core.graph.analyzer.signal_classifier import _classify_node, SignalClass
    from trace.core.graph.models import TraceNode, NodeKind
    
    node = TraceNode(
        id="test", name="data", module="m", kind=NodeKind.SIGNAL,
        width=(7, 0),  # 8-bit
    )
    sc, conf = _classify_node(node, "test")
    assert sc == SignalClass.DATA


def test_classify_node_handles_3tuple_width():
    """[Bug-fix] 3-tuple 不应崩"""
    from trace.core.graph.analyzer.signal_classifier import _classify_node, SignalClass
    from trace.core.graph.models import TraceNode, NodeKind
    
    node = TraceNode(
        id="test", name="tl_o", module="sram2tlul", kind=NodeKind.SIGNAL,
        width=(1, 0, 0),  # ← 3-tuple, 实际 OpenTitan 跑出的
    )
    # 不应该 raise
    sc, conf = _classify_node(node, "test")
    assert sc in (SignalClass.DATA, SignalClass.CONTROL, SignalClass.UNKNOWN)


def test_classify_node_handles_empty_width():
    """空 tuple 也不应崩"""
    from trace.core.graph.analyzer.signal_classifier import _classify_node, SignalClass
    from trace.core.graph.models import TraceNode, NodeKind
    
    node = TraceNode(
        id="test", name="x", module="m", kind=NodeKind.SIGNAL,
        width=(),
    )
    sc, conf = _classify_node(node, "test")
    assert sc in (SignalClass.DATA, SignalClass.CONTROL, SignalClass.UNKNOWN, SignalClass.CLOCK, SignalClass.RESET)


def test_classify_node_handles_non_tuple_width():
    """非 tuple 也不应崩"""
    from trace.core.graph.analyzer.signal_classifier import _classify_node, SignalClass
    from trace.core.graph.models import TraceNode, NodeKind
    
    node = TraceNode(
        id="test", name="x", module="m", kind=NodeKind.SIGNAL,
        width=None,
    )
    # 不应该 raise
    sc, conf = _classify_node(node, "test")
    assert sc in (SignalClass.DATA, SignalClass.CONTROL, SignalClass.UNKNOWN, SignalClass.CLOCK, SignalClass.RESET)
