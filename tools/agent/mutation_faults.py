#!/usr/bin/env python3
"""P165.3.2: mutation fault injection with an independent Verilator oracle.

A fault is defined by a concrete source mutation.  The mutation diff is the
ground truth; Verilator proves the mutant still elaborates; sv_query is then
asked the same query on baseline and mutant.  This avoids self-authored
expected answers and does not require an external project's git history.

Usage:
  python3 tools/agent/mutation_faults.py \
    --tasks tools/agent/task_corpora/mutation_faults_pilot.json --json
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CLI = ROOT / "run_cli.py"


def _load_verilator():
    import importlib.util
    p = Path(__file__).with_name("verilator_oracle.py")
    spec = importlib.util.spec_from_file_location("_svq_verilator_oracle", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _expand(path: str) -> Path:
    return Path(os.path.expandvars(os.path.expanduser(path)))


def _query(args: list[str]) -> tuple[int, dict | None, str]:
    cmd = [sys.executable, str(CLI), *args, "--json", "-q", "--no-cache"]
    proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)
    try:
        data = json.loads(proc.stdout) if proc.stdout.strip() else None
    except json.JSONDecodeError:
        data = None
    return proc.returncode, data, proc.stderr


def _facts(data: dict | None, kind: str) -> set[str] | None:
    if not isinstance(data, dict) or not data.get("ok"):
        return None
    signals = (data.get("result") or {}).get("signals") or []
    if not signals:
        return set()
    items = signals[0].get("drivers" if kind == "drivers" else "loads") or []
    return {str(x.get("id")) for x in items}


def _satisfies(facts: set[str] | None, expect: dict) -> bool:
    if facts is None:
        return False
    if not set(expect.get("contains", [])).issubset(facts):
        return False
    if set(expect.get("not_contains", [])) & facts:
        return False
    return True


def _prepare(task: dict, work: Path) -> tuple[Path, Path | None, str]:
    src = _expand(task["source"])
    if not src.is_file():
        raise FileNotFoundError(src)
    target = work / src.name
    shutil.copy2(src, target)
    text = target.read_text(encoding="utf-8")
    mut = task["mutation"]
    old, new = mut["old"], mut["new"]
    count = text.count(old)
    if count != int(mut.get("count", 1)):
        raise ValueError(f"mutation matched {count} times, expected {mut.get('count', 1)}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")
    filelist = None
    if task.get("filelist"):
        fl = _expand(task["filelist"])
        if not fl.is_file():
            raise FileNotFoundError(fl)
        filelist = work / fl.name
        lines = []
        for line in fl.read_text(encoding="utf-8").splitlines():
            p = Path(line.strip())
            if p.resolve() == src.resolve():
                lines.append(str(target))
            else:
                lines.append(line)
        filelist.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return target, filelist, target.read_text(encoding="utf-8")


def run_task(task: dict) -> dict:
    out = {"task_id": task.get("id"), "status": "error", "query": task.get("query")}
    with tempfile.TemporaryDirectory(prefix="svq_mut_") as td:
        work = Path(td)
        try:
            target, filelist, _ = _prepare(task, work)
        except Exception as e:
            out.update(error=f"prepare: {e}")
            return out
        oracle = _load_verilator()
        if filelist:
            v = oracle.run_verilator(str(filelist), None, task.get("top"))
        else:
            v = oracle.run_verilator(None, str(target), task.get("top"))
        if not v.get("ok"):
            out.update(status="invalid_mutant", verilator=v)
            return out
        args = [task["query"], task["signal"]]
        if filelist:
            args += ["--filelist", str(filelist)]
        else:
            args += ["--file", str(target)]
        rc, data, err = _query(args)
        after = _facts(data, task["query"])
        if after is None:
            out.update(status="query_error", rc=rc, stderr=err[-1000:], query_data=data)
            return out
        # Baseline query against the original source (no mutation).
        base_args = [task["query"], task["signal"]]
        if task.get("filelist"):
            base_args += ["--filelist", str(_expand(task["filelist"]))]
        else:
            base_args += ["--file", str(_expand(task["source"]))]
        brc, bdata, berr = _query(base_args)
        before = _facts(bdata, task["query"])
        exp = task.get("expect") or {}
        if not _satisfies(before, exp.get("before", {})):
            out.update(status="invalid_baseline", before=sorted(before or []),
                       stderr=berr[-1000:])
            return out
        if not _satisfies(after, exp.get("after", {})):
            out.update(status="failed", before=sorted(before or []),
                       after=sorted(after))
            return out
        out.update(status="passed", before=sorted(before or []),
                   after=sorted(after), verilator_ok=True)
        return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", required=True)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    spec = json.loads(_expand(args.tasks).read_text(encoding="utf-8"))
    results = [run_task(t) for t in spec.get("tasks", [])]
    summary = {
        "total": len(results),
        "passed": sum(r["status"] == "passed" for r in results),
        "failed": sum(r["status"] == "failed" for r in results),
        "invalid": sum(r["status"].startswith("invalid") for r in results),
        "other": sum(r["status"] not in ("passed", "failed") and
                     not r["status"].startswith("invalid") for r in results),
        "results": results,
    }
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(f"passed={summary['passed']} failed={summary['failed']} "
              f"invalid={summary['invalid']} other={summary['other']}")
        for r in results:
            print(f"{r['task_id']}: {r['status']}")
    return 0 if summary["failed"] == 0 and summary["other"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
