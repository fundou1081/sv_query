#!/usr/bin/env python3
"""[P85] Hard-isolated source/T2 pilot for signal-neighborhood tasks.

Two fixtures only: complex constraints and nested mux.  Each job gets its own
workspace; source is denied the repo/CLI, T2 is denied task/truth files.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import sys
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scoring import score_answer

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
MODELS = json.loads((HERE / "interactive_debug" / "models.json").read_text())["models"]
CREDS = Path.home() / ".dsh" / ".credentials.yaml"
FIXTURES = ROOT / "examples" / "interactive_debug"
PROFILES = HERE / "hard_isolated"
WORK = Path("/tmp/lr_neigh_hard")
SVQ = Path.home() / "miniconda3" / "bin" / "sv_query"

TASKS = [
    {
        "id": "complex_constraints",
        "fixture": "complex_constraints.sv",
        "question": "Extract the signal-graph neighborhood around top.e.p.len: all rand variables, each constraint block affecting len (block id, defined_in, inherited), condition variables (especially packet.mode), and the block coupling addr+len. Use exact ids.",
        "shape": {"property": "top.e.p.len", "rand_vars": [], "constraints": [],
                  "condition_vars": [], "both_addr_len_block": "", "inherited": []},
        "ground_truth": {
            "rand_vars": ["packet.addr", "packet.len", "packet.mode", "packet.payload"],
            "constraints": ["packet.c_len", "packet.c_mode", "packet.c_order"],
            "condition_vars": ["packet.mode"],
            "both_addr_len_block": "packet.c_order",
            "inherited": ["packet.c_len"],
        },
    },
    {
        "id": "mux_neighborhood",
        "fixture": "mux_neighborhood.sv",
        "question": "Extract the local signal-graph mux neighborhood around top.q: direct register/sink, all OP_TERNARY nodes, select signals, data sources a/b/c/d, and mux conditions. Use exact canonical ids.",
        "shape": {"seed": "top.q", "register": "top.q", "mux_nodes": [],
                  "selects": [], "data_sources": [], "conditions": []},
        "ground_truth": {
            "mux_nodes": ["top.u.lo.ternary_sel[0]", "top.u.hi.ternary_sel[0]",
                          "top.u.y.ternary_sel[1]"],
            "selects": ["top.u.sel[0]", "top.u.sel[1]"],
            "data_sources": ["top.u.a", "top.u.b", "top.u.c", "top.u.d"],
            "register": "top.q",
        },
    },
]

PROMPT = """SIGNAL-GRAPH NEIGHBORHOOD TASK. Work only in {ws}; read-only; no web.
Input: {input}
Question: {question}
{arm_hint}
Use at most {budget} tool commands. Do not read task JSON, ground truth or old artifacts.
Return compact JSON:
{{"task_id": "{task_id}", "answer": {shape}, "queries": ["commands actually run"],
 "confidence": "high|medium|low", "evidence": ["..."]}}
"""


def _env() -> dict:
    env = os.environ.copy()
    refs = yaml.safe_load(CREDS.read_text()).get("refs", {})
    for k in ("MINIMAX_CN_API_KEY", "DEEPSEEK_API_KEY"):
        if refs.get(k):
            env[k] = refs[k]
    env["DSH_PERMISSION_MODE"] = "danger-full-access"
    return env


def _extract_json(text: str) -> dict | None:
    # Prefer the complete envelope (task_id + answer); nested answer objects
    # must not be mistaken for the envelope.
    candidates: list[dict] = []
    for m in re.finditer(r"\{", text):
        depth = 0
        for i in range(m.start(), len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        d = json.loads(text[m.start():i + 1])
                        if isinstance(d, dict):
                            candidates.append(d)
                    except json.JSONDecodeError:
                        pass
                    break
    for d in reversed(candidates):
        if "task_id" in d and "answer" in d:
            return d
    return candidates[-1] if candidates else None

def _fact_check(task: dict, ws: Path) -> tuple[bool, dict]:
    f = ws / task["fixture"]
    env = _env()
    env["SVQ_CACHE_DIR"] = str(ws / ".cache")
    if task["id"] == "complex_constraints":
        r = subprocess.run(["sv_query", "trace", "constraints", "top.e.p.len",
                            "--file", str(f), "--json"], cwd=ws, env=env,
                           capture_output=True, text=True, timeout=180)
        if r.returncode != 0:
            return False, {"error": r.stderr[-500:]}
        items = json.loads(r.stdout)["result"]["constraints"]
        got = {"blocks": [x["block"] for x in items],
               "conditions": [c for x in items for c in x["conditions"]],
               "vars": [v for x in items for v in x["vars"]]}
        ok = ({"packet.c_len", "packet.c_mode", "packet.c_order"} <= set(got["blocks"])
              and "packet.mode" in got["conditions"])
        return ok, {"actual": got}
    r = subprocess.run(["sv_query", "graph", "subgraph", "top.q", "--depth", "5",
                        "--edge-kinds", "driver,connection,branch", "--file", str(f),
                        "--json"], cwd=ws, env=env, capture_output=True, text=True,
                       timeout=180)
    if r.returncode != 0:
        return False, {"error": r.stderr[-500:]}
    nodes = {n["id"] for n in json.loads(r.stdout)["result"]["nodes"]}
    want = {"top.u.lo.ternary_sel[0]", "top.u.hi.ternary_sel[0]",
            "top.u.y.ternary_sel[1]", "top.u.sel[0]", "top.u.sel[1]",
            "top.u.a", "top.u.b", "top.u.c", "top.u.d"}
    return want <= nodes, {"missing": sorted(want - nodes)}


def _run(task: dict, model: dict, arm: str, seed: int, budget: int) -> dict:
    ws = WORK / model["label"].replace(".", "_") / task["id"] / f"{arm}-s{seed}"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True)
    shutil.copy2(FIXTURES / task["fixture"], ws / task["fixture"])
    fc_ok, fc = _fact_check(task, ws)
    if not fc_ok:
        return {"task_id": task["id"], "model": model["label"], "arm": arm,
                "seed": seed, "rc": 0, "parsed": False, "fact_check_ok": False,
                "fact_check": fc, "answer": {}, "queries": [], "checks": {}}
    hint = ("SOURCE ONLY: read the RTL/class source; sv_query is unavailable."
            if arm == "source" else
            "T2: sv_query is available; use graph/class/controlflow queries.")
    prompt = PROMPT.format(ws=ws, input=ws / task["fixture"],
                           question=task["question"], arm_hint=hint,
                           budget=budget, task_id=task["id"],
                           shape=json.dumps(task["shape"], ensure_ascii=False))
    patch = ws / "model.patch.yml"
    shutil.copy2((HERE / "interactive_debug" / model["patch"]).resolve(), patch)
    profile = PROFILES / ("source.sb" if arm == "source" else "t2_long.sb")
    cmd = ["sandbox-exec", "-D", f"REPO={ROOT}", "-D", f"PILOT=/tmp/lr_pilot",
           "-D", f"SVQ={SVQ}", "-D", f"TASKS={ROOT / 'tools' / 'benchmark'}",
           "-D", f"TRUTH={ROOT / 'docs' / 'validation'}", "-f", str(profile),
           "dsh", "--profile", "headless", "--patch", str(patch), prompt]
    env = _env()
    env["SVQ_CACHE_DIR"] = str(ws / ".cache")
    t0 = time.time()
    text = err = ""
    rc = 1
    for attempt in range(3):
        try:
            r = subprocess.run(cmd, cwd=ws, env=env, capture_output=True,
                               text=True, timeout=900)
            text, err, rc = r.stdout, r.stderr[-1500:], r.returncode
        except subprocess.TimeoutExpired as e:
            text = (e.stdout or "")
            if isinstance(text, bytes):
                text = text.decode(errors="replace")
            err, rc = "TIMEOUT", 124
            break
        if rc == 0 or "RATE_LIMIT" not in err:
            break
        time.sleep(60 * (attempt + 1))
    parsed = _extract_json(text)
    score = score_answer(task, (parsed or {}).get("answer", {}))
    (ws / "raw.txt").write_text(text)
    return {"task_id": task["id"], "model": model["label"], "arm": arm,
            "seed": seed, "duration_ms": int((time.time() - t0) * 1000),
            "rc": rc, "parsed": parsed is not None, "fact_check_ok": True,
            "fact_check": fc, "answer": (parsed or {}).get("answer", {}),
            "queries": (parsed or {}).get("queries", []),
            "confidence": (parsed or {}).get("confidence"),
            "canonical": score["canonical"],
            "checks": {"parsed": parsed is not None,
                       "checks": score["canonical_checks"]},
            "semantic": {"parsed": parsed is not None,
                         "checks": score["semantic_checks"]},
            "semantic_ok": score["semantic"],
            "stderr": err, "workspace": str(ws)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--models", nargs="*", default=None)
    ap.add_argument("--arms", nargs="*", default=["source", "t2"])
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--budget", type=int, default=8)
    ap.add_argument("--output", type=Path, default=Path("/tmp/neighborhood_results.json"))
    args = ap.parse_args()
    models = MODELS if not args.models else [m for m in MODELS if m["label"] in args.models]
    jobs = [(t, m, a) for t in TASKS for m in models for a in args.arms]
    rows = []
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as ex:
        futs = {ex.submit(_run, t, m, a, args.seed, args.budget): (t, m, a)
                for t, m, a in jobs}
        for f in as_completed(futs):
            row = f.result()
            rows.append(row)
            print(json.dumps({k: row.get(k) for k in
                              ("task_id", "model", "arm", "seed", "rc", "parsed",
                               "checks", "fact_check_ok")}, ensure_ascii=False))
    rows.sort(key=lambda r: (r["task_id"], r["model"], r["arm"]))
    args.output.write_text(json.dumps({"protocol": "P85 neighborhood source/T2",
                                       "tasks": TASKS, "results": rows},
                                      ensure_ascii=False, indent=2))
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
