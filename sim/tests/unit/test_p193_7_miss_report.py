"""P193.7 — desensitized miss-report template and guide."""
from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
TEMPLATE = ROOT / ".github/ISSUE_TEMPLATE/miss_report.yml"
GUIDE = ROOT / "docs/MISS_REPORT_GUIDE.md"


def test_miss_template_requires_safe_report_fields():
    data = yaml.safe_load(TEMPLATE.read_text(encoding="utf-8"))
    assert data["name"]
    body = data["body"]
    ids = {item.get("id") for item in body if isinstance(item, dict)}
    assert {"version", "command", "expected", "actual", "fixture"} <= ids
    text = TEMPLATE.read_text(encoding="utf-8")
    assert "Do not paste proprietary RTL" in text
    assert "absolute local paths" in text


def test_guide_has_redaction_and_scan_workflow():
    text = GUIDE.read_text(encoding="utf-8")
    for needle in (
        "structure-preserving fixture",
        "Local scan before sharing",
        "Structural-only report",
        "no proprietary RTL",
        "MIT OR Apache-2.0",
    ):
        assert needle in text
