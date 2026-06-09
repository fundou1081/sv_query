"""
TDD: handshake detector must catch FIFO backpressure in continuous assign.

Bug: Case 0 (continuous passthrough) catches all continuous assigns with expr,
even when expr contains FIFO backpressure pattern (!fifo_full, !fifo_empty).
The FIFO BP detection (Case 2) comes after and never runs.

Pattern: `assign ready = !fifo_full || (count < THRESHOLD);`
Should be: COMBINATIONAL_BP (FIFO-based backpressure)
Was: WIRE_PASSTHROUGH (just a wire connection)
"""
import sys, warnings
warnings.filterwarnings('ignore')
sys.path.insert(0, 'src')

from trace.core.handshake_detector import _classify_one_driver
from trace.core.graph.models import DriverInfo, TraceNode, NodeKind


def make_di(expr="", cond="", assign_type="continuous", clock_domain=""):
    node = TraceNode(id="test_signal", name="test_signal", module="m",
                     kind=NodeKind.SIGNAL, width=(1, 0))
    return DriverInfo(
        node=node,
        target_signal="m.awready",
        expression=expr, condition=cond,
        assign_type=assign_type, clock_domain=clock_domain,
        bit_slice="", distance=0, reset_condition="",
    )


def test_continuous_assign_fifo_full():
    """`assign ready = !fifo_full` (continuous) → COMBINATIONAL_BP"""
    di = make_di(expr="!fifo_full", assign_type="continuous")
    result = _classify_one_driver("m.awready", di)
    assert result is not None
    assert result.handshake_type == "COMBINATIONAL_BP", \
        f"Expected COMBINATIONAL_BP, got {result.handshake_type}"


def test_continuous_assign_fifo_full_with_threshold():
    """`assign ready = !fifo_full || (count < 8)` → COMBINATIONAL_BP"""
    di = make_di(expr="!fifo_full || (count < 8)", assign_type="continuous")
    result = _classify_one_driver("m.awready", di)
    assert result is not None
    assert result.handshake_type == "COMBINATIONAL_BP", \
        f"Expected COMBINATIONAL_BP, got {result.handshake_type}"


def test_continuous_assign_fifo_empty():
    """`assign ready = !fifo_empty` (continuous) → COMBINATIONAL_BP"""
    di = make_di(expr="!fifo_empty", assign_type="continuous")
    result = _classify_one_driver("m.rready", di)
    assert result is not None
    assert result.handshake_type == "COMBINATIONAL_BP"


def test_continuous_assign_pure_wire_still_passthrough():
    """`assign ready = sig` (no FIFO pattern) → WIRE_PASSTHROUGH"""
    di = make_di(expr="other_signal", assign_type="continuous")
    result = _classify_one_driver("m.awready", di)
    assert result is not None
    assert result.handshake_type == "WIRE_PASSTHROUGH", \
        f"Expected WIRE_PASSTHROUGH, got {result.handshake_type}"


if __name__ == '__main__':
    import pytest
    sys.exit(pytest.main([__file__, '-v']))
