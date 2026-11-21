"""P193.6 — external English user docs exist and cover the essentials."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
USER = ROOT / "docs/USER_GUIDE_EN.md"
LIMITS = ROOT / "docs/KNOWN_LIMITATIONS_EN.md"


def test_english_docs_exist_and_cover_install_query_evidence():
    user = USER.read_text(encoding="utf-8")
    assert "pip install sv_query" in user
    assert "sv_query drivers" in user
    assert "verified / contradicted / unknown" in user
    limits = LIMITS.read_text(encoding="utf-8")
    assert "bit-granular" in limits or "bus-granular" in limits
    assert "--from-snapshot" in limits
    assert "uncalibrated" in limits


def test_readme_links_english_docs():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "docs/USER_GUIDE_EN.md" in readme
    assert "docs/KNOWN_LIMITATIONS_EN.md" in readme
