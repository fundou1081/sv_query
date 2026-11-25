"""P197.5 — semantic reset classification and evidence LHS verification."""
from __future__ import annotations

from sv_query.trace.core.coverage_models import SourceLocation, SourceSnippet
from sv_query.trace.core.source_assignment import is_reset_condition
from sv_query.trace.core.trace_evidence import Evidence


def test_assignment_is_not_a_reset_condition():
    assert not is_reset_condition("assign reset_counter = data;")
    assert is_reset_condition("!rst_n && en")
    assert is_reset_condition("rst_n")


def test_evidence_does_not_verify_by_substring():
    snippet = SourceSnippet(
        location=SourceLocation(file="x.sv", line_start=1, line_end=1),
        text="assign metadata = x;")
    ev = Evidence(signal="top.data", enclosing_assign=snippet)
    assert ev.matches_signal_name is False
    assert ev.is_verified is False


def test_evidence_matches_whole_identifier():
    snippet = SourceSnippet(
        location=SourceLocation(file="x.sv", line_start=1, line_end=1),
        text="always_comb data = metadata;")
    ev = Evidence(signal="top.data", enclosing_assign=snippet)
    assert ev.matches_signal_name is True
