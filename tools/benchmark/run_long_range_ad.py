#!/usr/bin/env python3
"""[P94] 12-task source/T2 run with A (pruned filelist) + D (snapshot).

Only the T2 arm is rerun here: source has no CLI, so A/D cannot change it.
Original source/T2 baseline is the P87 fixed-protocol run. Snapshots are built
once per design from a pruned filelist (AXI/SERV) or the single Pico file, then
agents query them with --from-snapshot (no parse/build).
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import run_long_range as base
from scoring import score_answer

HERE = Path(__file__).resolve().parent
AD_WORK = Path("/tmp/lr_ad_prep")
AD_SNAPS = Path("/tmp/lr_ad_snaps")
AD_SNAP_ENV = "SVQ_SNAPSHOT_DIR"
TAG = {"axi": "ad_axi", "serv": "ad_serv", "pico": "ad_pico"}
SKILL = base.ROOT / ".dsh" / "skills" / "svq-query-protocol"
TOP = {"axi": "axi_adapter", "serv": "serv_rf_top"}


def _run(cmd: list[str], cwd: Path, env: dict, timeout: int = 300) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True,
                          timeout=timeout)


def _prepare() -> dict:
    AD_WORK.mkdir(parents=True, exist_ok=True)
    AD_SNAPS.mkdir(parents=True, exist_ok=True)
    env = base._env()
    env[AD_SNAP_ENV] = str(AD_SNAPS)
    env["SVQ_CACHE_DIR"] = str(AD_WORK / ".cache")
    out = {}
    for design in ("axi", "serv", "pico"):
        ws = AD_WORK / design
        if ws.exists():
            shutil.rmtree(ws)
        ws.mkdir(parents=True)
        inp = base._copy_design(design, ws)
        if design == "pico":
            picof = ws / "pico.f"
            picof.write_text(str(inp) + "\n")
            inp = picof
        t0 = time.perf_counter()
        if design in TOP:
            pruned = ws / f"{design}_pruned.f"
            r = _run(["sv_query", "filelist", "prune", "--filelist", str(inp),
                      "--top", TOP[design], "--output", str(pruned), "--json"],
                     ws, env)
            if r.returncode != 0:
                raise RuntimeError(f"prune failed for {design}: {r.stderr[-500:]}")
            inp = pruned
        save_cmd = ["sv_query", "snapshot", "save", str(inp), "--filelist", str(inp),
                    "--tag", TAG[design], "--json"]
        r = _run(save_cmd, ws, env)
        if r.returncode != 0:
            raise RuntimeError(f"snapshot save failed for {design}: {r.stderr[-500:]}")
        snap = json.loads(r.stdout)
        out[design] = {"input": str(inp), "tag": TAG[design],
                       "files": snap.get("files"),
                       "nodes": snap.get("node_count"),
                       "sec": round(time.perf_counter() - t0, 2)}
        print(json.dumps({"prepared": design, **out[design]}, ensure_ascii=False))
    out["snapshot_dir"] = str(AD_SNAPS)
    return out


def _check_snapshots() -> list[dict]:
    env = base._env()
    env[AD_SNAP_ENV] = str(AD_SNAPS)
    env["SVQ_CACHE_DIR"] = str(AD_WORK / ".cache")
    tasks = json.loads(base.TASKS.read_text())["tasks"]
    rows = []
    for t in tasks:
        design = base._design(t["id"])
        q = t["query"]
        if q["cmd"] == "fanin":
            cmds = [["sv_query", "drivers", q["signal"], "--depth", "1",
                     "--from-snapshot", TAG[design], "--json"]]
            if q.get("also_loads"):
                cmds.append(["sv_query", "loads", q["signal"], "--depth", "1",
                             "--from-snapshot", TAG[design], "--json"])
        elif q["cmd"] == "fanout":
            cmds = [["sv_query", "loads", q["signal"], "--depth", "1",
                     "--from-snapshot", TAG[design], "--json"]]
        else:
            cmds = [["sv_query", "paths", q["src"], q["dst"], "--directed",
                     "--from-snapshot", TAG[design], "--json"]]
        got = {}
        for cmd in cmds:
            r = _run(cmd, AD_WORK / design, env)
            if r.returncode != 0:
                raise RuntimeError(f"snapshot check failed {t['id']}: {r.stderr[-400:]}")
            data = json.loads(r.stdout)
            res = data.get("result") or data
            if "signals" in res:
                sig = res["signals"][0]
                if "drivers" in cmd:
                    got["drivers"] = [d["id"] for d in sig.get("drivers", [])]
                if "loads" in cmd:
                    got["loads"] = [d["id"] for d in sig.get("loads", [])]
            else:
                got["path"] = res.get("path")
                got["count"] = res.get("hop_count")
        if "drivers" in got:
            got["count"] = len(got["drivers"])
        elif "loads" in got:
            got["count"] = len(got["loads"])
        truth = t["ground_truth"]
        ok = all(got.get(k) == v for k, v in truth.items())
        rows.append({"task": t["id"], "ok": ok, "actual": got, "expected": truth})
        if not ok:
            raise RuntimeError(f"snapshot ground truth mismatch: {t['id']}")
    return rows


def _ad_run(task: dict, model: dict, seed: int, budget: int, mode: str) -> dict:
    design = base._design(task["id"])
    tag = TAG[design]
    ws = base.WORK / model["label"].replace(".", "_") / task["id"] / f"t2ad-{mode}-s{seed}"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True)
    input_path = base._copy_design(design, ws)
    fc_ok, fc = base._fact_check(task, input_path, ws)
    # The fact check intentionally warms the private AST cache; remove it before
    # the agent starts so it cannot bypass the snapshot interface by reading it.
    shutil.rmtree(ws / ".cache", ignore_errors=True)
    if not fc_ok:
        return {"task_id": task["id"], "model": model["label"], "arm": f"t2ad-{mode}",
                "seed": seed, "rc": 0, "parsed": False, "fact_check_ok": False,
                "fact_check": fc, "answer": {}, "queries": [], "exact": False}
    hint = (f"T2 A+D: snapshots are prebuilt. Use `--from-snapshot {tag}` on every "
            "query; do NOT parse/build source. For direct fanin/fanout also use "
            "`--depth 1`; record exact commands in `queries`.")
    if mode == "skill":
        skill_dst = ws / ".dsh" / "skills" / "svq-query-protocol"
        skill_dst.parent.mkdir(parents=True, exist_ok=True)
        if skill_dst.exists():
            shutil.rmtree(skill_dst)
        shutil.copytree(SKILL, skill_dst)
        hint += (" A project skill `svq-query-protocol` is installed. Load it "
                 "with the skill tool before the first query and follow it.")
    elif mode == "inline":
        body = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        if body.startswith("---"):
            parts = body.split("---", 2)
            body = parts[2] if len(parts) == 3 else body
        hint += ("\n\nPROTOCOL SKILL (inline; source .dsh/skills/"
                 "svq-query-protocol/SKILL.md):\n" + body.strip())
    prompt = base.PROMPT.format(ws=ws, input=input_path, question=task["question"],
                                budget=budget, task_id=task["id"], arm_hint=hint)
    patch = ws / "model.patch.yml"
    shutil.copy2((base.INTERACTIVE / model["patch"]).resolve(), patch)
    cmd = ["sandbox-exec",
           "-D", f"REPO={base.ROOT}", "-D", f"PILOT={base.PILOT}",
           "-D", f"SVQ={base.SVQ}", "-D", f"TASKS={base.HERE}",
           "-D", f"TRUTH={base.ROOT / 'docs' / 'validation'}",
           "-f", str(base.PROFILES / "t2_long.sb"),
           "dsh", "--profile", "headless", "--patch", str(patch), prompt]
    env = base._env()
    env[AD_SNAP_ENV] = str(AD_SNAPS)
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
    parsed = base._extract_json(text)
    ans = (parsed or {}).get("answer", parsed or {})
    queries = (parsed or {}).get("queries") or []
    sc = score_answer(task, ans)
    depth1_ok = (not base._needs_depth(task)) or any(
        "--depth 1" in str(q) or "--depth=1" in str(q) for q in queries)
    raw = base.WORK / model["label"].replace(".", "_") / task["id"] / f"t2ad-{mode}-s{seed}.txt"
    raw.write_text(text)
    return {"task_id": task["id"], "model": model["label"], "arm": f"t2ad-{mode}",
            "seed": seed, "duration_ms": int((time.time() - t0) * 1000),
            "rc": rc, "confidence": (parsed or {}).get("confidence"),
            "answer": ans, "queries": queries, "depth1_ok": depth1_ok,
            "fact_check_ok": True, "fact_check": fc,
            "parsed": parsed is not None, "exact": sc["canonical"],
            "semantic": sc["semantic"], "workspace": str(ws), "stderr": err}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", nargs="*", default=None)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--models", nargs="*", default=["MiniMax-M3", "DeepSeek-Flash"])
    ap.add_argument("--modes", nargs="*", default=["prompt", "skill"])
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--budget", type=int, default=8)
    ap.add_argument("--output", type=Path, default=Path("/tmp/long_12_ad.json"))
    args = ap.parse_args()
    prep = _prepare()
    checks = _check_snapshots()
    tasks = json.loads(base.TASKS.read_text())["tasks"]
    if args.tasks:
        tasks = [t for t in tasks if t["id"] in args.tasks]
    models = [m for m in base.MODELS if m["label"] in args.models]
    jobs = [(t, m, mode) for t in tasks for m in models for mode in args.modes]
    rows = []
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as ex:
        futs = {ex.submit(_ad_run, t, m, args.seed, args.budget, mode): (t, m, mode)
                for t, m, mode in jobs}
        for f in as_completed(futs):
            r = f.result()
            rows.append(r)
            print(json.dumps({k: r.get(k) for k in
                              ("task_id", "model", "arm", "seed", "rc", "parsed",
                               "duration_ms", "exact", "protocol_ok")}, ensure_ascii=False))
    rows.sort(key=lambda r: (r["task_id"], r["model"]))
    payload = {"protocol": "P94 12-task A+D: pruned filelist snapshot, T2 only",
               "seed": args.seed, "prep": prep, "checks": checks,
               "tasks": tasks, "results": rows}
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
