"""P193.8 — product runtime has no network/telemetry imports."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))

import check_no_telemetry as tool  # noqa: E402


def test_src_has_no_network_telemetry():
    assert tool.scan(ROOT) == []


def test_gate_detects_network_and_documents_local_only(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "bad.py").write_text("import requests\n# posthog\n")
    assert tool.scan(tmp_path)
    doc = (ROOT / "docs/PRIVACY.md").read_text(encoding="utf-8")
    assert "No telemetry, no RTL upload" in doc
    assert "python3 tools/check_no_telemetry.py" in doc
