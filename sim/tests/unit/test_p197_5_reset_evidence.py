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


def test_cli_evidence_does_not_score_metadata_as_data(tmp_path):
    import json
    import subprocess
    import sys
    from pathlib import Path
    root = Path(__file__).resolve().parents[3]
    sv = tmp_path / "meta.sv"
    sv.write_text(
        "module top(input logic [7:0] data, output logic [7:0] metadata);\n"
        "  assign metadata = data;\n"
        "endmodule\n")
    p = subprocess.run([sys.executable, "run_cli.py", "trace", "evidence",
                        "top.data", "-f", str(sv), "--json", "--no-cache"],
                       cwd=root, capture_output=True, text=True, timeout=120)
    assert p.returncode == 0, p.stderr[-400:]
    ev = json.loads(p.stdout)["result"]["signals"][0]["evidence"]
    assert ev["is_verified"] is False


def test_reset_substring_tokens_are_not_reset():
    assert not is_reset_condition("check_reset_status && valid")
    assert is_reset_condition("soft_reset && valid")
    assert is_reset_condition("rst_n")


def test_source_expr_does_not_match_substring():
    snippet = SourceSnippet(
        location=SourceLocation(file="x.sv", line_start=1, line_end=1),
        text="always_comb y = metadata;")
    ev = Evidence(signal="top.y", source_expr="data", enclosing_assign=snippet)
    assert ev.matches_source_expr is False
    snippet.text = "always_comb y = data;"
    assert ev.matches_source_expr is True


def test_reset_exotic_suffixes_are_recognized():
    for cond in ("rst_n_i", "reset2", "rst_n1", "aresetn_i"):
        assert is_reset_condition(cond), cond


def test_declaration_is_not_a_reset_condition():
    assert not is_reset_condition("logic reset;")


def test_hierarchical_source_expr_requires_full_name():
    snippet = SourceSnippet(
        location=SourceLocation(file="x.sv", line_start=1, line_end=1),
        text="assign other.z = foo.data;")
    ev = Evidence(signal="top.y", source_expr="top.data", enclosing_assign=snippet)
    assert ev.matches_source_expr is False
