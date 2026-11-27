"""P194.5h — P194.5d charter and audit reconciliation exist."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_p1945d_acceptance_charter_is_complete():
    text = (ROOT / "docs/validation/P1945D_ACCEPTANCE_CHARTER_2026-11-27.md").read_text()
    for heading in ("## 2. Dataset", "## 3. Tasks and ground truth",
                    "## 4. Arms and controls", "## 5. Token accounting",
                    "## 6. Metrics and acceptance", "## 7. Artifacts"):
        assert heading in text
    assert "provider's **actual tokenizer" in text
    assert "30 tasks total" in text


def test_audit_reconciliation_marks_p1s_fixed():
    audit = (ROOT / "docs/validation/P1945_AUDIT_2026-11-23.md").read_text()
    assert "P194.5h reconciliation" in audit
    for item in ("P1-1", "P1-2", "P1-3"):
        assert f"| {item} " in audit and "fixed" in audit
