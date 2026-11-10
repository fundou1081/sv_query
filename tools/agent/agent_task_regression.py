#!/usr/bin/env python3
"""Portable agent task regression corpus (P145).

Each task runs the public CLI and assigns an explicit expected outcome.  The
harness reports exact/false-confident/false-found separately; a negative task
is never counted as success merely because the command exited 0.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CLI = ROOT / "run_cli.py"
FIX = ROOT / "sim" / "tests" / "fixtures"
DEEP = FIX / "deep_cross_module.sv"
CONSTRAINT = FIX / "constraint_neighborhood.sv"
ARCH = FIX / "arch_pair.sv"
BOUNDARY = FIX / "explicit_boundary.sv"
COVER = FIX / "golden_mini" / "coverage_demo.sv"
RUNNER = ROOT / "examples" / "project_adaptations" / "opentitan_fifo" / "trace_with_map.py"


def run(args: list[str], timeout: int = 120) -> tuple[dict | None, str]:
    try:
        p = subprocess.run([sys.executable, str(CLI), *args, "--json"],
                           capture_output=True, text=True, cwd=ROOT,
                           timeout=timeout)
    except subprocess.TimeoutExpired:
        return None, "timeout"
    try:
        data = json.loads(p.stdout)
    except json.JSONDecodeError:
        return None, f"non-JSON rc={p.returncode}: {p.stderr[-300:]}"
    if p.returncode != 0 and data.get("ok") is not False:
        return data, f"rc={p.returncode}"
    return data, ""


def _path(result: dict) -> list[str]:
    return result.get("path") or []


def task_deep_path() -> dict:
    d, err = run(["paths", "top.x", "top.y", "--directed", "-f", str(DEEP)])
    path = _path(d or {})
    ok = bool(err == "" and d and d.get("found") and len(path) >= 6
              and "top.u_mid.u_leaf.a" in path)
    return {"passed": ok, "expected": "found deep path", "error": err}


def task_deep_reverse() -> dict:
    d, err = run(["paths", "top.y", "top.x", "--directed", "-f", str(DEEP)])
    ok = bool(err == "" and d and d.get("found") is False)
    return {"passed": ok, "expected": "reverse not_found", "error": err}


def task_dataflow_deep() -> dict:
    d, err = run(["dataflow", "analyze", "top.x", "top.y", "-f", str(DEEP)])
    r = (d or {}).get("result", {})
    return {"passed": bool(err == "" and r.get("is_reachable")),
            "expected": "reachable", "error": err}


def task_verify_deep() -> dict:
    claim = json.dumps({"type": "path", "from": "top.x", "to": "top.y"})
    d, err = run(["verify", "claim", "--claim", claim, "-f", str(DEEP)])
    status = (d or {}).get("result", {}).get("status")
    return {"passed": bool(err == "" and status == "verified"),
            "expected": "verified", "error": err}


def task_constraint_chain() -> dict:
    d, err = run(["trace", "constraint-chain", "rnd_item.a", "rnd_item.d",
                  "-f", str(CONSTRAINT)])
    r = (d or {}).get("result", {})
    ok = bool(err == "" and r.get("found") and r.get("hop_count") == 3
              and r.get("blocks") == ["rnd_item.c_ab", "rnd_item.c_bc",
                                      "rnd_item.c_cd"])
    return {"passed": ok, "expected": "3-hop chain", "error": err}


def task_constraint_not_random() -> dict:
    d, err = run(["trace", "constraint-chain", "rnd_item.a", "rnd_item.k",
                  "-f", str(CONSTRAINT)])
    r = (d or {}).get("result", {})
    ok = bool(err == "" and r.get("found") is False
              and r.get("reason") == "endpoint_not_random")
    return {"passed": ok, "expected": "not_random", "error": err}


def task_constraint_unknown() -> dict:
    d, err = run(["trace", "constraint-chain", "rnd_item.a", "rnd_item.nope",
                  "-f", str(CONSTRAINT)])
    ok = bool(d and d.get("ok") is False and not (d.get("result") or {}).get("found"))
    return {"passed": ok, "expected": "explicit unknown", "error": err}


def task_frontier() -> dict:
    d, err = run(["trace", "frontier", "top.x", "--direction", "fanout",
                  "-f", str(ARCH)])
    r = (d or {}).get("result", {})
    rows = r.get("frontier") or []
    ok = bool(err == "" and rows and all("instance" in x for x in rows)
              and "FIFO" not in (r.get("note") or ""))
    return {"passed": ok, "expected": "generic frontier", "error": err}


def _boundary(map_data: dict) -> subprocess.CompletedProcess:
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(map_data, f)
        mp = f.name
    try:
        return subprocess.run(
            [sys.executable, str(RUNNER), "top.x", "top.y",
             "--file", str(BOUNDARY), "--map", mp],
            capture_output=True, text=True, cwd=ROOT, timeout=120)
    finally:
        Path(mp).unlink(missing_ok=True)


def task_boundary_trace() -> dict:
    p = _boundary({"adapter": "test", "boundaries": [{
        "src": "top.p", "dst": "top.q", "kind": "fifo_state",
        "evidence": "fixture:1", "confidence": "medium"}]})
    try:
        d = json.loads(p.stdout)
    except json.JSONDecodeError:
        return {"passed": False, "expected": "explicit boundary", "error": "non-JSON"}
    ok = bool(p.returncode == 0 and d.get("status") == "traced"
              and d.get("proven") is False and len(d.get("boundary_hops") or []) == 1)
    return {"passed": ok, "expected": "traced with asserted boundary", "error": ""}


def task_boundary_empty() -> dict:
    p = _boundary({"adapter": "test", "boundaries": []})
    try:
        d = json.loads(p.stdout)
    except json.JSONDecodeError:
        return {"passed": False, "expected": "stop at frontier", "error": "non-JSON"}
    ok = bool(p.returncode == 2 and d.get("status") == "boundary" and not d.get("chain"))
    return {"passed": ok, "expected": "boundary/no chain", "error": ""}


def task_schema_envelope() -> dict:
    d, err = run(["capabilities"])
    rows = {c["name"]: c for c in (d or {}).get("commands", [])}
    ok = bool(err == "" and rows.get("search", {}).get("envelope") == "direct"
              and rows.get("filelist prune", {}).get("write_scope") == "output"
              and "envelope_policy" in (d or {}).get("json_contract", {}))
    return {"passed": ok, "expected": "schema envelope/write_scope", "error": err}


def task_neighborhood_truncated() -> dict:
    d, err = run(["trace", "constraint-neighborhood", "rnd_item.a",
                  "--max-nodes", "1", "-f", str(CONSTRAINT)])
    summary = (d or {}).get("result", {}).get("summary", {})
    return {"passed": bool(err == "" and summary.get("truncated") is True),
            "expected": "truncated=true", "error": err}


def task_coverage_reason() -> dict:
    d, err = run(["trace", "coverpoints", "no.such.signal", "-f", str(COVER)])
    r = (d or {}).get("result", {})
    return {"passed": bool(err == "" and r.get("complete") is True
                           and r.get("reason") == "no_sampling_refs"),
            "expected": "coverage reason", "error": err}


TASKS = [
    ("deep_path", task_deep_path),
    ("deep_reverse", task_deep_reverse),
    ("dataflow_deep", task_dataflow_deep),
    ("verify_deep", task_verify_deep),
    ("constraint_chain", task_constraint_chain),
    ("constraint_not_random", task_constraint_not_random),
    ("constraint_unknown", task_constraint_unknown),
    ("frontier", task_frontier),
    ("boundary_trace", task_boundary_trace),
    ("boundary_empty", task_boundary_empty),
    ("schema_envelope", task_schema_envelope),
    ("neighborhood_truncated", task_neighborhood_truncated),
    ("coverage_reason", task_coverage_reason),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    results = []
    for name, fn in TASKS:
        try:
            out = fn()
        except Exception as e:  # explicit task-level failure, not a pass
            out = {"passed": False, "expected": "no exception", "error": str(e)}
        out["task"] = name
        results.append(out)
    passed = sum(1 for r in results if r["passed"])
    # A failing negative task is the only way this corpus can produce a false
    # positive; individual tasks already check explicit negative outcomes.
    false_found = sum(1 for r in results
                      if r["task"] in {"deep_reverse", "boundary_empty",
                                       "constraint_unknown"}
                      and not r["passed"])
    data = {"tasks": len(results), "passed": passed,
            "failed": len(results) - passed,
            "false_confident": 0 if passed == len(results) else None,
            "false_found": false_found,
            "results": results}
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print(f"{passed}/{len(results)} tasks passed")
        for r in results:
            print(f"  {'PASS' if r['passed'] else 'FAIL'} {r['task']}: "
                  f"{r['expected']} {r['error']}")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
