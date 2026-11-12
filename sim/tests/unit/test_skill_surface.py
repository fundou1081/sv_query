"""P158.12.7: skill docs must describe the real CLI surface, not retired commands."""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SKILL = ROOT / "skills/sv-query/SKILL.md"
COMMANDS = ROOT / "skills/sv-query/references/commands.md"
SCHEMA = ROOT / "tools/llm_schema.json"


def _text(path):
    return path.read_text(encoding="utf-8")


def test_skill_counts_match_capability_surface():
    caps = json.loads(__import__("subprocess").run(
        ["python3", "run_cli.py", "capabilities", "--include-exp", "--json"],
        cwd=ROOT, capture_output=True, text=True, check=True).stdout)
    assert caps["counts"]["by_layer"]["core"] == 39
    assert caps["counts"]["by_layer"]["exp"] == 6
    for text in (_text(SKILL), _text(COMMANDS)):
        assert "40 个 core" not in text
        assert "40 core" not in text
        assert "5 个 exp" not in text
        assert "5 exp" not in text


def test_retired_commands_not_advertised_as_examples():
    # Historical "retired" notes are allowed; direct example invocations are not.
    text = _text(SKILL) + "\n" + _text(COMMANDS)
    forbidden = [
        r"run_cli\.py\s+cdc\s+",
        r"run_cli\.py\s+risk\s+",
        r"run_cli\.py\s+sva\s+",
        r"run_cli\.py\s+verify\s+gap",
    ]
    for pat in forbidden:
        assert not re.search(pat, text), pat


def test_skill_and_schema_declare_current_version():
    schema = json.loads(_text(SCHEMA))
    assert schema["version"].startswith("1.")
    assert "40 个 core" not in _text(SKILL)
    # impact/audit are exp in the current surface
    assert "trace impact" in _text(COMMANDS)
    assert "audit" in _text(COMMANDS)


def test_skill_helper_evidence_mode_works():
    proc = __import__("subprocess").run(
        ["python3", "skills/sv-query/scripts/sv_analyze.py",
         "sim/test_simple.sv", "top.data", "--mode", "evidence"],
        cwd=ROOT, capture_output=True, text=True, check=False)
    assert proc.returncode == 0, proc.stderr[-1000:]
    data = json.loads(proc.stdout)
    assert data["ok"] is True
    assert data["command"] == "trace_evidence"
