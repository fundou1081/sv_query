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


@pytest.mark.skipif(shutil.which("verilator") is None, reason="verilator not installed")
def test_path_query_mutation():
    mod = _load()
    task = {
        "id": "path",
        "source": "sim/test_simple.sv",
        "top": "top",
        "query": "paths",
        "signal": "top.din",
        "to_signal": "top.dout",
        "mutation": {"old": "assign data = din;", "new": "assign data = en;"},
        "expect": {
            "before": {"fields": {"found": True}},
            "after": {"fields": {"found": False}},
        },
    }
    result = mod.run_task(task)
    assert result["status"] == "passed", result


@pytest.mark.skipif(shutil.which("verilator") is None, reason="verilator not installed")
def test_condition_query_mutation():
    mod = _load()
    task = {
        "id": "condition",
        "source": "sim/test_simple.sv",
        "top": "top",
        "query": "controlflow",
        "signal": "top.dout",
        "mutation": {"old": "else if (en)", "new": "else if (!en)"},
        "expect": {
            "before": {"contains": ["!(!rst_n) && en"]},
            "after": {"contains": ["!(!rst_n) && !en"]},
        },
    }
    result = mod.run_task(task)
    assert result["status"] == "passed", result


@pytest.mark.skipif(shutil.which("verilator") is None, reason="verilator not installed")
def test_cdc_bypass_mutation():
    mod = _load()
    task = {
        "id": "cdc",
        "source": "sim/tests/integration/dataflow_fixtures/two_flop_sync.sv",
        "top": "two_flop_sync",
        "query": "dataflow",
        "signal": "two_flop_sync.data_in",
        "to_signal": "two_flop_sync.data_out",
        "mutation": {"old": ".data_b_i(async_wire)", "new": ".data_b_i(data_in)"},
        "expect": {
            "before": {"contains": ["two_flop_sync.u_a.data_a_o"],
                       "fields": {"primary_is_async": True}},
            "after": {"not_contains": ["two_flop_sync.u_a.data_a_o"],
                      "fields": {"primary_is_async": False}},
        },
    }
    result = mod.run_task(task)
    assert result["status"] == "passed", result
