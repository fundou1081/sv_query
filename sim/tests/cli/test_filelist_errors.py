"""[P72] filelist 导致的 slang 编译失败必须显式分类。"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _run(fl: Path):
    return subprocess.run(["sv_query", "drivers", "top.y", "--filelist", str(fl),
                           "--json", "--no-cache"], capture_output=True, text=True,
                          timeout=60, cwd=str(ROOT))


def test_filelist_with_no_valid_sources_is_explicit(tmp_path):
    fl = tmp_path / "empty.f"
    fl.write_text(f"{tmp_path / 'missing.sv'}\n")
    r = _run(fl)
    assert r.returncode != 0
    d = json.loads(r.stdout)
    assert d["ok"] is False
    assert d["error_code"] == "E_FILELIST_INCOMPLETE"


def test_filelist_elaboration_failure_is_not_silent(tmp_path):
    src = tmp_path / "miss.sv"
    src.write_text("module top(input a, output y); missing u(.a(a), .y(y)); endmodule\n")
    fl = tmp_path / "f.f"
    fl.write_text(f"{src}\n")
    r = _run(fl)
    assert r.returncode != 0
    d = json.loads(r.stdout)
    assert d["ok"] is False
    assert d["error_code"] == "E_ELABORATION_FAILED"
    assert "unknown module" in d["error"]
