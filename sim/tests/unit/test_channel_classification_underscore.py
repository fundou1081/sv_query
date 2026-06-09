"""
TDD: channel classification must handle both underscore and non-underscore AXI variants.

Bug: _classify_by_name uses substring 'awvalid' which matches 'awvalid' but not 'aw_valid'.
Need to handle both styles (AXI spec uses no underscore, real projects often use underscore).
"""
import sys, warnings
warnings.filterwarnings('ignore')
sys.path.insert(0, 'src')

from trace.core.handshake_detector import _classify_by_name


def test_aw_no_underscore():
    assert _classify_by_name("awvalid") == "AW"
    assert _classify_by_name("awready") == "AW"


def test_aw_with_underscore():
    """axi_pkg style: aw_valid, aw_ready"""
    assert _classify_by_name("aw_valid") == "AW"
    assert _classify_by_name("aw_ready") == "AW"


def test_w_b_ar_r_variants():
    """All AXI channels must handle both styles"""
    # No underscore
    assert _classify_by_name("wvalid") == "W"
    assert _classify_by_name("wready") == "W"
    assert _classify_by_name("bvalid") == "B"
    assert _classify_by_name("bready") == "B"
    assert _classify_by_name("arvalid") == "AR"
    assert _classify_by_name("arready") == "AR"
    assert _classify_by_name("rvalid") == "R"
    assert _classify_by_name("rready") == "R"

    # With underscore
    assert _classify_by_name("w_valid") == "W"
    assert _classify_by_name("w_ready") == "W"
    assert _classify_by_name("b_valid") == "B"
    assert _classify_by_name("b_ready") == "B"
    assert _classify_by_name("ar_valid") == "AR"
    assert _classify_by_name("ar_ready") == "AR"
    assert _classify_by_name("r_valid") == "R"
    assert _classify_by_name("r_ready") == "R"


def test_with_module_prefix():
    assert _classify_by_name("axi_adapter.awvalid") == "AW"
    assert _classify_by_name("axi_adapter.aw_valid") == "AW"
    assert _classify_by_name("axi_adapter.s_axi_awvalid") == "AW"
    assert _classify_by_name("axi_adapter.s_axi_aw_valid") == "AW"


def test_addr_signals():
    """Address/data signals (e.g. awaddr) should also classify"""
    assert _classify_by_name("awaddr") == "AW"
    assert _classify_by_name("aw_addr") == "AW"
    assert _classify_by_name("wdata") == "W"
    assert _classify_by_name("w_data") == "W"
    assert _classify_by_name("bresp") == "B"
    assert _classify_by_name("b_resp") == "B"


if __name__ == '__main__':
    import pytest
    sys.exit(pytest.main([__file__, '-v']))
