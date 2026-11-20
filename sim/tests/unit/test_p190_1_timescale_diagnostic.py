"""P190.1 — diagnose timescale must actually see MissingTimeScale."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "run_cli.py", *args],
        cwd=ROOT, capture_output=True, text=True, timeout=120,
    )


def _write_mixed(tmp_path: Path) -> Path:
    (tmp_path / "with_ts.sv").write_text(
        "`timescale 1ns/1ps\nmodule with_ts; initial #1 $display(\"a\"); endmodule\n"
    )
    (tmp_path / "without_ts.sv").write_text(
        "module without_ts; logic x; initial begin #5 x = 1'b1; end endmodule\n"
    )
    filelist = tmp_path / "mixed.f"
    filelist.write_text(
        f"{tmp_path / 'with_ts.sv'}\n{tmp_path / 'without_ts.sv'}\n"
    )
    return filelist


def test_mixed_design_lists_missing_timescale(tmp_path):
    filelist = _write_mixed(tmp_path)
    proc = _run("diagnose", "timescale", "--filelist", str(filelist), "--json")
    assert proc.returncode == 0, proc.stderr[-400:]
    data = json.loads(proc.stdout)
    assert data["count"] == 1
    assert data["writes_files"] is False
    assert data["files"][0]["file"].endswith("without_ts.sv")
    assert not any(row["file"].endswith("with_ts.sv") for row in data["files"])


def test_all_files_have_timescale_is_empty(tmp_path):
    (tmp_path / "a.sv").write_text(
        "`timescale 1ns/1ps\nmodule a; initial #1 $display(\"a\"); endmodule\n"
    )
    (tmp_path / "b.sv").write_text(
        "`timescale 1ns/1ps\nmodule b; initial #2 $display(\"b\"); endmodule\n"
    )
    filelist = tmp_path / "all.f"
    filelist.write_text(f"{tmp_path / 'a.sv'}\n{tmp_path / 'b.sv'}\n")
    proc = _run("diagnose", "timescale", "--filelist", str(filelist), "--json")
    assert proc.returncode == 0, proc.stderr[-400:]
    data = json.loads(proc.stdout)
    assert data["count"] == 0
    assert data["files"] == []


def test_default_analysis_still_injects_timescale(tmp_path):
    (tmp_path / "one.sv").write_text(
        "module one; logic x; initial begin #5 x = 1'b1; end endmodule\n"
    )
    filelist = tmp_path / "one.f"
    filelist.write_text(f"{tmp_path / 'one.sv'}\n")
    proc = _run("stats", "--filelist", str(filelist), "--json")
    assert proc.returncode == 0, proc.stderr[-400:]
    assert json.loads(proc.stdout)["ok"] is True
