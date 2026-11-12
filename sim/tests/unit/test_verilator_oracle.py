"""P165.3.1: independent Verilator elaboration oracle (skip if unavailable)."""
import importlib.util
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
MOD_PATH = ROOT / "tools/agent/verilator_oracle.py"


def _load():
    spec = importlib.util.spec_from_file_location("verilator_oracle", MOD_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.skipif(shutil.which("verilator") is None, reason="verilator not installed")
def test_simple_rtl_elaborates_under_verilator():
    mod = _load()
    result = mod.run_verilator(None, str(ROOT / "sim/test_simple.sv"), "top")
    assert result["available"] is True
    assert result["ok"] is True
    assert result["error_count"] == 0
