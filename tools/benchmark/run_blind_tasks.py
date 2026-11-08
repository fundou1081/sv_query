#!/usr/bin/env python3
"""[P110] Blind realistic structural validation for constrained svq_query."""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import time
from pathlib import Path

import run_long_range as base
from session_telemetry import extract

ROOT = base.ROOT
TOOL_PATCH = ROOT / "tools" / "agent" / "svq_query.patch.yml"
TASKS = ROOT / "tools" / "benchmark" / "blind_tasks_2026-11-08.json"
WORK = Path("/tmp/blind_pilot")
SNAPS = Path("/tmp/lr_ad_snaps")


def answer_shape(kind: str) -> str:
    if kind == "neighbors":
        return '{"drivers":["ids"],"loads":["ids"]}'
    if kind == "loads":
        return '{"loads":["ids"]}'
    if kind == "path":
        return '{"path":["ids"],"hop_count":integer}'
    return '{"reason":"not_found"}'


def prompt(task: dict) -> str:
    return (
        "Use only svq_query. bash/read/grep are unavailable. "
        f"Snapshot: {task['snapshot']!r}. "
        f"{task['question']} "
        "Return ONE valid JSON object, no markdown:\n"
        f'{{"task_id":{task["id"]!r},"found":true,'
        f'"answer":{answer_shape(task["kind"])},'
        '"confidence":"high|medium|low","evidence":[]}'
        " Use canonical IDs from the tool result. If lookup fails, set "
        '`found:false` and answer {"reason":"not_found"}; do not invent IDs.'
    )


def score(task: dict, parsed: dict | None) -> tuple[bool, bool]:
    if not parsed:
        return False, False
    exp = task["expected"]
    found = parsed.get("found") is exp["found"]
    ans = parsed.get("answer") if isinstance(parsed.get("answer"), dict) else {}
    if "drivers" not in ans and "driver_ids" in ans:
        ans = {**ans, "drivers": ans.get("driver_ids", [])}
    if "loads" not in ans and "load_ids" in ans:
        ans = {**ans, "loads": ans.get("load_ids", [])}
    if not found:
        return False, parsed.get("confidence") == "high"
    if task["kind"] == "path":
        ok = (ans.get("path") == exp["answer"]["path"]
              and ans.get("hop_count") == exp["answer"]["hop_count"])
    elif task["kind"] == "unknown":
        ok = str(ans.get("reason", "")).lower() == "not_found"
    elif task["kind"] == "loads":
        ok = sorted(ans.get("loads", [])) == sorted(exp["answer"]["loads"])
    else:
        ok = (sorted(ans.get("drivers", [])) == sorted(exp["answer"]["drivers"])
              and sorted(ans.get("loads", [])) == sorted(exp["answer"]["loads"]))
    return ok, (not ok and parsed.get("confidence") == "high")


def run_one(task: dict, model: dict) -> dict:
    ws = WORK / model["label"].replace(".", "_") / task["id"]
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True)
    env = base._env()
    env["SVQ_SNAPSHOT_DIR"] = task.get("snapshot_dir", str(SNAPS))
    env["SVQ_SOURCE_ROOT"] = task["source_root"]
    patch = (base.INTERACTIVE / model["patch"]).resolve()
    cmd = ["dsh", "--profile", "headless", "--patch", str(patch),
           "--patch", str(TOOL_PATCH), prompt(task)]
    t0 = time.time()
    r = subprocess.run(cmd, cwd=ws, env=env, capture_output=True, text=True,
                       timeout=300)
    (ws / "raw.txt").write_text(r.stdout)
    parsed = base._extract_json(r.stdout)
    exact, false_conf = score(task, parsed)
    try:
        tel = extract(ws)
        calls = tel.get("tool_detail", [])
    except Exception:
        calls = []
    return {
        "task_id": task["id"], "model": model["label"], "kind": task["kind"],
        "duration_ms": int((time.time() - t0) * 1000), "rc": r.returncode,
        "parsed": parsed is not None, "found": (parsed or {}).get("found"),
        "answer": (parsed or {}).get("answer"),
        "confidence": (parsed or {}).get("confidence"),
        "evidence": (parsed or {}).get("evidence", []),
        "exact": exact, "false_confident": false_conf,
        "tool_calls": len(calls), "workspace": str(ws),
        "stderr": r.stderr[-800:],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="*", default=["MiniMax-M3", "DeepSeek-Flash"])
    ap.add_argument("--tasks", type=Path, default=TASKS)
    ap.add_argument("--output", type=Path, default=Path("/tmp/blind_pilot.json"))
    args = ap.parse_args()
    data = json.loads(args.tasks.read_text())
    models = [m for m in base.MODELS if m["label"] in args.models]
    rows = [run_one(t, m) for t in data["tasks"] for m in models]
    for r in rows:
        print(json.dumps({k: r[k] for k in
                          ("task_id", "model", "exact", "false_confident",
                           "confidence", "duration_ms", "tool_calls")},
                         ensure_ascii=False))
    out = dict(data)
    out["results"] = rows
    args.output.write_text(json.dumps(out, ensure_ascii=False, indent=2))
    print("wrote", args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
