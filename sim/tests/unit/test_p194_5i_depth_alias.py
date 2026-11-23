"""P194.5i — depth=1 must not return a dangling bit-range alias as its own driver."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _run(path: Path, *args: str) -> dict:
    proc = subprocess.run(
        [sys.executable, "run_cli.py", *args, "--file", str(path),
         "--json", "--compact", "--no-cache"],
        cwd=ROOT, capture_output=True, text=True, timeout=120,
    )
    assert proc.returncode == 0, proc.stderr[-400:]
    return json.loads(proc.stdout)["result"]["signals"][0]


def _fixture(tmp_path: Path) -> Path:
    sv = tmp_path / "bin2gray.sv"
    sv.write_text(
        "module bin2gray(input logic [31:0] bin_in, output logic [31:0] gray_out);\n"
        "  assign gray_out = bin_in ^ (bin_in >> 1);\n"
        "endmodule\n")
    return sv


def test_depth1_skips_dangling_full_range_alias(tmp_path):
    row = _run(_fixture(tmp_path), "drivers", "gray_out", "--depth", "1")
    ids = [item["id"] for item in row["drivers"]]
    assert "bin2gray.gray_out[31:0]" not in ids
    assert any("bin2gray.bin_in" in item for item in ids)


def test_depth1_input_port_does_not_report_its_own_bit_alias(tmp_path):
    row = _run(_fixture(tmp_path), "drivers", "bin_in", "--depth", "1")
    ids = [item["id"] for item in row["drivers"]]
    assert "bin2gray.bin_in[31:0]" not in ids
