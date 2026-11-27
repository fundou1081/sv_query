"""P197.10 — audit dispositions are reconciled with claims."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_claims_cover_p197_remediation_and_audit_links_them():
    claims = (ROOT / "docs/dev/CLAIMS.md").read_text()
    audit = (ROOT / "docs/validation/CODE_SMELL_AUDIT_2026-11-23.md").read_text()
    for claim in ("C-67", "C-68", "C-69", "C-70", "C-71", "C-72", "C-73"):
        assert claim in claims
    assert "payload declares graph-only capability" not in claims
    assert "P197.10 remediation reconciliation" in audit
    for finding in ("F1", "F6", "F8", "F9", "S1", "S2", "S3"):
        assert f"| {finding} | fixed |" in audit
    assert "| F10 | open" in audit
    assert "| F4 | fixed" in audit and "| F5 | fixed" in audit
    c62 = next(line for line in claims.splitlines() if line.startswith("| C-62 |"))
    assert c62.rstrip().endswith("| `verified` |")
    assert "C-63 |" in claims
    assert "P197.14" in audit and "P197.16" in audit
