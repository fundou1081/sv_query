"""P171.6.2: mutation gate corpus is repo-only and runnable."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
GATE = ROOT / "tools/agent/task_corpora/mutation_faults_gate.json"
SCRIPT = ROOT / "tools/run_mutation_gate.py"


def test_mutation_gate_corpus_is_repo_only():
    tasks = json.loads(GATE.read_text())["tasks"]
    assert len(tasks) == 20
    for task in tasks:
        src = task["source"]
        assert not src.startswith("/")
        assert "picorv32" not in src
    assert SCRIPT.is_file()


def test_mutation_gate_script_has_explicit_verilator_failure():
    text = SCRIPT.read_text()
    assert "verilator not installed" in text
    assert "return 2" in text
    assert "detection_rate" in text
