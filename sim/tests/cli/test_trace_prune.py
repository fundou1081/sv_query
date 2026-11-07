"""[P91] trace --prune: build parity + explicit fallback metadata."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
FL = ROOT / "sim" / "tests" / "fixtures" / "strict_uart" / "filelist.f"


def _run(*args):
    return subprocess.run(["sv_query", *args], cwd=str(ROOT),
                          capture_output=True, text=True, timeout=60)


def _sig(*args):
    r = _run(*args)
    assert r.returncode == 0, r.stderr[-300:]
    return json.loads(r.stdout)["result"]["signals"][0]


def test_prune_fanin_matches_full():
    full = _sig("drivers", "uart_top.rx_fifo.count_q", "--filelist", str(FL),
                "--depth", "1", "--json")
    pruned = _sig("drivers", "uart_top.rx_fifo.count_q", "--filelist", str(FL),
                  "--top", "uart_top", "--prune", "--depth", "1", "--json")
    assert pruned["count"] == full["count"]
    assert {d["id"] for d in pruned["drivers"]} == {d["id"] for d in full["drivers"]}


def test_prune_fanout_matches_full():
    full = _sig("loads", "uart_top.rx_fifo.count_q", "--filelist", str(FL),
                "--depth", "1", "--json")
    pruned = _sig("loads", "uart_top.rx_fifo.count_q", "--filelist", str(FL),
                  "--top", "uart_top", "--prune", "--depth", "1", "--json")
    assert pruned["count"] == full["count"]
    assert {d["id"] for d in pruned["loads"]} == {d["id"] for d in full["loads"]}


def test_prune_reports_selected_and_fallback_false():
    r = _run("drivers", "uart_top.rx_fifo.count_q", "--filelist", str(FL),
             "--top", "uart_top", "--prune", "--json")
    assert r.returncode == 0, r.stderr[-300:]
    info = json.loads(r.stdout)["prune"]
    assert info["enabled"] is True
    assert info["selected_count"] == 2
    assert info["fallback"] is False


def test_prune_requires_top():
    r = _run("drivers", "uart_top.rx_fifo.count_q", "--filelist", str(FL),
             "--prune", "--json")
    assert r.returncode != 0
    data = json.loads(r.stdout)
    assert data["ok"] is False
    assert "--top" in data["error"]


def test_prune_requires_filelist():
    src = ROOT / "sim" / "tests" / "fixtures" / "strict_uart" / "uart_top.sv"
    r = _run("drivers", "uart_top.rx_fifo.count_q", "--file", str(src),
             "--prune", "--json")
    assert r.returncode != 0
    assert json.loads(r.stdout)["ok"] is False
