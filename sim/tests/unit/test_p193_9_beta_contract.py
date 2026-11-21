"""P193.9 — external beta contract page."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DOC = ROOT / "docs/BETA_CONTRACT.md"


def test_beta_contract_covers_stable_no_promise_and_evidence():
    text = DOC.read_text(encoding="utf-8")
    for needle in (
        "Stable surface",
        "No promise",
        "verified", "unknown", "contradicted",
        "Warm in-graph queries",
        "45 canonical",
    ):
        assert needle in text
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "docs/BETA_CONTRACT.md" in readme
