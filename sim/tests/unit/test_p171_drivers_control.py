"""P171.4: drivers CLOCK/RESET opt-in (no external corpus)."""
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BASE = str(ROOT / "sim/tests/fixtures/minimal_3module/filelist.f")


def _drivers(*extra):
    r = subprocess.run(["python3", str(ROOT / "run_cli.py"), "drivers",
                        "top_minimal.sa1.ready_q", "--filelist", BASE,
                        "--json", "-q", *extra],
                       capture_output=True, text=True, cwd=ROOT)
    return r, json.loads(r.stdout)


def test_drivers_include_clock_and_reset():
    _, d = _drivers()
    ids = {x["id"] for x in d["result"]["signals"][0]["drivers"]}
    assert "top_minimal.sa1.clk" not in ids
    assert "top_minimal.sa1.rst_n" not in ids

    _, clock = _drivers("--include-clock")
    cids = {x["id"] for x in clock["result"]["signals"][0]["drivers"]}
    assert "top_minimal.sa1.clk" in cids

    _, reset = _drivers("--include-reset")
    rids = {x["id"] for x in reset["result"]["signals"][0]["drivers"]}
    assert "top_minimal.sa1.rst_n" in rids


def test_drivers_include_control_is_explicit_error():
    r, d = _drivers("--include-control")
    assert r.returncode == 0  # explicit business error, same shape as fanout
    assert d["ok"] is False
    assert "unsupported" in (d.get("errors") or [{}])[0].get("error", "").lower()
