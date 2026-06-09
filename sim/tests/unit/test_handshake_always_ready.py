"""
TDD: handshake scan must handle always-1 ready signals (TileLink/AXI common pattern).

Pattern: `always_comb a_ready_o = 1'b1;` (always ready)
- This is the simplest TileLink/AXI master that always accepts
- Should be classified as PORT_PASSTHROUGH (always-on passthrough)
"""
import sys, warnings
warnings.filterwarnings('ignore')
sys.path.insert(0, 'src')

from trace.core.handshake_detector import _classify_one_driver
from trace.core.graph.models import DriverInfo


def make_di(cond="", expr="", assign_type="continuous", clock_domain=""):
    from trace.core.graph.models import TraceNode, NodeKind
    node = TraceNode(id="test_signal", name="test_signal", module="test",
                     kind=NodeKind.SIGNAL, width=(1, 0))
    return DriverInfo(
        node=node,
        target_signal="test_signal",
        expression=expr, condition=cond,
        assign_type=assign_type, clock_domain=clock_domain,
        bit_slice="", distance=0, reset_condition="",
    )


def test_always_ready_one_b1():
    """always_comb a_ready_o = 1'b1 → should be classified, not UNKNOWN"""
    di = make_di(cond="", expr="1'b1", assign_type="nonblocking")
    result = _classify_one_driver("a_ready_o", di)
    assert result is not None, "nonblocking with constant expression returned None"
    assert result.handshake_type in ("PORT_PASSTHROUGH", "WIRE_PASSTHROUGH"), \
        f"Expected passthrough, got {result.handshake_type}"
    assert result.channel == "A"


def test_always_ready_blocking():
    """always_comb a_ready_o = 1 (blocking) → should be classified"""
    di = make_di(cond="", expr="1", assign_type="blocking")
    result = _classify_one_driver("a_ready_o", di)
    assert result is not None
    assert result.handshake_type in ("PORT_PASSTHROUGH", "WIRE_PASSTHROUGH")


def test_always_ready_all_ones():
    """always_comb a_ready_o = '1 (all-ones literal) → should be classified"""
    di = make_di(cond="", expr="'1", assign_type="nonblocking")
    result = _classify_one_driver("a_ready_o", di)
    assert result is not None
    assert result.handshake_type in ("PORT_PASSTHROUGH", "WIRE_PASSTHROUGH")


def test_always_ready_d_channel():
    """d_ready_i = 1'b1 (TileLink D channel) → should classify as D"""
    di = make_di(cond="", expr="1'b1", assign_type="nonblocking")
    result = _classify_one_driver("d_ready_i", di)
    assert result is not None
    assert result.channel == "D"


def test_always_ready_wvalid():
    """s_axi_wvalid = 1'b1 → A channel? No, this is W channel"""
    di = make_di(cond="", expr="1'b1", assign_type="nonblocking")
    result = _classify_one_driver("s_axi_wvalid", di)
    assert result is not None
    assert result.channel == "W"


if __name__ == '__main__':
    import pytest
    sys.exit(pytest.main([__file__, '-v']))
