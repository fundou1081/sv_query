#!/usr/bin/env python3
"""[P69] 独立复验：结果覆盖 + 当前图 ground truth。

用法:
  python3 tools/benchmark/verify_long_range.py
  python3 tools/benchmark/verify_long_range.py --json
  python3 tools/benchmark/verify_long_range.py --no-truth   # 只验结果/评分

默认使用 tools/benchmark/long_range_tasks.json 的稳定 source 定义，
不依赖当时的 /tmp source copy。source 缺失时显式失败，不跳过。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOLS = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(TOOLS))

from inputs import ensure_serv_filelist  # noqa: E402
from score_long_range import score  # noqa: E402
from sv_query.trace.unified_tracer import UnifiedTracer  # noqa: E402

TASKS = TOOLS / "long_range_tasks.json"
RESULTS = ROOT / "docs" / "validation" / "long_range_12_2026-11-05.json"


def _source_key(task: dict) -> tuple[str, str]:
    src = task["source"]
    if src["kind"] == "filelist":
        return "filelist", str(ROOT / src["path"])
    if src["kind"] == "serv":
        path = ensure_serv_filelist()
        if not path:
            raise RuntimeError("SERV sources unavailable (openrtl/serv missing)")
        return "filelist", path
    if src["kind"] == "file":
        path = Path(src["path"]).expanduser()
        if not path.exists():
            raise RuntimeError(f"source file missing: {path}")
        return "file", str(path)
    raise RuntimeError(f"unknown source kind: {src['kind']}")


def _build_tracer(kind: str, path: str) -> UnifiedTracer:
    if kind == "file":
        return UnifiedTracer(files=[path], log_level="ERROR")
    return UnifiedTracer(filelist=path, log_level="ERROR")


def _query(tracer: UnifiedTracer, task: dict) -> dict:
    q = task["query"]
    if q["cmd"] == "path":
        path = tracer.find_path(q["src"], q["dst"])
        return {"path": path or [], "count": len(path) - 1 if path else 0}
    rows = (tracer.trace_fanin(q["signal"], depth=1) if q["cmd"] == "fanin"
            else tracer.trace_fanout(q["signal"], depth=1))
    out = {("drivers" if q["cmd"] == "fanin" else "loads"): [r.id for r in rows]}
    out["count"] = len(rows)
    if q.get("also_loads"):
        out["loads"] = [r.id for r in tracer.trace_fanout(q["signal"], depth=1)]
    return out


def _matches(got: dict, expected: dict) -> tuple[bool, list[str]]:
    bad = []
    for field, want in expected.items():
        have = got.get(field)
        if field == "path":
            ok = have == want
        elif field == "count":
            ok = have == want
        else:
            ok = set(have or []) == set(want)
        if not ok:
            bad.append(f"{field}: got={have!r} want={want!r}")
    return not bad, bad


def verify_truth(tasks: dict) -> list[dict]:
    cache: dict[tuple[str, str], UnifiedTracer] = {}
    rows = []
    for task in tasks["tasks"]:
        key = _source_key(task)
        if key not in cache:
            cache[key] = _build_tracer(*key)
            cache[key].build_graph(use_cache=False)
        got = _query(cache[key], task)
        ok, bad = _matches(got, task["ground_truth"])
        rows.append({"task_id": task["id"], "ok": ok, "got": got,
                     "expected": task["ground_truth"], "mismatches": bad})
    return rows


def verify_results(results: dict, tasks: dict) -> list[str]:
    problems = []
    want = {(t["id"], m, a)
            for t in tasks["tasks"]
            for m in ("MiniMax-M3", "DeepSeek-Flash")
            for a in ("source", "svq")}
    have = {(r["task_id"], r["model"], r["arm"]) for r in results["results"]}
    missing = want - have
    extra = have - want
    if missing:
        problems.append(f"missing cells: {sorted(missing)}")
    if extra:
        problems.append(f"extra cells: {sorted(extra)}")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", type=Path, default=TASKS)
    ap.add_argument("--results", type=Path, default=RESULTS)
    ap.add_argument("--no-truth", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    tasks = json.loads(args.tasks.read_text(encoding="utf-8"))
    results = json.loads(args.results.read_text(encoding="utf-8"))
    coverage = verify_results(results, tasks)
    scores = score(results)["summary"]
    truth = [] if args.no_truth else verify_truth(tasks)
    truth_bad = [r for r in truth if not r["ok"]]
    ok = not coverage and not truth_bad
    out = {"ok": ok, "coverage_problems": coverage,
           "truth_checked": len(truth), "truth_mismatches": truth_bad,
           "scores": scores}
    if args.json:
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        print(f"coverage: {'OK' if not coverage else 'FAIL'} ({len(results['results'])} cells)")
        for p in coverage:
            print(" ", p)
        if not args.no_truth:
            print(f"truth: {len(truth)-len(truth_bad)}/{len(truth)} OK")
            for r in truth_bad:
                print(f"  {r['task_id']}: {'; '.join(r['mismatches'])}")
        print(f"result: {'✅ PASS' if ok else '❌ FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
