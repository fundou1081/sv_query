#!/usr/bin/env python3
"""[P90.1] Attribute agent wall time to cold build / cache load / queries / residual.

Uses an existing long-range result JSON and its workspace, replays the T2
commands with a cold cache and then a warm cache, and reports medians.
Read-only with respect to the original workspace (copies to /tmp).
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import statistics
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORK = Path("/tmp/p90_attr")


def _run(cmd: str, cwd: Path, env: dict, timeout: int = 300) -> float:
    t0 = time.perf_counter()
    subprocess.run(cmd, cwd=cwd, env=env, shell=True, executable="/bin/bash",
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                   timeout=timeout)
    return (time.perf_counter() - t0) * 1000.0


def _startup_ms(env: dict, cwd: Path) -> float:
    vals = [_run("sv_query --help", cwd, env, timeout=30) for _ in range(5)]
    return round(statistics.median(vals), 1)


def _selected(results: dict, task: str, model: str, arm: str, seed: int) -> dict:
    for r in results["results"]:
        if (r["task_id"], r["model"], r["arm"], r["seed"]) == (task, model, arm, seed):
            return r
    raise KeyError((task, model, arm, seed))


def attribute(row: dict, out_dir: Path) -> dict:
    src = Path(row.get("workspace") or
               f"/tmp/lr_long_hard/{row['model'].replace('.', '_')}/"
               f"{row['task_id']}/{row['arm']}-s{row['seed']}")
    ws = out_dir / row["task_id"]
    if ws.exists():
        shutil.rmtree(ws)
    shutil.copytree(src, ws)
    shutil.rmtree(ws / ".cache", ignore_errors=True)
    cache = ws / ".cache"
    env = os.environ.copy()
    env["SVQ_CACHE_DIR"] = str(cache)
    cmds = [q for q in row.get("queries", []) if q.strip().startswith("sv_query")]
    if not cmds:
        return {"task_id": row["task_id"], "model": row["model"],
                "seed": row["seed"], "error": "no sv_query commands"}

    cold = _run(cmds[0], ws, env)
    # Two warm passes; first command of pass 1 includes cache load.
    warm_passes: list[list[float]] = []
    for _ in range(2):
        warm_passes.append([_run(c, ws, env) for c in cmds])
    warm = [round(statistics.median([p[i] for p in warm_passes]), 1)
            for i in range(len(cmds))]
    startup = _startup_ms(env, ws)
    warm_sum = round(sum(warm), 1)
    nonfirst_median = statistics.median(warm[1:]) if len(warm) > 1 else warm[0]
    outliers = [i for i, ms in enumerate(warm)
                if ms > max(5000.0, 5 * nonfirst_median)]
    return {
        "task_id": row["task_id"], "model": row["model"], "arm": row["arm"],
        "seed": row["seed"], "agent_wall_ms": row["duration_ms"],
        "commands": len(cmds), "cli_startup_ms": startup,
        "cold_first_ms": round(cold, 1), "warm_first_ms": warm[0],
        "warm_sum_ms": warm_sum,
        "build_over_warm_ms": round(cold - warm[0], 1),
        "agent_minus_observed_ms": round(row["duration_ms"] - warm_sum, 1),
        "warm_outliers": outliers,
        "warm_outlier_commands": [cmds[i] for i in outliers],
        "warm_commands_ms": warm,
        "queries": cmds,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", type=Path,
                    default=ROOT / "docs/validation/long_range_12_fixed_2026-11-07.json")
    ap.add_argument("--output", type=Path,
                    default=ROOT / "docs/validation/query_cost_attribution_2026-11-07.json")
    ap.add_argument("--markdown", type=Path,
                    default=ROOT / "docs/validation/QUERY_COST_ATTRIBUTION_2026-11-07.md")
    args = ap.parse_args()
    data = json.loads(args.results.read_text())
    picks = [
        ("axi_araddr_neighbors", "MiniMax-M3", "t2", 1),
        ("serv_clk_path", "DeepSeek-Flash", "t2", 2),
        ("pico_adapter_mem_valid_fanout", "MiniMax-M3", "t2", 2),
    ]
    WORK.mkdir(parents=True, exist_ok=True)
    rows = [attribute(_selected(data, *p), WORK / f"{p[2]}-{p[3]}") for p in picks]
    out = {"method": "cold cache vs warm cache replay of agent T2 commands",
           "caution": "agent_minus_observed = agent wall - warm command sum; includes model generation and harness overhead; negative/outlier values mean self-reported query logs are not telemetry",
           "rows": rows}
    args.output.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n")
    lines = [
        "# 查询成本归因（P90.1）", "",
        "**方法**: 从 12-task fixed 结果中取 3 个 T2 cell，复制 workspace，清空 `.cache`；",
        "先跑第一条命令测 cold，再用同一 cache 跑两遍 warm，取每条命令中位数。",
        "`agent_minus_observed = agent wall - warm 命令总和`，包含模型生成/harness 开销；",
        "负值或异常大值说明 self-reported query log 与 wall 不一致，不能当精确 telemetry。", "",
        "| task | model | agent wall | cmds | cold | warm first | warm sum | agent-observed | outliers |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in rows:
        if "error" in r:
            lines.append(f"| {r['task_id']} | {r['model']} | - | - | - | - | - | {r['error']} | - |")
        else:
            lines.append(
                f"| {r['task_id']} | {r['model']} | {r['agent_wall_ms']/1000:.1f}s | "
                f"{r['commands']} | {r['cold_first_ms']/1000:.1f}s | "
                f"{r['warm_first_ms']/1000:.1f}s | {r['warm_sum_ms']/1000:.1f}s | "
                f"{r['agent_minus_observed_ms']/1000:.1f}s | "
                f"{','.join(str(i) for i in r['warm_outliers']) or '-'} |")
    lines += ["", "原始数据: " + args.output.name]
    args.markdown.write_text("\n".join(lines) + "\n")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
