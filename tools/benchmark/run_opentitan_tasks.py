#!/usr/bin/env python3
"""[P118] Run the frozen OpenTitan UART tasks through constrained svq_query."""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import time
from pathlib import Path

import run_long_range as base
from answer_json import parse_answer_json
from session_telemetry import extract

ROOT = base.ROOT
TOOL_PATCH = ROOT / "tools" / "agent" / "svq_query.patch.yml"
TASKS = ROOT / "tools" / "benchmark" / "opentitan_uart_tasks_2026-11-09.json"
WORK = Path("/tmp/opentitan_agent")


def prompt(meta: dict, task: dict) -> str:
    return (
        "Use only svq_query. bash/read/grep are unavailable. "
        f"Snapshot: {meta['snapshot']!r}. "
        f"{task['question']} "
        "Return ONE valid JSON object, no markdown: "
        f'{{"task_id":{task["id"]!r},"found":true,"answer":{{}},"confidence":"high|medium|low","evidence":[]}}. '
        "Use canonical IDs from tool results; do not invent IDs."
    )


def score(task: dict, parsed: dict | None) -> tuple[bool, bool, bool]:
    if not parsed:
        return False, False, False
    exp = task["expected"]
    ans = parsed.get("answer") if isinstance(parsed.get("answer"), dict) else {}
    kind = task["kind"]
    if kind == "t1":
        ok = (
            ans.get("primary_signal") == exp["primary_signal"]
            and sorted(ans.get("primary_drivers", [])) == sorted(exp["primary_drivers"])
            and sorted(ans.get("primary_loads", [])) == sorted(exp["primary_loads"])
            and ans.get("empty_side_signal") == exp["empty_side_signal"]
            and sorted(ans.get("empty_side_drivers", [])) == sorted(exp["empty_side_drivers"])
            and sorted(ans.get("empty_side_loads", [])) == sorted(exp["empty_side_loads"])
        )
    elif kind == "t2":
        ok = (ans.get("path") == exp["path"] and ans.get("hop_count") == exp["hop_count"])
    elif kind == "t3":
        ok = (str(ans.get("file", "")).endswith(exp["file"])
              and ans.get("line") == exp["line"]
              and exp["source_contains"] in str(ans.get("source_line", "")))
    elif kind == "t4":
        ok = all(ans.get(k) == v for k, v in exp.items())
    elif kind == "t5":
        ok = (ans.get("missing_signal_status") == exp["missing_signal_status"]
              and ans.get("no_path_status") == exp["no_path_status"])
    else:
        ok = False
    false_conf = (not ok and parsed.get("confidence") == "high")
    false_found = (not exp.get("found", True) and parsed.get("found") is True)
    return ok, false_conf, false_found


def run_one(meta: dict, task: dict, model: dict) -> dict:
    ws = WORK / model["label"].replace(".", "_") / task["id"]
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True)
    env = base._env()
    env["SVQ_SNAPSHOT_DIR"] = meta["snapshot_dir"]
    env["SVQ_SOURCE_ROOT"] = meta["source_root"]
    patch = (base.INTERACTIVE / model["patch"]).resolve()
    cmd = ["dsh", "--profile", "headless", "--patch", str(patch),
           "--patch", str(TOOL_PATCH), prompt(meta, task)]
    t0 = time.time()
    timeout = getattr(run_one, "timeout", 600)
    timed_out = False
    try:
        r = subprocess.run(cmd, cwd=ws, env=env, capture_output=True, text=True,
                           timeout=timeout)
        stdout, stderr, rc = r.stdout, r.stderr, r.returncode
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        stdout = exc.stdout if isinstance(exc.stdout, str) else (exc.stdout or b"").decode("utf-8", "replace")
        stderr = f"timeout after {timeout}s"
        rc = 124
    (ws / "raw.txt").write_text(stdout or "")
    parsed, repaired = parse_answer_json(stdout or "")
    exact, false_conf, false_found = score(task, parsed)
    try:
        calls = extract(ws).get("tool_detail", [])
    except Exception:
        calls = []
    return {
        "task_id": task["id"], "model": model["label"], "kind": task["kind"],
        "duration_ms": int((time.time() - t0) * 1000), "rc": rc,
        "timeout": timed_out,
        "parsed": parsed is not None, "json_repaired": repaired,
        "found": (parsed or {}).get("found"),
        "answer": (parsed or {}).get("answer"),
        "confidence": (parsed or {}).get("confidence"),
        "evidence": (parsed or {}).get("evidence", []),
        "exact": exact, "false_confident": false_conf, "false_found": false_found,
        "tool_calls": len(calls), "workspace": str(ws),
        "stderr": stderr[-800:],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="*", default=["MiniMax-M3", "DeepSeek-Flash"])
    ap.add_argument("--tasks", type=Path, default=TASKS)
    ap.add_argument("--only", nargs="*", default=None)
    ap.add_argument("--timeout", type=int, default=600,
                    help="per-cell DSH timeout in seconds")
    ap.add_argument("--output", type=Path, default=Path("/tmp/opentitan_agent.json"))
    args = ap.parse_args()
    data = json.loads(args.tasks.read_text())
    meta = {k: data[k] for k in ("snapshot", "snapshot_dir", "source_root")}
    models = [m for m in base.MODELS if m["label"] in args.models]
    run_one.timeout = args.timeout
    tasks = [t for t in data["tasks"] if not args.only or t["id"] in args.only]
    rows = []
    for task in tasks:
        for model in models:
            try:
                rows.append(run_one(meta, task, model))
            except Exception as exc:
                rows.append({"task_id": task["id"], "model": model["label"],
                             "kind": task["kind"], "exact": False,
                             "false_confident": False, "false_found": False,
                             "timeout": False, "parsed": False,
                             "rc": 1, "error": str(exc), "workspace": None})
    for r in rows:
        print(json.dumps({k: r[k] for k in
                          ("task_id", "model", "exact", "false_confident",
                           "false_found", "timeout", "confidence", "duration_ms",
                           "tool_calls", "json_repaired")}, ensure_ascii=False))
    out = dict(data); out["results"] = rows
    args.output.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n")
    print("wrote", args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
