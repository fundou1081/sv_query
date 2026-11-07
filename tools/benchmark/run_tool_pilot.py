#!/usr/bin/env python3
"""[P98] 3-cell pilot for the constrained svq_query tool (no bash/fs)."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

import run_long_range as base
from scoring import score_answer

ROOT = base.ROOT
TOOL_PATCH = ROOT / "tools" / "agent" / "svq_query.patch.yml"
WORK = Path("/tmp/svq_tool_pilot")
SNAPS = Path("/tmp/lr_ad_snaps")
TAG = {"axi": "ad_axi", "serv": "ad_serv", "pico": "ad_pico"}


def _prompt(task: dict, tag: str) -> str:
    q = task["query"]
    if q["cmd"] == "path":
        intent = "path"
        ask = "path (src -> dst)"
        shape = '{"path":["ids"],"count":hop_count}'
    elif task["id"] == "axi_araddr_neighbors":
        intent = "neighbors"
        ask = "neighbors (drivers + loads)"
        shape = '{"drivers":["ids"],"loads":["ids"],"count":integer}'
    elif q["cmd"] == "fanin":
        intent = "fanin"
        ask = "fanin (drivers)"
        shape = '{"drivers":["ids"],"count":integer}'
    else:
        intent = "fanout"
        ask = "fanout (loads)"
        shape = '{"loads":["ids"],"count":integer}'
    signal = q.get("signal") or q.get("src")
    dst = q.get("dst")
    extra = f", dst {dst!r}" if dst else ""
    return (
        "Use only svq_query; bash/read/grep are unavailable. "
        f"Call svq_query with intent={intent}, snapshot={tag!r}, "
        f"signal={signal!r}{extra}, depth=1 where applicable. "
        "Then return ONE valid JSON object, no markdown, no explanation, "
        "with double-quoted keys:\n"
        f'{{"task_id":{task["id"]!r},"answer":{shape},'
        '"queries":[{"tool":"svq_query"}],"confidence":"high"}'
        " Copy IDs from the tool result exactly."
    )


def run_one(task: dict, model: dict) -> dict:
    design = base._design(task["id"])
    tag = TAG[design]
    ws = WORK / model["label"].replace(".", "_") / task["id"]
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True)
    env = base._env()
    env["SVQ_SNAPSHOT_DIR"] = str(SNAPS)
    patch = (base.INTERACTIVE / model["patch"]).resolve()
    cmd = ["dsh", "--profile", "headless", "--patch", str(patch),
           "--patch", str(TOOL_PATCH), _prompt(task, tag)]
    t0 = time.time()
    r = subprocess.run(cmd, cwd=ws, env=env, capture_output=True, text=True,
                       timeout=300)
    (ws / "raw.txt").write_text(r.stdout)
    parsed = base._extract_json(r.stdout)
    ans = (parsed or {}).get("answer", parsed or {})
    sc = score_answer(task, ans)
    return {"task_id": task["id"], "model": model["label"], "arm": "tool",
            "duration_ms": int((time.time() - t0) * 1000),
            "rc": r.returncode, "parsed": parsed is not None,
            "answer": ans, "queries": (parsed or {}).get("queries", []),
            "exact": sc["canonical"], "workspace": str(ws),
            "stderr": r.stderr[-1000:]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", nargs="*", default=[
        "axi_araddr_neighbors", "serv_clk_path", "pico_adapter_mem_valid_fanout"])
    ap.add_argument("--models", nargs="*", default=["MiniMax-M3", "DeepSeek-Flash"])
    ap.add_argument("--output", type=Path, default=Path("/tmp/tool_pilot.json"))
    args = ap.parse_args()
    if not SNAPS.is_dir():
        raise SystemExit(f"missing snapshots: {SNAPS}")
    all_tasks = json.loads(base.TASKS.read_text())["tasks"]
    tasks = [t for t in all_tasks if t["id"] in args.tasks]
    models = [m for m in base.MODELS if m["label"] in args.models]
    rows = [run_one(t, m) for t in tasks for m in models]
    for r in rows:
        print(json.dumps({k: r.get(k) for k in
                          ("task_id", "model", "rc", "parsed", "exact",
                           "duration_ms")}, ensure_ascii=False))
    args.output.write_text(json.dumps({"protocol": "P98 constrained svq_query",
                                       "tasks": tasks, "results": rows},
                                      ensure_ascii=False, indent=2))
    print("wrote", args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
