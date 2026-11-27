"""P194.6 — scoped static typing and generated result schema."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_generated_result_schema_matches_registry():
    sys.path.insert(0, str(ROOT / "src"))
    from sv_query.cli._registry import JSON_CONTRACT

    generated = json.loads((ROOT / "tools/generated_result_schema.json").read_text())
    assert set(generated["commands"]) == set(JSON_CONTRACT["commands"])
    for name, row in JSON_CONTRACT["commands"].items():
        if "result_fields" in row:
            optional = set(row.get("optional_result_fields", ()))
            required = [f for f in row["result_fields"] if f not in optional]
            assert generated["commands"][name]["required"] == required
            assert generated["commands"][name]["optional"] == sorted(optional)
        else:
            props = generated["commands"][name]["properties"]
            assert props, f"{name} has no generated properties"


def test_mypy_scope_passes():
    proc = subprocess.run(
        [sys.executable, "-m", "mypy"], cwd=ROOT, capture_output=True,
        text=True, timeout=180)
    assert proc.returncode == 0, proc.stdout[-800:] + proc.stderr[-400:]
