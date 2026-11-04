#!/usr/bin/env python3
"""[iter_369 / PLAN P67.1] 查询性能基准：冷启动 + 图内查询 + 峰值内存。

用法:
  python3 tools/benchmark/query_perf.py --output /tmp/query_perf.json
  python3 tools/benchmark/query_perf.py --json

测量:
- build_ms: 一次构图；
- query_ms: 图内 trace_fanin/fanout；
- cold_cli_ms: 新进程 `sv_query trace ... --no-cache` 的端到端延迟；
- peak_rss_mb: 构图 + 查询子进程 ru_maxrss。

设计:
- picorv32（单文件 RISC-V 核）
- verilog-axi（165 实例、13k 节点）
- SERV（rtl/servile/serving 24 文件）
缺语料 → 显式 skipped，不伪造。
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import resource
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from inputs import (  # noqa: E402
    ensure_serv_filelist, ensure_verilog_axi_filelist, picorv32_file,
)
from trace.unified_tracer import UnifiedTracer  # noqa: E402


def _cases() -> list[dict]:
    pico = picorv32_file()
    axi = ensure_verilog_axi_filelist()
    serv = ensure_serv_filelist()
    return [
        {"name": "picorv32", "kind": "file", "path": pico,
         "queries": [{"cmd": "fanin", "signal": "picorv32_axi.axi_adapter.mem_rdata[16]"},
                     {"cmd": "fanout", "signal": "picorv32_axi.mem_valid"}]},
        {"name": "verilog-axi", "kind": "filelist", "path": axi,
         "queries": [{"cmd": "fanin",
                      "signal": "axi_adapter.axi_adapter_rd_inst.m_axi_araddr[0]"},
                     {"cmd": "fanout",
                      "signal": "axi_adapter.axi_adapter_rd_inst.m_axi_arvalid"}]},
        {"name": "serv", "kind": "filelist", "path": serv,
         "queries": [{"cmd": "fanin", "signal": "serv_rf_top.clk"},
                     {"cmd": "fanout", "signal": "serv_rf_top.clk"}]},
    ]


def _rss_mb() -> float:
    raw = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    # macOS: bytes; Linux: KiB
    div = 1024 ** 2 if sys.platform == "darwin" else 1024
    return round(raw / div, 1)


def _tracer(spec: dict) -> UnifiedTracer:
    if spec["kind"] == "file":
        return UnifiedTracer(files=[spec["path"]], log_level="ERROR")
    return UnifiedTracer(filelist=spec["path"], log_level="ERROR")


def _in_process(spec: dict) -> dict:
    if not spec.get("path"):
        return {"name": spec["name"], "status": "skipped",
                "reason": "missing openrtl source"}
    t0 = time.perf_counter()
    tracer = _tracer(spec)
    graph = tracer.build_graph(use_cache=False)
    build_ms = round((time.perf_counter() - t0) * 1000, 1)
    queries = []
    for q in spec["queries"]:
        t0 = time.perf_counter()
        if q["cmd"] == "fanin":
            rows = tracer.trace_fanin(q["signal"])
        else:
            rows = tracer.trace_fanout(q["signal"])
        queries.append({"cmd": q["cmd"], "signal": q["signal"],
                        "ms": round((time.perf_counter() - t0) * 1000, 1),
                        "count": len(rows)})
    return {"name": spec["name"], "status": "ok", "build_ms": build_ms,
            "nodes": graph.number_of_nodes(), "edges": graph.number_of_edges(),
            "queries": queries, "peak_rss_mb": _rss_mb()}


def _cold_cli(spec: dict, query: dict) -> dict:
    path_flag = "--file" if spec["kind"] == "file" else "--filelist"
    cmd = ["sv_query", "trace", query["cmd"], query["signal"],
           path_flag, spec["path"], "--no-cache", "--json"]
    t0 = time.perf_counter()
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300,
                          cwd=str(ROOT))
    ms = round((time.perf_counter() - t0) * 1000, 1)
    ok = proc.returncode == 0
    count = None
    if ok:
        try:
            data = json.loads(proc.stdout)
            count = data.get("result", {}).get("total_count")
        except json.JSONDecodeError:
            ok = False
    return {"cmd": query["cmd"], "signal": query["signal"], "ms": ms,
            "ok": ok, "count": count,
            "error": None if ok else (proc.stderr[-200:] or proc.stdout[-200:])}


def _child(name: str) -> int:
    spec = next((s for s in _cases() if s["name"] == name), None)
    if spec is None:
        print(json.dumps({"name": name, "status": "error",
                          "reason": "unknown case"}))
        return 1
    print(json.dumps(_in_process(spec), ensure_ascii=False))
    return 0


def _main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", help="write full JSON here")
    ap.add_argument("--json", action="store_true", help="print full JSON")
    ap.add_argument("--child", help=argparse.SUPPRESS)
    args = ap.parse_args()
    if args.child:
        return _child(args.child)

    cases = []
    for spec in _cases():
        if not spec.get("path"):
            cases.append({"name": spec["name"], "status": "skipped",
                          "reason": "missing openrtl source"})
            continue
        proc = subprocess.run(
            [sys.executable, __file__, "--child", spec["name"]],
            capture_output=True, text=True, timeout=600, cwd=str(ROOT))
        if proc.returncode != 0 or not proc.stdout.strip():
            cases.append({"name": spec["name"], "status": "error",
                          "reason": (proc.stderr or proc.stdout)[-300:]})
            continue
        row = json.loads(proc.stdout)
        row["cold_cli"] = [_cold_cli(spec, q) for q in spec["queries"][:1]]
        cases.append(row)

    report = {
        "ok": all(c.get("status") == "ok" for c in cases),
        "skipped": [c["name"] for c in cases if c.get("status") == "skipped"],
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "environment": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "cpu": platform.processor(),
        },
        "cases": cases,
    }
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8")
    if args.json:
        print(text)
    else:
        for c in cases:
            if c["status"] != "ok":
                print(f"{c['name']}: {c['status']} ({c.get('reason')})")
                continue
            print(f"{c['name']}: build={c['build_ms']}ms "
                  f"nodes={c['nodes']} rss={c['peak_rss_mb']}MB")
            for q, cli in zip(c["queries"], c.get("cold_cli", [])):
                print(f"  {q['cmd']} {q['signal']}: {q['ms']}ms "
                      f"count={q['count']} | cold_cli={cli['ms']}ms")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(_main())
