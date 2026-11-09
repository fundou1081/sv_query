#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, shutil, subprocess, time
from pathlib import Path
import run_long_range as base
from answer_json import parse_answer_json
from session_telemetry import extract

ROOT = base.ROOT
PATCH = ROOT / "tools/agent/svq_query.patch.yml"
TASKS = ROOT / "tools/benchmark/opentitan_p127_tasks_2026-11-09.json"
WORK = Path("/tmp/opentitan_p127_agent")

def shape(kind):
    if kind == "discovery":
        return ('{"enable_signal_id":"...","value_signal_id":"...",'
                '"flop_signal_id":"...","tx_pin_signal_id":"...",'
                '"priority_order":["reset","override","system_loopback","transmitter"],'
                '"path":["ids"],"hop_count":0}')
    return '{"path":["ids"],"hop_count":0}'

def prompt(task):
    return ("Use only svq_query. bash/read/grep are unavailable. "
            f"Snapshot: {task['snapshot']!r}. {task['question']} "
            "Return ONE valid JSON object, no markdown: "
            f'{{"task_id":{task["id"]!r},"found":true,"answer":{shape(task["kind"])},'
            '"confidence":"high|medium|low","evidence":[]}. '
            "Use canonical IDs from tool results; do not invent IDs.")

def score(task, parsed):
    if not parsed:
        return False, False, False
    exp = task["expected"]; ans = parsed.get("answer") if isinstance(parsed.get("answer"), dict) else {}
    if task["kind"] == "discovery":
        ok = (ans.get("enable_signal_id") == exp["enable_signal_id"]
              and ans.get("value_signal_id") == exp["value_signal_id"]
              and ans.get("flop_signal_id") == exp["flop_signal_id"]
              and ans.get("tx_pin_signal_id") == exp["tx_pin_signal_id"]
              and ans.get("priority_order") == exp["priority_order"]
              and ans.get("path") == exp["path"]
              and ans.get("hop_count") == exp["hop_count"])
    else:
        ok = ans.get("path") == exp["path"] and ans.get("hop_count") == exp["hop_count"]
    return ok, (not ok and parsed.get("confidence") == "high"), parsed.get("found") is False

def run(meta, task, model, timeout):
    ws = WORK / model["label"].replace(".", "_") / task["id"]
    if ws.exists(): shutil.rmtree(ws)
    ws.mkdir(parents=True)
    env = base._env(); env["SVQ_SNAPSHOT_DIR"] = task["snapshot_dir"]; env["SVQ_SOURCE_ROOT"] = meta["source_root"]
    patch = (base.INTERACTIVE / model["patch"]).resolve()
    cmd = ["dsh", "--profile", "headless", "--patch", str(patch), "--patch", str(PATCH), prompt(task)]
    t0 = time.time(); timed = False
    try:
        r = subprocess.run(cmd, cwd=ws, env=env, capture_output=True, text=True, timeout=timeout)
        out, err, rc = r.stdout, r.stderr, r.returncode
    except subprocess.TimeoutExpired as e:
        timed = True
        out = e.stdout if isinstance(e.stdout, str) else (e.stdout or b"").decode("utf-8", "replace")
        err, rc = f"timeout {timeout}s", 124
    (ws / "raw.txt").write_text(out or "")
    parsed, repaired = parse_answer_json(out or "")
    exact, fc, ff = score(task, parsed)
    try: calls = extract(ws).get("tool_detail", [])
    except Exception: calls = []
    return {"task_id":task["id"],"model":model["label"],"kind":task["kind"],
            "duration_ms":int((time.time()-t0)*1000),"rc":rc,"timeout":timed,
            "parsed":parsed is not None,"json_repaired":repaired,
            "found":(parsed or {}).get("found"),"answer":(parsed or {}).get("answer"),
            "confidence":(parsed or {}).get("confidence"),"exact":exact,
            "false_confident":fc,"false_found":ff,"tool_calls":len(calls),
            "workspace":str(ws),"stderr":err[-500:]}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="*", default=["MiniMax-M3","DeepSeek-Flash"])
    ap.add_argument("--timeout", type=int, default=600)
    ap.add_argument("--only", nargs="*", default=None)
    ap.add_argument("--output", type=Path, default=Path("/tmp/opentitan_p127_agent.json"))
    args = ap.parse_args()
    d = json.loads(TASKS.read_text()); meta={"source_root":d["source_root"]}
    models=[m for m in base.MODELS if m["label"] in args.models]
    tasks=[t for t in d["tasks"] if not args.only or t["id"] in args.only]
    rows=[run(meta,t,m,args.timeout) for t in tasks for m in models]
    for r in rows:
        print(json.dumps({k:r[k] for k in ("task_id","model","exact","false_confident","false_found","timeout","confidence","duration_ms","tool_calls")},ensure_ascii=False))
    out=dict(d); out["results"]=rows; args.output.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
    print("wrote",args.output); return 0
if __name__ == "__main__": raise SystemExit(main())
