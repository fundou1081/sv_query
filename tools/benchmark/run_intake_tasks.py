#!/usr/bin/env python3
"""P125: run the three independent OpenTitan DV intake tasks."""
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
TASKS = ROOT / "tools" / "benchmark" / "opentitan_intake_tasks_2026-11-09.json"
WORK = Path("/tmp/opentitan_intake_agent")


def answer_shape(kind: str) -> str:
    if kind == "discovery":
        return ('{"register_bit":"CTRL.NF","canonical_signal_id":"...",'
                '"intermediate_signal_id":"...","mux_output_signal_id":"...",'
                '"hop_count":0}')
    if kind == "verify":
        return ('{"nack":"verified|contradicted|unknown",'
                '"unhandled_nack_timeout":"...","bus_timeout":"...",'
                '"arbitration_lost":"...","tx_pending":"..."}')
    return '{"path":["ids"],"hop_count":0,"bypasses_input_synchronizer":true}'


def prompt(task: dict) -> str:
    return (
        "Use only svq_query. bash/read/grep are unavailable. "
        f"Snapshot: {task['snapshot']!r}. {task['question']} "
        "Return ONE valid JSON object, no markdown, with "
        f'{{"task_id":{task["id"]!r},"found":true,"answer":{answer_shape(task["kind"])},'
        '"confidence":"high|medium|low","evidence":[]}. '
        "Use canonical IDs from tool results; do not invent IDs. "
        "For verify, preserve unknown when the node is absent."
    )


def score(task: dict, parsed: dict | None) -> tuple[bool, bool, bool]:
    if not parsed:
        return False, False, False
    exp = task["expected"]
    ans = parsed.get("answer") if isinstance(parsed.get("answer"), dict) else {}
    kind = task["kind"]
    if kind == "discovery":
        ok = (ans.get("canonical_signal_id") == exp["canonical_signal_id"]
              and ans.get("intermediate_signal_id") == exp["intermediate_signal_id"]
              and ans.get("mux_output_signal_id") == exp["mux_output_signal_id"]
              and ans.get("hop_count") == exp["hop_count"])
    elif kind == "verify":
        ok = all(ans.get(k) == v for k, v in exp.items())
    else:
        ok = (ans.get("path") == exp["path"]
              and ans.get("hop_count") == exp["hop_count"]
              and ans.get("bypasses_input_synchronizer") is exp["bypasses_input_synchronizer"])
    false_conf = (not ok and parsed.get("confidence") == "high")
    false_found = (parsed.get("found") is False)
    return ok, false_conf, false_found


def run_one(meta: dict, task: dict, model: dict, timeout: int) -> dict:
    ws = WORK / model["label"].replace(".", "_") / task["id"]
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True)
    env = base._env()
    env["SVQ_SNAPSHOT_DIR"] = task["snapshot_dir"]
    env["SVQ_SOURCE_ROOT"] = meta["source_root"]
    patch = (base.INTERACTIVE / model["patch"]).resolve()
    cmd = ["dsh", "--profile", "headless", "--patch", str(patch),
           "--patch", str(TOOL_PATCH), prompt(task)]
    t0 = time.time()
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
    except Exception as exc:  # [P158.12 / R-027] task 异常必须留行计数, 不得让整轮跑挂
        task_error = str(exc)
        stdout, stderr, rc = "", task_error[:500], 130
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
        "timeout": timed_out, "parsed": parsed is not None,
        "json_repaired": repaired, "found": (parsed or {}).get("found"),
        "answer": (parsed or {}).get("answer"),
        "confidence": (parsed or {}).get("confidence"),
        "exact": exact, "false_confident": false_conf, "false_found": false_found,
        "tool_calls": len(calls), "workspace": str(ws), "stderr": stderr[-500:], "task_error": rc == 130,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="*", default=["MiniMax-M3", "DeepSeek-Flash"])
    ap.add_argument("--timeout", type=int, default=600)
    ap.add_argument("--output", type=Path, default=Path("/tmp/opentitan_intake_agent.json"))
    args = ap.parse_args()
    data = json.loads(TASKS.read_text())
    meta = {"source_root": data["source_root"]}
    models = [m for m in base.MODELS if m["label"] in args.models]
    rows = [run_one(meta, t, m, args.timeout) for t in data["tasks"] for m in models]
    for r in rows:
        print(json.dumps({k: r[k] for k in ("task_id", "model", "exact",
                          "false_confident", "false_found", "timeout",
                          "confidence", "duration_ms", "tool_calls")},
                         ensure_ascii=False))
    out = dict(data); out["results"] = rows
    args.output.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n")
    print("wrote", args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
