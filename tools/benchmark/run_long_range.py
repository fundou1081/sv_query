#!/usr/bin/env python3
"""[P81] Repeatable long-range benchmark runner with hard isolation.

Runs the 12 frozen tasks from long_range_tasks.json for source/T2 arms.
The workspace contains only design sources and a local filelist; task JSON,
ground truth, old /tmp/lr_pilot artifacts and the sv_query repo are denied.
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

import yaml

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
TASKS = HERE / "long_range_tasks.json"
INTERACTIVE = HERE / "interactive_debug"
MODELS = json.loads((INTERACTIVE / "models.json").read_text())["models"]
CREDS = Path.home() / ".dsh" / ".credentials.yaml"
PILOT = Path("/tmp/lr_pilot")
WORK = Path("/tmp/lr_long_hard")
PROFILES = HERE / "hard_isolated"
SVQ = Path.home() / "miniconda3" / "bin" / "sv_query"

PROMPT = """REAL RTL DEBUG TASK. Work only in {ws}; read-only; no web.
Input: {input}
Question: {question}
The answer must use exact canonical node IDs / paths / counts.
Use at most {budget} tool commands; do not read task JSON, ground truth or old pilot artifacts.
{arm_hint}
Return compact JSON:
{{"task_id": "{task_id}", "answer": {{"drivers": [], "loads": [], "path": [], "count": 0}},
 "queries": ["exact commands you actually ran"], "confidence": "high|medium|low",
 "evidence": ["..."]}}
Only include the fields required by the question.
"""

SOURCE_HINT = ("For source-only work, a direct edge means one graph hop; "
               "do not report terminal/transitive uses as direct.")
T2_HINT = ("T2: for every direct (distance=1) fanin/fanout question you MUST use "
           "`sv_query ... --depth 1`; record the exact commands in `queries`.")


def _env() -> dict:
    env = os.environ.copy()
    refs = yaml.safe_load(CREDS.read_text()).get("refs", {})
    for k in ("MINIMAX_CN_API_KEY", "DEEPSEEK_API_KEY"):
        if refs.get(k):
            env[k] = refs[k]
    env["DSH_PERMISSION_MODE"] = "danger-full-access"
    return env


def _design(task_id: str) -> str:
    if task_id.startswith("axi_"):
        return "axi"
    if task_id.startswith("serv_"):
        return "serv"
    return "pico"


def _copy_design(design: str, ws: Path) -> Path:
    """Copy only source + local filelist; never copy task/ground-truth files."""
    dst = ws / design
    dst.mkdir(parents=True, exist_ok=True)
    if design in ("axi", "serv"):
        src = PILOT / design
        if not src.is_dir():
            openrtl = Path(os.environ.get("SVQ_OPENRTL_ROOT",
                                          Path.home() / "my_dv_proj" / "openrtl"))
            src = openrtl / ("verilog-axi/rtl" if design == "axi" else "serv")
        files = sorted(src.rglob("*.v"))
        if not files:
            raise FileNotFoundError(f"no .v sources for {design}: {src}")
        for f in files:
            shutil.copy2(f, dst / f.name)
        local = sorted(dst.glob("*.v"))
        fl = ws / f"{design}.f"
        fl.write_text("\n".join(str(p) for p in local) + "\n")
        return fl
    src = PILOT / "pico" / "picorv32.v"
    if not src.exists():
        openrtl = Path(os.environ.get("SVQ_OPENRTL_ROOT",
                                      Path.home() / "my_dv_proj" / "openrtl"))
        src = openrtl / "picorv32" / "picorv32.v"
    out = ws / "picorv32.v"
    shutil.copy2(src, out)
    return out


def _extract_json(text: str) -> dict | None:
    decoder = json.JSONDecoder()
    candidates: list[dict] = []
    for m in re.finditer(r"\{", text):
        try:
            d, _ = decoder.raw_decode(text[m.start():])
        except json.JSONDecodeError:
            continue
        if isinstance(d, dict):
            candidates.append(d)
    for d in reversed(candidates):
        if "task_id" in d and "answer" in d:
            return d
    return candidates[-1] if candidates else None

def _query_spec(task: dict, input_path: Path) -> list[list[str]]:
    """Deterministic CLI fact-check commands from the frozen task query."""
    q = task["query"]
    inp = ["--filelist" if input_path.suffix in (".f", ".fl") else "--file",
           str(input_path)]
    if q["cmd"] == "fanin":
        cmds = [["sv_query", "drivers", q["signal"], "--depth", "1", *inp, "--json"]]
        if q.get("also_loads"):
            cmds.append(["sv_query", "loads", q["signal"], "--depth", "1", *inp, "--json"])
        return cmds
    if q["cmd"] == "fanout":
        return [["sv_query", "loads", q["signal"], "--depth", "1", *inp, "--json"]]
    return [["sv_query", "paths", q["src"], q["dst"], "--directed", *inp, "--json"]]


def _fact_check(task: dict, input_path: Path, ws: Path) -> tuple[bool, dict]:
    """Verify frozen ground truth against current graph before agents run."""
    got: dict = {}
    env = _env()
    env["SVQ_CACHE_DIR"] = str(ws / ".cache")
    for cmd in _query_spec(task, input_path):
        r = subprocess.run(cmd, cwd=ws, env=env, capture_output=True,
                           text=True, timeout=180)
        if r.returncode != 0:
            return False, {"error": r.stderr[-500:], **got}
        data = json.loads(r.stdout)
        res = data.get("result") or data
        sig = (res.get("signals") or [{}])[0]
        if "drivers" in cmd:
            got["drivers"] = [d["id"] for d in sig.get("drivers", [])]
        if "loads" in cmd:
            got["loads"] = [d["id"] for d in sig.get("loads", [])]
        if "paths" in cmd:
            got["path"] = res.get("path")
            got["count"] = res.get("hop_count")
    if "drivers" in got:
        got["count"] = len(got["drivers"])
    elif "loads" in got:
        got["count"] = len(got["loads"])
    truth = task["ground_truth"]
    ok = all(got.get(k) == v for k, v in truth.items())
    return ok, {"actual": got, "expected": truth}


def _needs_depth(task: dict) -> bool:
    return task["query"]["cmd"] in ("fanin", "fanout")


def _run(task: dict, model: dict, arm: str, seed: int, budget: int) -> dict:
    ws = WORK / model["label"].replace(".", "_") / task["id"] / f"{arm}-s{seed}"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True)
    input_path = _copy_design(_design(task["id"]), ws)
    fc_ok, fc = _fact_check(task, input_path, ws)
    if not fc_ok:
        return {"task_id": task["id"], "model": model["label"], "arm": arm,
                "seed": seed, "duration_ms": 0, "rc": 0, "parsed": False,
                "fact_check_ok": False, "fact_check": fc,
                "answer": {}, "queries": [], "depth1_ok": False,
                "stderr": "GROUND_TRUTH_MISMATCH", "workspace": str(ws)}
    arm_hint = T2_HINT if arm == "t2" else SOURCE_HINT
    prompt = PROMPT.format(ws=ws, input=input_path, question=task["question"],
                           budget=budget, task_id=task["id"], arm_hint=arm_hint)
    profile = PROFILES / ("source.sb" if arm == "source" else "t2_long.sb")
    # The repo is denied inside both sandboxes; stage the model overlay in ws.
    patch = ws / "model.patch.yml"
    shutil.copy2((INTERACTIVE / model["patch"]).resolve(), patch)
    cmd = ["sandbox-exec",
           "-D", f"REPO={ROOT}", "-D", f"PILOT={PILOT}", "-D", f"SVQ={SVQ}",
           "-D", f"TASKS={HERE}", "-D", f"TRUTH={ROOT / 'docs' / 'validation'}",
           "-f", str(profile),
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
            text, err, rc = r.stdout, r.stderr[-2000:], r.returncode
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
    ans = (parsed or {}).get("answer", parsed or {})
    queries = (parsed or {}).get("queries") or []
    depth1_ok = (not (arm == "t2" and _needs_depth(task))) or any(
        "--depth 1" in str(q) or "--depth=1" in str(q) for q in queries)
    raw = WORK / model["label"].replace(".", "_") / task["id"] / f"{arm}-s{seed}.txt"
    raw.write_text(text)
    return {
        "task_id": task["id"], "model": model["label"], "arm": arm, "seed": seed,
        "duration_ms": int((time.time() - t0) * 1000), "rc": rc,
        "confidence": (parsed or {}).get("confidence"),
        "answer": ans, "queries": queries, "depth1_ok": depth1_ok,
        "fact_check_ok": True, "fact_check": fc,
        "parsed": parsed is not None, "stderr": err, "workspace": str(ws),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", nargs="*", default=None)
    ap.add_argument("--models", nargs="*", default=None)
    ap.add_argument("--arms", nargs="*", default=["source", "t2"])
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--budget", type=int, default=8)
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--output", type=Path, default=Path("/tmp/long_range_runner.json"))
    args = ap.parse_args()
    tasks = json.loads(TASKS.read_text())["tasks"]
    if args.tasks:
        tasks = [t for t in tasks if t["id"] in args.tasks]
    models = MODELS if not args.models else [m for m in MODELS if m["label"] in args.models]
    jobs = [(t, m, a) for t in tasks for m in models for a in args.arms]
    rows = []
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as ex:
        futs = {ex.submit(_run, t, m, a, args.seed, args.budget): (t, m, a)
                for t, m, a in jobs}
        for f in as_completed(futs):
            row = f.result()
            rows.append(row)
            print(json.dumps({k: row[k] for k in ("task_id", "model", "arm", "seed",
                                                   "rc", "parsed", "duration_ms")},
                             ensure_ascii=False))
    rows.sort(key=lambda r: (r["task_id"], r["model"], r["arm"]))
    payload = {"protocol": "P81 hard-isolated long-range runner",
               "tasks": tasks, "results": rows}
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
