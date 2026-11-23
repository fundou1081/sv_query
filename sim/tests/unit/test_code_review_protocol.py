"""Worker-only code-review protocol is documented and wired into release docs."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DOC = ROOT / "docs/dev/CODE_REVIEW_PROTOCOL.md"


def test_protocol_requires_independent_worker_and_rework():
    text = DOC.read_text(encoding="utf-8")
    for required in (
        "separate worker/session", "read-only", "P0/P1", "must rework",
        "re-audit", "not valid", "docs/validation/reviews/",
    ):
        assert required in text, required


def test_protocol_is_linked_from_engineering_entrypoints():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    testing = (ROOT / "TESTING.md").read_text(encoding="utf-8")
    release = (ROOT / "RELEASE.md").read_text(encoding="utf-8")
    assert "CODE_REVIEW_PROTOCOL" in agents
    assert "CODE_REVIEW_PROTOCOL" in testing
    assert "CODE_REVIEW_PROTOCOL" in release


def test_protocol_blocks_open_p0_p1_release():
    text = DOC.read_text(encoding="utf-8")
    assert "no release tag" in text
    assert "all P0/P1 findings are closed" in text
