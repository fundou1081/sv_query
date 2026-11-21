"""P182.4 — capabilities-generated agent entry."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))

import gen_agent_skill as gen  # noqa: E402


def test_generated_reference_has_core_commands():
    text = gen.DOC.read_text(encoding="utf-8")
    assert "core commands in this reference: **39**" in text
    assert "all registered commands (core+exp): **45**" in text
    assert "| `drivers` |" in text
    assert "| `capabilities` |" in text


def test_generator_check_passes_current_tree():
    assert gen.main(["--check"]) == 0


def test_generated_reference_and_skill_reference_are_identical():
    assert gen._strip_volatile(gen.DOC.read_text(encoding="utf-8")).rstrip(
        "\n"
    ) == gen._strip_volatile(gen.SKILL_REF.read_text(encoding="utf-8")).rstrip(
        "\n"
    )


def test_generated_rows_match_core_command_count():
    from sv_query.cli._registry import to_json

    data = to_json()
    text = gen.DOC.read_text(encoding="utf-8")
    rows = [line for line in text.splitlines() if line.startswith("| `")]
    assert len(rows) == sum(1 for c in data["commands"] if c["layer"] == "core")
    assert (ROOT / ".agents/skills/query-protocol/SKILL.md").exists()
    skill = (ROOT / ".agents/skills/query-protocol/SKILL.md").read_text(encoding="utf-8")
    for rel in ("docs/agent/CAPABILITIES_GENERATED.md",
                ".agents/skills/query-protocol/references/capabilities.md"):
        assert rel in skill
        assert (ROOT / rel).exists()


def test_missing_generated_file_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(gen, "DOC", tmp_path / "missing.md")
    monkeypatch.setattr(gen, "SKILL_REF", tmp_path / "missing_ref.md")
    assert gen.main(["--check"]) == 1


def test_stale_generated_reference_fails(tmp_path, monkeypatch):
    doc = tmp_path / "capabilities.md"
    ref = tmp_path / "ref.md"
    monkeypatch.setattr(gen, "DOC", doc)
    monkeypatch.setattr(gen, "SKILL_REF", ref)
    assert gen.main([]) == 0
    doc.write_text(doc.read_text(encoding="utf-8") + "\nstale\n", encoding="utf-8")
    assert gen.main(["--check"]) == 1
