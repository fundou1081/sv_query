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
    """Resolve task paths relative to the repo, never to the caller CWD."""
    p = Path(os.path.expandvars(os.path.expanduser(path)))
    return p if p.is_absolute() else (ROOT / p)


def _query(args: list[str]) -> tuple[int, dict | None, str]:
    cmd = [sys.executable, str(CLI), *args, "--json", "-q"]
    if args and args[0] in ("drivers", "loads"):
        cmd.append("--no-cache")
    proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)
    try:
        data = json.loads(proc.stdout) if proc.stdout.strip() else None
    except json.JSONDecodeError:
        data = None
    return proc.returncode, data, proc.stderr


def _facts(data: dict | None, kind: str) -> dict | None:
    """Normalize a query result to {items: set, fields: dict}."""
    if not isinstance(data, dict) or not data.get("ok"):
        return None
    if kind in ("drivers", "loads"):
        signals = (data.get("result") or {}).get("signals") or []
        if not signals:
            return {"items": set(), "fields": {}}
        sig = signals[0]
        items = sig.get(kind) or []
        fields = {
            k: sig.get(k) for k in (
                "driver_count", "multi_driver", "driver_conflict",
                "conditional_drivers",
            )
            if k in sig
        }
        return {"items": {str(x.get("id")) for x in items}, "fields": fields}
    if kind == "paths":
        return {
            "items": {str(x) for x in (data.get("path") or [])},
            "fields": {"found": bool(data.get("found"))},
        }
    if kind == "controlflow":
        result = data.get("result") or {}
        exprs = set()
        for cd in result.get("conditioned_drivers") or []:
            for cond in cd.get("conditions") or []:
                exprs.add(str(cond.get("expr", "")))
        return {"items": exprs, "fields": {}}
    if kind == "dataflow":
        result = data.get("result") or {}
        return {
            "items": {str(x) for x in (result.get("intermediate_signals") or [])},
            "fields": {
                "is_reachable": result.get("is_reachable"),
                "clock_domain": result.get("clock_domain"),
                "primary_is_async": result.get("primary_is_async"),
            },
        }
    return None


def _satisfies(facts: dict | None, expect: dict) -> bool:
    if facts is None:
        return False
    items = facts["items"]
    if not set(expect.get("contains", [])).issubset(items):
        return False
    if set(expect.get("not_contains", [])) & items:
        return False
    for key, value in (expect.get("fields") or {}).items():
        if facts["fields"].get(key) != value:
            return False
    return True


def _query_args(task: dict) -> list[str]:
    kind = task["query"]
    if kind == "paths":
        return ["paths", task["signal"], task["to_signal"]]
    if kind == "dataflow":
        return ["dataflow", "analyze", task["signal"], task["to_signal"]]
    if kind == "controlflow":
        return ["controlflow", "analyze", task["signal"]]
    return [kind, task["signal"]]


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
            raw = line.strip()
            if not raw or raw.startswith(("#", "//")):
                lines.append(line)
                continue
            if raw.startswith("+incdir+"):
                d = raw[len("+incdir+"):].strip()
                p = Path(d)
                if not p.is_absolute():
                    p = fl.parent / p
                lines.append(f"+incdir+{p.resolve()}")
                continue
            p = Path(raw)
            if not p.is_absolute():
                p = fl.parent / p
            lines.append(str(target) if p.resolve() == src.resolve() else str(p.resolve()))
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
        args = _query_args(task)
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
        base_args = _query_args(task)
        if task.get("filelist"):
            base_args += ["--filelist", str(_expand(task["filelist"]))]
        else:
            base_args += ["--file", str(_expand(task["source"]))]
        brc, bdata, berr = _query(base_args)
        before = _facts(bdata, task["query"])
        exp = task.get("expect") or {}
        if not _satisfies(before, exp.get("before", {})):
            out.update(status="invalid_baseline",
                       before=sorted((before or {}).get("items", [])),
                       stderr=berr[-1000:])
            return out
        if not _satisfies(after, exp.get("after", {})):
            out.update(status="failed",
                   before=sorted((before or {}).get("items", [])),
                   after=sorted((after or {}).get("items", [])))
            return out
        out.update(status="passed",
                   before=sorted((before or {}).get("items", [])),
                   after=sorted((after or {}).get("items", [])),
                   verilator_ok=True)
        return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", required=True)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    spec = json.loads(_expand(args.tasks).read_text(encoding="utf-8"))
    results = [run_task(t) for t in spec.get("tasks", [])]
    passed = sum(r["status"] == "passed" for r in results)
    failed = sum(r["status"] == "failed" for r in results)
    valid = passed + failed
    by_query: dict[str, int] = {}
    for r in results:
        q = str(r.get("query"))
        by_query[q] = by_query.get(q, 0) + 1
    summary = {
        "total": len(results),
        "passed": passed,
        "failed": failed,
        "invalid": sum(r["status"].startswith("invalid") for r in results),
        "other": sum(r["status"] not in ("passed", "failed") and
                     not r["status"].startswith("invalid") for r in results),
        "valid": valid,
        "detection_rate": (passed / valid) if valid else None,
        "by_query": by_query,
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
