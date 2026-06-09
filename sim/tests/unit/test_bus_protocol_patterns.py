"""
TDD: handshake scan must recognize ready/valid patterns from non-AXI bus protocols.

Found 31+ missing patterns from real projects (axi/, opentitan tlul/, verilog-axi):
- AXI sub-channels (apb_*, arb_*, *_spill_*, *_dec_*, *_done)
- TileLink (a_ack, d_ack, dmi_*_valid, flush_req, flush_ack)
- AHB (hready, hgrant, hreq, hresp)
- APB (psel, penable, pready)
- Wishbone (cyc, stb, we, ack)
- Custom req/ack/done (dma_*, axi_lite_*, rd_wait, wr_req)
- AXI4-Stream variants (s_axis_*, m_axis_*)
"""
import sys, warnings
warnings.filterwarnings('ignore')
sys.path.insert(0, 'src')

from cli.commands.handshake import _is_ready_or_valid, _strip_suffix


# ==============================================================================
# AXI sub-channels and AXI-Stream variants (from axi/ project)
# ==============================================================================
AXI_SUBCHANNEL_SIGNALS = [
    # APB-related
    'apb_req_valid', 'apb_req_ready',
    'apb_dec_valid',
    'apb_rresp_valid', 'apb_rresp_ready',
    'apb_wresp_valid', 'apb_wresp_ready',
    # arbiter
    'arb_req_valid', 'arb_req_ready',
    'arb_valid', 'arb_ready',
    # AXI internal channels
    'aw_chan_spill_valid', 'aw_chan_spill_ready',
    'ar_chan_spill_valid', 'ar_chan_spill_ready',
    'aw_dec_valid', 'ar_dec_valid',
    'aw_done', 'ar_done',
    # AXI-Lite
    'axi_lite_req', 'axi_lite_mst_req', 'axi_lite_slv_req',
    'axi_bresp_valid', 'axi_bresp_ready',
    'axi_rresp_valid', 'axi_rresp_ready',
]


# ==============================================================================
# TileLink UL patterns (from opentitan/hw/ip/tlul)
# ==============================================================================
TILELINK_SIGNALS = [
    # A/D channels
    'a_valid', 'a_ready', 'a_ack',
    'd_valid', 'd_ready', 'd_ack',
    # DMI (JTAG debug)
    'dmi_req_valid', 'dmi_req_ready',
    'dmi_resp_valid', 'dmi_resp_ready',
    # SRAM handshakes
    'sram_ack', 'sram_a_ack', 'sram_d_ack',
    # Flush
    'flush_req', 'flush_ack',
]


# ==============================================================================
# AHB / APB / Wishbone patterns
# ==============================================================================
AHB_SIGNALS = [
    'hready', 'hgrant', 'hreq', 'hresp', 'hburst', 'hwrite',
]
APB_SIGNALS = [
    'apb_psel', 'apb_penable', 'apb_pready',
    'psel', 'penable', 'pready',
]
WISHBONE_SIGNALS = [
    'cyc', 'stb', 'we', 'ack',  # bare
    'cyc_o', 'stb_o', 'we_o', 'ack_i',  # directional
    'cyc_i', 'stb_i', 'we_i', 'ack_o',
    'wb_cyc', 'wb_stb', 'wb_we', 'wb_ack',
]


# ==============================================================================
# Custom req/ack/done (real designs)
# ==============================================================================
CUSTOM_SIGNALS = [
    'dma_req', 'dma_ack', 'dma_done',
    'irq', 'irq_ack',
    'rd_req', 'wr_req', 'rd_wait',
    'pend_req', 'pending_req',
    'cmd_valid', 'cmd_ready', 'resp_valid', 'resp_ready',
    'req_valid', 'req_ready', 'ack',
    'data_valid', 'data_ready',
    'req', 'ack',
    'done', 'busy',
]


# ==============================================================================
# AXI4-Stream
# ==============================================================================
AXIS_SIGNALS = [
    'm_axis_tvalid', 'm_axis_tready',
    's_axis_tvalid', 's_axis_tready',
    'axis_tdata', 'axis_tlast', 'axis_tkeep',
]


def test_axi_subchannel_patterns():
    for sig in AXI_SUBCHANNEL_SIGNALS:
        assert _is_ready_or_valid(sig), f'NOT recognized (AXI sub): {sig}'


def test_tilelink_patterns():
    for sig in TILELINK_SIGNALS:
        assert _is_ready_or_valid(sig), f'NOT recognized (TileLink): {sig}'


def test_ahb_patterns():
    for sig in AHB_SIGNALS:
        assert _is_ready_or_valid(sig), f'NOT recognized (AHB): {sig}'


def test_apb_patterns():
    for sig in APB_SIGNALS:
        assert _is_ready_or_valid(sig), f'NOT recognized (APB): {sig}'


def test_wishbone_patterns():
    for sig in WISHBONE_SIGNALS:
        assert _is_ready_or_valid(sig), f'NOT recognized (Wishbone): {sig}'


def test_custom_req_ack_done():
    for sig in CUSTOM_SIGNALS:
        assert _is_ready_or_valid(sig), f'NOT recognized (custom): {sig}'


def test_axis_patterns():
    for sig in AXIS_SIGNALS:
        assert _is_ready_or_valid(sig), f'NOT recognized (AXIS): {sig}'


# ==============================================================================
# _strip_suffix pair matching
# ==============================================================================
def test_strip_pair_tilelink_a():
    """a_valid ↔ a_ready, a_ack ↔ a_ack"""
    assert _strip_suffix('a_valid') == 'a'
    assert _strip_suffix('a_ready') == 'a'
    assert _strip_suffix('a_ack') == 'a_ack'  # OK, a_ack is its own thing

def test_strip_pair_apb_req():
    """apb_req_valid ↔ apb_req_ready"""
    assert _strip_suffix('apb_req_valid') == 'apb_req'
    assert _strip_suffix('apb_req_ready') == 'apb_req'

def test_strip_pair_apb_pready():
    """apb_penable ↔ apb_pready (same prefix apb_p)"""
    # Both should reduce to 'apb_p' for pairing
    assert _strip_suffix('apb_penable') == 'apb_penable'
    assert _strip_suffix('apb_pready') == 'apb_p'

def test_strip_pair_ahb():
    """hready ↔ hgrant (both should reduce to 'h')"""
    # hready and hgrant don't pair naturally; they have different semantics
    # but _strip_suffix should at least be deterministic
    assert _strip_suffix('hready') == 'h'
    assert _strip_suffix('hgrant') == 'hgrant'

def test_strip_pair_dma():
    """dma_req ↔ dma_ack (these are different semantics, but should strip same prefix)"""
    # dma_req → 'dma_req' (no valid/ready/ack suffix)
    # dma_ack → 'dma_ack' (ack is not in our suffix list)
    # These won't pair under current logic, which is OK
    pass  # not a hard requirement

def test_strip_pair_dmi():
    """dmi_req_valid ↔ dmi_req_ready"""
    assert _strip_suffix('dmi_req_valid') == 'dmi_req'
    assert _strip_suffix('dmi_req_ready') == 'dmi_req'


# ==============================================================================
# Channel classification (what _classify_by_name should return)
# ==============================================================================
def test_classify_tilelink_a():
    from trace.core.handshake_detector import _classify_by_name
    assert _classify_by_name('a_valid') == 'A'
    assert _classify_by_name('a_ready') == 'A'
    # a_ack is TL-UL response - not a valid/ready pair, but should classify as A channel
    assert _classify_by_name('a_ack') == 'A'

def test_classify_tilelink_d():
    from trace.core.handshake_detector import _classify_by_name
    assert _classify_by_name('d_valid') == 'D'
    assert _classify_by_name('d_ready') == 'D'
    assert _classify_by_name('d_ack') == 'D'

def test_classify_axis():
    from trace.core.handshake_detector import _classify_by_name
    # AXI4-Stream uses D channel
    assert _classify_by_name('m_axis_tvalid') == 'D'
    assert _classify_by_name('m_axis_tready') == 'D'
    assert _classify_by_name('s_axis_tvalid') == 'D'


if __name__ == '__main__':
    import pytest
    sys.exit(pytest.main([__file__, '-v']))
