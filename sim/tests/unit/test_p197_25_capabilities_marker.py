"""P197.25 — canonical capabilities marker documents array elements."""
from __future__ import annotations

from sv_query.cli._registry import BIT_PRECISION


def test_array_element_exception_is_in_capabilities_marker():
    marker = BIT_PRECISION["markers"]["signal.coarse_fallback"]
    assert "unpacked array" in marker
    assert "element-level" in marker
