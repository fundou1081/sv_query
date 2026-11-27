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
        elif "base_fields" in row:
            base = list(row["base_fields"])
            all_fields = list(base)
            for fields in row.get("modes", {}).values():
                all_fields.extend(f for f in fields if f not in all_fields)
            all_fields.extend(f for f in row.get("optional_fields", ())
                              if f not in all_fields)
            generated_row = generated["commands"][name]
            assert generated_row["required"] == base
            assert generated_row["optional"] == sorted(
                f for f in all_fields if f not in base)
            assert "edge_evidence" in generated_row["properties"]
        else:
            ref = row.get("fields")
            definition = JSON_CONTRACT.get(ref, {}) if isinstance(ref, str) else {}
            expected = sorted(definition) if isinstance(definition, dict) else []
            generated_row = generated["commands"][name]
            assert sorted(generated_row["properties"]) == expected
            assert generated_row["required"] == []
            assert generated_row["optional"] == expected


def test_mypy_scope_passes():
    proc = subprocess.run(
        [sys.executable, "-m", "mypy"], cwd=ROOT, capture_output=True,
        text=True, timeout=180)
    assert proc.returncode == 0, proc.stdout[-800:] + proc.stderr[-400:]
