"""P178: JSON error contract for class/constraints and evidence params."""
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
FL = ROOT / "sim/tests/fixtures/minimal_3module/filelist.f"


def _run(*args):
    return subprocess.run(["sv_query", *args], capture_output=True, text=True,
                          cwd=ROOT, timeout=120)


def test_class_missing_input_is_json_error():
    r = _run("class", "--json", "-q")
    assert r.returncode == 1
    d = json.loads(r.stdout)
    assert d["ok"] is False
    assert "required" in d["error"]


def test_constraints_missing_input_is_json_error():
    r = _run("trace", "constraints", "top.x", "--json", "-q")
    assert r.returncode == 1
    d = json.loads(r.stdout)
    assert d["ok"] is False
    assert "required" in d["error"]


def test_evidence_params_file_is_null_with_filelist():
    r = _run("trace", "evidence", "top_minimal.ready_o", "--filelist", str(FL),
             "--json", "-q")
    assert r.returncode == 0, r.stderr[-300:]
    d = json.loads(r.stdout)
    assert d["params"]["file"] is None
