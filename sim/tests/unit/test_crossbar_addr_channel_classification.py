"""
TDD: classify_signal_channel must recognize axi_crossbar_addr internal AW/AR signals.

Bug: m_wc_valid / m_wc_ready / m_wc_select are axi_crossbar_addr's internal
AW channel indicators (master write command). m_rc_valid / m_rc_ready are
AR channel indicators (master read command). Both were being classified
as UNKNOWN, dropping 7+ signals from the AW/AR scan.
"""
import sys, warnings
warnings.filterwarnings('ignore')
sys.path.insert(0, 'src')

from trace.core.handshake_detector import classify_signal_channel


WC_RC_SIGNALS = [
    ('m_wc_valid', 'AW'),
    ('m_wc_ready', 'AW'),
    ('m_wc_select', 'AW'),
    ('m_wc_decerr', 'AW'),
    ('m_rc_valid', 'AR'),
    ('m_rc_ready', 'AR'),
    ('m_rc_decerr', 'AR'),
    # Scoped
    ('axi_crossbar_addr.m_wc_valid', 'AW'),
    ('axi_crossbar_addr.m_rc_valid', 'AR'),
    # With suffix
    ('m_wc_valid_reg', 'AW'),
    ('m_rc_valid_next', 'AR'),
]


def test_wc_classified_as_aw():
    for sig, expected in WC_RC_SIGNALS:
        actual = classify_signal_channel(sig)
        assert actual == expected, f'{sig}: expected {expected}, got {actual}'


if __name__ == '__main__':
    test_wc_classified_as_aw()
    print('All tests passed')
