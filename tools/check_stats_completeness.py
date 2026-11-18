#!/usr/bin/env python3
"""[P182.3] stats completeness contract.

- A successful stats must report elaboration_errors=[].
- Malformed RTL under --json must be a structured E_ELABORATION_FAILED
  failure with no result, not a bare human error on stderr.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIXTURE = "sim/tests/fixtures/scheduler_minimal/filelist.f"


def _run_stats(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "run_cli.py", "stats", *args, "--json"],
        cwd=ROOT, capture_output=True, text=True, timeout=120,
    )


def check_success() -> list[str]:
    proc = _run_stats("--filelist", FIXTURE)
    if proc.returncode != 0:
        return [f"success rc={proc.returncode}, expected 0"]
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        return [f"success stdout not JSON: {exc.msg}"]
    if data.get("ok") is not True:
        return [f"success ok={data.get('ok')!r}, expected true"]
    result = data.get("result")
    if not isinstance(result, dict):
        return ["success result is not object"]
    errors = result.get("elaboration_errors")
    if errors != []:
        return [f"success elaboration_errors={errors!r}, expected []"]
    return []


def check_elaboration_failure() -> list[str]:
    with tempfile.TemporaryDirectory(prefix="svq_p182_3_") as tmp:
        src = Path(tmp) / "bad.sv"
        src.write_text("module top; missing_child u(); endmodule\n")
        proc = _run_stats("-f", str(src))
    problems = []
    if proc.returncode != 1:
        problems.append(f"failure rc={proc.returncode}, expected 1")
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        return problems + [f"failure stdout not JSON: {exc.msg}"]
    if data.get("ok") is not False:
        problems.append(f"failure ok={data.get('ok')!r}, expected false")
    if data.get("error_code") != "E_ELABORATION_FAILED":
        problems.append(f"failure error_code={data.get('error_code')!r}")
    if not data.get("errors"):
        problems.append("failure errors is empty")
    if "result" in data:
        problems.append("failure must not include result")
    return problems


def check_filelist_failure() -> list[str]:
    with tempfile.TemporaryDirectory(prefix="svq_p182_3_fl_") as tmp:
        filelist = Path(tmp) / "bad.f"
        filelist.write_text(str(Path(tmp) / "missing.sv") + "\n")
        proc = _run_stats("--filelist", str(filelist))
    problems = []
    if proc.returncode != 1:
        problems.append(f"filelist failure rc={proc.returncode}, expected 1")
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        return problems + [f"filelist failure stdout not JSON: {exc.msg}"]
    if data.get("error_code") != "E_FILELIST_INCOMPLETE":
        problems.append(f"filelist failure error_code={data.get('error_code')!r}")
    if "result" in data:
        problems.append("filelist failure must not include result")
    return problems


def main() -> int:
    problems = check_success() + check_elaboration_failure() + check_filelist_failure()
    if problems:
        for problem in problems:
            print(f"FAIL\t{problem}")
        print(f"stats-completeness: FAIL ({len(problems)} problems)")
        return 1
    print("stats-completeness: PASS (success empty + structured failures)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
