"""P165.3.2: mutation fault harness (small local task; Verilator optional)."""
import importlib.util
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
MOD = ROOT / "tools/agent/mutation_faults.py"


def _load():
    spec = importlib.util.spec_from_file_location("mutation_faults", MOD)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.skipif(shutil.which("verilator") is None, reason="verilator not installed")
def test_simple_driver_swap_ground_truth():
    mod = _load()
    task = {
        "id": "t",
        "source": "sim/test_simple.sv",
        "top": "top",
        "query": "drivers",
        "signal": "top.data",
        "mutation": {"old": "assign data = din;", "new": "assign data = en;"},
        "expect": {
            "before": {"contains": ["top.din"]},
            "after": {"contains": ["top.en"], "not_contains": ["top.din"]},
        },
    }
    result = mod.run_task(task)
    assert result["status"] == "passed", result
