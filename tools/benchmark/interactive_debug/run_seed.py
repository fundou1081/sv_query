#!/usr/bin/env python3
"""[P79] Run interactive-debug scenarios for one repeat seed.

No ground truth is copied into the agent workspace.  The parsed answers are
stored for human/scorer review; raw output stays under /tmp.
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

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
FIXTURES = ROOT / "examples" / "interactive_debug"
WORK = Path("/private/tmp/lr_p1")
RAW = Path("/tmp/lr_p1_raw")
CREDS = Path.home() / ".dsh" / ".credentials.yaml"

PROMPT_TAIL = """
This is repeat seed {seed}/2. Do not read any ground-truth/scenario JSON.
Use at least 4 actual query rounds; each round = one query + a short observation.
Return a compact JSON object:
{{"task_id": "...", "rounds": [{{"query": "...", "observation": "..."}}],
 "answer": {shape}, "confidence": "high|medium|low", "evidence": ["..."]}}
"""

SHAPES = {
    "deep_drive_chain": """{"path": [canonical ids], "hop_count": int,
 "register": "canonical REG id", "xor_node": "canonical signal id",
 "mux_control": "canonical select id", "mux_node": "canonical OP_TERNARY id",
 "combinational": bool}""",
    "rand_constraints": """{"vars": {"top.e.p.addr": {"rand_mode": "Rand", "type": "int", "constraints": ["packet.c_base", "packet.c_packet"]}, "top.e.p.len": {"rand_mode": "Rand", "type": "bit[7:0]", "constraints": ["packet.c_packet"]}},
 "defined_in": {"packet.c_base": "base", "packet.c_packet": "packet"},
 "inherited": {"packet.c_base": true, "packet.c_packet": false},
 "both_vars_block": "packet.c_packet"}""",
    "rand_coverage_mapping": """{"instance": "top.e", "covergroup": "cg",
 "mapping": {"top.e.p.addr": {"coverpoint": "cp_addr", "bins": ["low", "high"]},
             "top.e.p.len": {"coverpoint": "cp_len", "bins": ["len_small", "len_large"]}},
 "cross": {"name": "cross_cp_addr_cp_len", "items": ["cp_addr", "cp_len"]},
 "uncovered_rand_vars": []}""",
}

EXPECTED = {
    "deep_drive_chain": {
        "path": ["top.din", "top.u_mid.d", "top.u_mid.u_stage.d",
                 "top.u_mid.u_stage.u_leaf.d.ternary_sel", "top.u_mid.u_stage.u_leaf.d",
                 "top.u_mid.u_stage.u_leaf.q", "top.u_mid.u_stage.leaf_q",
                 "top.u_mid.u_stage.mixed", "top.u_mid.u_stage.q",
                 "top.u_mid.q", "top.mid_q", "top.dout"],
        "hop_count": 11, "register": "top.u_mid.u_stage.u_leaf.q",
        "xor_node": "top.u_mid.u_stage.mixed",
        "mux_control": "top.u_mid.u_stage.sel",
        "mux_node": "top.u_mid.u_stage.u_leaf.d.ternary_sel",
        "combinational": False,
    },
}


def _env() -> dict:
    env = os.environ.copy()
    refs = yaml.safe_load(CREDS.read_text()).get("refs", {})
    for k in ("MINIMAX_CN_API_KEY", "DEEPSEEK_API_KEY"):
        if refs.get(k):
            env[k] = refs[k]
    env["DSH_PERMISSION_MODE"] = "danger-full-access"
    return env


def _extract_json(text: str) -> dict | None:
    blocks = re.findall(r"```(?:json)?\s*(.*?)```", text, re.S)
    for block in reversed(blocks):
        try:
            d = json.loads(block)
        except json.JSONDecodeError:
            continue
        if isinstance(d, dict):
            return d
    # Last-resort: balanced object starting at a task_id/answer marker.
    for m in reversed(list(re.finditer(r"\{", text))):
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
                            return d
                    except json.JSONDecodeError:
                        break
    return None


def _find_answer(d: dict) -> dict:
    if isinstance(d.get("answer"), dict):
        return d["answer"]
    return d


def _check(task: str, d: dict | None) -> dict:
    if d is None:
        return {"parsed": False, "checks": {}}
    a = _find_answer(d)
    if task == "deep_drive_chain":
        exp = EXPECTED[task]
        return {"parsed": True, "checks": {
            "path": a.get("path") == exp["path"],
            "hop_count": a.get("hop_count") == exp["hop_count"],
            "register": a.get("register") == exp["register"],
            "xor_node": a.get("xor_node") == exp["xor_node"],
            "mux_control": a.get("mux_control") == exp["mux_control"],
            "mux_node": a.get("mux_node") == exp["mux_node"],
            "combinational": a.get("combinational") is False,
        }}
    blob = json.dumps(a, ensure_ascii=False).lower()
    if task == "rand_constraints":
        return {"parsed": True, "checks": {
            "c_base": "c_base" in blob, "c_packet": "c_packet" in blob,
            "base_defined": "base" in blob, "both_block": "packet.c_packet" in blob,
            "addr_rand": "rand" in blob and "addr" in blob,
        }}
    return {"parsed": True, "checks": {
        "cp_addr": "cp_addr" in blob, "cp_len": "cp_len" in blob,
        "low_high": "low" in blob and "high" in blob,
        "len_bins": "len_small" in blob and "len_large" in blob,
        "cross": "cross_cp_addr_cp_len" in blob,
        "uncovered_empty": "uncovered_rand_vars" in blob,
    }}


def _run_one(model: dict, scenario: dict, seed: int) -> dict:
    sid = scenario["id"]
    ws = WORK / model["label"].replace(".", "_") / sid / f"s{seed}"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True)
    shutil.copy2(FIXTURES / scenario["fixture"].split("/")[-1], ws)
    shape = SHAPES[sid]
    prompt = (
        "INTERACTIVE DEBUG. Work only in the current directory (cwd is the "
        f"isolated workspace {ws}); read-only; no web; use installed sv_query. "
        f"Fixture {Path(scenario['fixture']).name}. {scenario['prompt']}\n"
        + PROMPT_TAIL.format(seed=seed, shape=shape)
    )
    patch = (HERE / model["patch"]).resolve()
    t0 = time.time()
    r = None
    for attempt in range(3):
        try:
            r = subprocess.run(
                ["dsh", "--profile", "headless", "--patch", str(patch), prompt],
                cwd=ws, env=_env(), capture_output=True, text=True, timeout=900,
            )
        except subprocess.TimeoutExpired as e:
            text = (e.stdout or "")
            if isinstance(text, bytes):
                text = text.decode(errors="replace")
            err = "TIMEOUT"
            rc = 124
            break
        text, err, rc = r.stdout, r.stderr[-2000:], r.returncode
        if rc == 0 or "RATE_LIMIT" not in err:
            break
        time.sleep(60 * (attempt + 1))
    RAW.mkdir(parents=True, exist_ok=True)
    raw_name = f"{model['label'].replace('.', '_')}__{sid}__s{seed}.txt"
    (RAW / raw_name).write_text(text)
    parsed = _extract_json(text)
    return {
        "model": model["label"], "scenario": sid, "seed": seed,
        "seconds": round(time.time() - t0, 1), "rc": rc, "stderr": err,
        "result": parsed, "checks": _check(sid, parsed),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=2)
    ap.add_argument("--models", nargs="*", default=None)
    ap.add_argument("--scenarios", nargs="*", default=None)
    ap.add_argument("--workers", type=int, default=3)
    args = ap.parse_args()
    scenarios = json.loads((HERE / "scenarios.json").read_text())["scenarios"]
    models = json.loads((HERE / "models.json").read_text())["models"]
    if args.models:
        models = [m for m in models if m["label"] in args.models]
    if args.scenarios:
        scenarios = [s for s in scenarios if s["id"] in args.scenarios]
    jobs = [(m, s) for m in models for s in scenarios]
    out = []
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as ex:
        futs = {ex.submit(_run_one, m, s, args.seed): (m, s) for m, s in jobs}
        for f in as_completed(futs):
            row = f.result()
            out.append(row)
            print(json.dumps({k: row[k] for k in ("model", "scenario", "seed", "seconds", "checks")},
                             ensure_ascii=False))
    out.sort(key=lambda r: (r["model"], r["scenario"]))
    dest = Path("/tmp/lr_p1_results.json")
    dest.write_text(json.dumps(out, ensure_ascii=False, indent=2))
    print(f"wrote {dest}")


if __name__ == "__main__":
    main()
