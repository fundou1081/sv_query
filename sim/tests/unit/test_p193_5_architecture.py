"""P193.5 — external architecture landing page must not be a stale snapshot."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DOC = ROOT / "docs/ARCHITECTURE.md"


def test_architecture_has_no_stale_banner_or_counts():
    text = DOC.read_text(encoding="utf-8")
    assert "已不代表当前实现" not in text
    assert "2026-08-26 快照" not in text
    assert "本文只作历史设计记录" not in text
    for needle in ("45 canonical", "39 default-visible", "32 standard", "13 direct"):
        assert needle in text
