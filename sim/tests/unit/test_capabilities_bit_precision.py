"""[iter_304 / PLAN P13.3] capabilities 的位精确性契约（agent 可发现性）。"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from cli._registry import to_json  # noqa: E402


class TestBitPrecisionContract:
    def test_present_and_versioned(self):
        data = to_json()
        bp = data["bit_precision"]
        assert bp["schema_version"] == "1"
        assert set(bp["modes"]) == {"one", "full"}
        assert bp["precise_forms"] and bp["coarse_forms"]

    def test_precise_forms_cover_recent_work(self):
        bp = to_json()["bit_precision"]
        text = " ".join(bp["precise_forms"])
        for token in ("slice", "bitwise", "constants", "signed", "integer",
                      "packed struct"):
            assert token in text, token

    def test_coarse_forms_are_explicit(self):
        bp = to_json()["bit_precision"]
        text = " ".join(bp["coarse_forms"])
        for token in ("comparison", "variable shift", "dynamic part-select",
                      "function/task"):
            assert token in text, token

    def test_markers_documented(self):
        markers = to_json()["bit_precision"]["markers"]
        assert "bit | bus | constant" in markers["node.precision"]
        assert "signal.coarse_fallback" in markers
        assert "true" in markers["signal.coarse_fallback"]

    def test_cli_json_exposes_contract(self):
        r = subprocess.run(["sv_query", "capabilities", "--json"],
                           capture_output=True, text=True, timeout=60,
                           cwd=str(PROJECT_ROOT))
        assert r.returncode == 0
        data = json.loads(r.stdout)
        assert data["bit_precision"]["schema_version"] == "1"

    def test_cli_human_shows_summary(self):
        r = subprocess.run(["sv_query", "capabilities"],
                           capture_output=True, text=True, timeout=60,
                           cwd=str(PROJECT_ROOT))
        assert r.returncode == 0
        assert "[bit precision]" in r.stdout
