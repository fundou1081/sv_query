"""
TDD: OR-based handshake conditions should be classified as COMPLEX_ARB.

Bug: Case 3 (STANDARD_AXI) was checked before COMPLEX_ARB,
so `if ((v1 && r1) || (v2 && r2))` was mis-classified as STANDARD_AXI.
This represents multi-source arbitration (e.g. multi-master crossbar).
"""
import sys, warnings
warnings.filterwarnings('ignore')
sys.path.insert(0, 'src')

from trace.core.handshake_detector import _classify_one_driver
from trace.core.graph.models import DriverInfo, TraceNode, NodeKind


def make_di(cond="", expr="", assign_type="always_comb", clock_domain="clk"):
    node = TraceNode(id="test_signal", name="test_signal", module="m",
                     kind=NodeKind.SIGNAL, width=(1, 0))
    return DriverInfo(
        node=node,
        target_signal="m.awready",
        expression=expr, condition=cond,
        assign_type=assign_type, clock_domain=clock_domain,
        bit_slice="", distance=0, reset_condition="",
    )


def test_multi_master_or_arbitration():
    """if (mst_a_valid && mst_a_ready) || (mst_b_valid && mst_b_ready) → COMPLEX_ARB"""
    di = make_di(cond='(mst_a_req_o.aw_valid && mst_a_resp_i.aw_ready) || '
                     '(mst_b_req_o.aw_valid && mst_b_resp_i.aw_ready)')
    result = _classify_one_driver("m.awready", di)
    assert result is not None
    assert result.handshake_type == "COMPLEX_ARB", \
        f"Expected COMPLEX_ARB, got {result.handshake_type}"


def test_standard_and_still_axi():
    """Regular AND (no OR) → STANDARD_AXI (regression test)"""
    di = make_di(cond='mst_resp.w_ready && mst_req.w_valid')
    result = _classify_one_driver("m.w_done", di)
    assert result is not None
    assert result.handshake_type == "STANDARD_AXI"


def test_tilelink_d_or_ack():
    """TL-UL: a_valid_i && a_ready_o → a_ack (not OR-related)
    Note: this is a STANDARD AXI-style handshake, not arbitration"""
    di = make_di(cond='a_valid_i && a_ready_o')
    result = _classify_one_driver("m.a_ack", di)
    assert result is not None
    assert result.handshake_type == "STANDARD_AXI"
    assert result.channel == "A"


def test_or_no_valid_no_ready():
    """OR with neither valid nor ready → CONDITIONAL_CTRL (not arbitration)"""
    di = make_di(cond='state == IDLE || state == READY')
    result = _classify_one_driver("m.signal", di)
    assert result is not None
    # No valid/ready pattern → falls to CONDITIONAL_CTRL
    assert result.handshake_type == "CONDITIONAL_CTRL"


if __name__ == '__main__':
    import pytest
    sys.exit(pytest.main([__file__, '-v']))
