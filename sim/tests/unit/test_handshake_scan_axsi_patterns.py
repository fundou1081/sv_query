"""
TDD: handshake scan must recognize standard AXI signal patterns.

Bug: READY_VALID_PATTERNS only includes 'aw_valid' (with underscore) and
'_valid' (with leading underscore), so it doesn't match signals like
's_axi_awvalid', 'm_axi_wready' (no underscore between channel and valid/ready).
"""
import sys, warnings
warnings.filterwarnings('ignore')
sys.path.insert(0, 'src')

from cli.commands.handshake import _is_ready_or_valid, _strip_suffix


# Standard AXI signal patterns that MUST be recognized
AXI_VALID_READY = [
    's_axi_awvalid', 's_axi_awready',
    'm_axi_awvalid', 'm_axi_awready',
    's_axi_wvalid',  's_axi_wready',
    's_axi_bvalid',  's_axi_bready',
    's_axi_arvalid', 's_axi_arready',
    's_axi_rvalid',  's_axi_rready',
    'm_axi_bvalid',  'm_axi_bready',
    'm_axi_arvalid', 'm_axi_arready',
    'm_axi_rvalid',  'm_axi_rready',
    # With _reg/_next suffix
    's_axi_awvalid_reg', 's_axi_awready_reg',
    'm_axi_awvalid_next', 's_axi_awready_next',
]

def test_standard_axi_signals_recognized():
    """Bug: _is_ready_or_valid returns False for s_axi_awvalid, s_axi_awready, etc."""
    for sig in AXI_VALID_READY:
        assert _is_ready_or_valid(sig), f'NOT recognized: {sig}'


def test_axi_valid_ready_pair_strip():
    """Stripped prefixes must match between valid/ready for pairing."""
    valid = _strip_suffix('axi_adapter.s_axi_awvalid_reg')
    ready = _strip_suffix('axi_adapter.s_axi_awready_reg')
    assert valid == ready, f'pair mismatch: {valid!r} != {ready!r}'


def test_full_axsi_channel_pair():
    """All AXI channels produce matching valid/ready base names."""
    for ch in ['aw', 'w', 'b', 'ar', 'r']:
        v = _strip_suffix(f's_axi_{ch}valid')
        r = _strip_suffix(f's_axi_{ch}ready')
        assert v == r, f'channel {ch}: {v!r} != {r!r}'


if __name__ == '__main__':
    test_standard_axi_signals_recognized()
    test_axi_valid_ready_pair_strip()
    test_full_axsi_channel_pair()
    print('All tests passed')
