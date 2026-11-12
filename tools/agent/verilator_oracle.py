#!/usr/bin/env python3
"""P165.3 alternative: independent Verilator lint/elaboration oracle.

No OpenTitan git history is required.  We use a second, independently
maintained elaborator (Verilator) to check that a candidate filelist or RTL
unit actually elaborates; sv_query remains the query engine, not the judge of
its own filelist.

Usage:
  python3 tools/agent/verilator_oracle.py --filelist /tmp/uart.f --top uart --json
  python3 tools/agent/verilator_oracle.py --file sim/test_simple.sv --top top --json

This is an external *compile oracle*, not a semantic proof of every query.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path


def run_verilator(filelist: str | None, file: str | None, top: str | None,
                  extra: list[str] | None = None) -> dict:
    exe = shutil.which("verilator")
    if not exe:
        return {"ok": False, "available": False, "error": "verilator not found"}
    cmd = [exe, "--lint-only", "-Wno-fatal"]
    if top:
        cmd += ["--top-module", top]
    if filelist:
        cmd += ["-f", filelist]
    elif file:
        cmd.append(file)
    else:
        return {"ok": False, "available": True, "error": "filelist or file required"}
    cmd += extra or []
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    except subprocess.TimeoutExpired:
        return {"ok": False, "available": True, "error": "verilator timeout (120s)",
                "command": cmd}
    text = proc.stdout + "\n" + proc.stderr
    errors = [line for line in text.splitlines() if line.startswith("%Error")]
    warnings = [line for line in text.splitlines() if line.startswith("%Warning")]
    version = ""
    m = re.search(r"Verilator\s+([0-9][^\s]*)", text)
    if m:
        version = m.group(1)
    return {
        "ok": proc.returncode == 0,
        "available": True,
        "rc": proc.returncode,
        "version": version,
        "errors": errors[-20:],
        "error_count": len(errors),
        "warning_count": len(warnings),
        "command": cmd,
        "stdout_tail": proc.stdout[-1500:],
        "stderr_tail": proc.stderr[-1500:],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--filelist")
    src.add_argument("--file")
    ap.add_argument("--top", default=None)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    result = run_verilator(args.filelist, args.file, args.top)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"verilator ok={result.get('ok')} rc={result.get('rc')} "
              f"errors={result.get('error_count')} warnings={result.get('warning_count')}")
        for line in result.get("errors", [])[:5]:
            print(line, file=sys.stderr)
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
