#!/usr/bin/env python3
"""[iter_317 / PLAN P21] 真实工程查询 smoke。

验证 P13~P20 对图/精度/缓存标记的改动在真实多文件工程上不回归：
  - 构建：节点/边规模下限、dynamic/function 标记节点
  - 查询：agent 常用 fanin/fanout/位查询 JSON 契约与 precision 标记
  - 缓存：strict_uart 二次加载 dynamic 标记不丢

用法:
  python3 tools/smoke_real_projects.py --project all --json
  python3 tools/smoke_real_projects.py --project uart
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from trace.unified_tracer import UnifiedTracer  # noqa: E402

UART_FL = ROOT / "sim" / "tests" / "fixtures" / "strict_uart" / "filelist.f"
AXI_FL = ROOT / "sim" / "tests" / "fixtures" / "verilog-axi" / "filelist.f"
PICO = Path("/Users/fundou/my_dv_proj/openrtl/picorv32/picorv32.v")

PROJECTS = {
    "uart": {
        "kind": "filelist",
        "path": UART_FL,
        "required": True,
        "min_nodes": 20,
        "queries": [
            {"cmd": "fanin", "sig": "uart_top.rx_data_o",
             "expect": {"precision": "unknown", "dynamic_index": True,
                        "function_call": False, "min_count": 1}},
            {"cmd": "fanin", "sig": "uart_top.rx_data_o[3]",
             "expect": {"precision": "unknown", "dynamic_index": True,
                        "function_call": False, "min_count": 1}},
            {"cmd": "fanout", "sig": "uart_top.rx_fifo.mem",
             "expect": {"precision": "unknown", "dynamic_index": True,
                        "function_call": False, "min_count": 1}},
        ],
    },
    "axi": {
        "kind": "filelist",
        "path": AXI_FL,
        "required": False,
        "min_nodes": 10_000,
        "queries": [
            {"cmd": "fanin", "sig": "axi_adapter.axi_adapter_rd_inst.m_axi_araddr[0]",
             "expect": {"precision": "bus", "coarse_fallback": True,
                        "dynamic_index": False, "function_call": False,
                        "min_count": 1}},
        ],
    },
    "picorv32": {
        "kind": "file",
        "path": PICO,
        "required": False,
        "min_nodes": 1_000,
        "queries": [
            {"cmd": "fanin", "sig": "picorv32_axi.mem_rdata[16]",
             "expect": {"precision": "bit", "coarse_fallback": False,
                        "dynamic_index": False, "function_call": False,
                        "min_count": 1}},
        ],
    },
}


def _svq_cmd() -> list[str]:
    exe = shutil.which("sv_query")
    if exe:
        return [exe]
    return [sys.executable, "-m", "cli.main"]


def _run_query(kind: str, path: Path, query: dict) -> dict:
    args = _svq_cmd() + [
        "trace", query["cmd"], query["sig"],
        "--filelist" if kind == "filelist" else "--file", str(path),
        "--json",
    ]
    proc = subprocess.run(args, capture_output=True, text=True, timeout=180,
                          cwd=str(ROOT))
    if proc.returncode != 0:
        return {"ok": False, "error": f"rc={proc.returncode}",
                "stderr": proc.stderr[-300:]}
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        return {"ok": False, "error": f"bad json: {exc}", "stdout": proc.stdout[-300:]}
    sig = data.get("result", {}).get("signals", [{}])[0]
    return {"ok": bool(data.get("ok")), "signal": sig,
            "errors": data.get("errors", [])}


def _check(query: dict, got: dict) -> list[str]:
    fails = []
    if not got.get("ok"):
        fails.append(f"ok=false: {got.get('error') or got.get('errors')}")
        return fails
    sig = got.get("signal") or {}
    for key, want in query["expect"].items():
        if key == "min_count":
            if int(sig.get("count", 0)) < int(want):
                fails.append(f"count {sig.get('count')} < {want}")
        elif sig.get(key) != want:
            fails.append(f"{key} {sig.get(key)!r} != {want!r}")
    for key in ("precision", "coarse_fallback", "dynamic_index", "function_call"):
        if key not in sig:
            fails.append(f"missing field {key}")
    return fails


def run_project(name: str, spec: dict) -> dict:
    path = spec["path"]
    if not path.exists():
        return {"status": "skipped", "reason": f"missing {path}"}

    t0 = time.time()
    tracer = UnifiedTracer(
        **({"filelist": str(path)} if spec["kind"] == "filelist"
           else {"sources": {str(path): path.read_text()}}),
        log_level="ERROR",
    )
    try:
        graph = tracer.build_graph(use_cache=True, force=True)
    except Exception as exc:  # noqa: BLE001 - smoke 要报告失败，不能吞
        return {"status": "failed", "error": f"build: {exc}"}
    nodes = len(graph.nodes())
    edges = sum(1 for _ in graph.edges())
    dynamic = len(getattr(graph, "_dynamic_nodes", set()))
    functions = len(getattr(graph, "_function_nodes", set()))
    build_s = round(time.time() - t0, 2)

    result = {
        "status": "ok", "kind": spec["kind"], "path": str(path),
        "build_seconds": build_s, "nodes": nodes, "edges": edges,
        "dynamic_nodes": dynamic, "function_nodes": functions,
        "checks": [], "failures": [],
    }
    if nodes < spec["min_nodes"]:
        result["failures"].append(f"nodes {nodes} < {spec['min_nodes']}")

    # 缓存二次加载：strict_uart 验证 dynamic 标记不丢（图 key v9）
    if name == "uart":
        t2 = UnifiedTracer(filelist=str(path), log_level="ERROR")
        g2 = t2.build_graph(use_cache=True)
        result["cache_dynamic_nodes"] = len(getattr(g2, "_dynamic_nodes", set()))
        if set(getattr(g2, "_dynamic_nodes", set())) != set(getattr(graph, "_dynamic_nodes", set())):
            result["failures"].append("cache roundtrip lost dynamic nodes")

    for query in spec["queries"]:
        got = _run_query(spec["kind"], path, query)
        fails = _check(query, got)
        sig = got.get("signal") or {}
        result["checks"].append({
            "cmd": query["cmd"], "signal": query["sig"],
            "precision": sig.get("precision"),
            "coarse_fallback": sig.get("coarse_fallback"),
            "dynamic_index": sig.get("dynamic_index"),
            "function_call": sig.get("function_call"),
            "count": sig.get("count"),
            "failures": fails,
        })
        result["failures"].extend(fails)

    if result["failures"]:
        result["status"] = "failed"
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--project", choices=["all", *PROJECTS], default="all")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args()

    names = list(PROJECTS) if args.project == "all" else [args.project]
    report = {"ok": True, "projects": {}, "skipped": []}
    for name in names:
        res = run_project(name, PROJECTS[name])
        report["projects"][name] = res
        if res["status"] == "skipped":
            report["skipped"].append({"project": name, "reason": res.get("reason")})
        elif res["status"] != "ok":
            report["ok"] = False

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        for name, res in report["projects"].items():
            if res["status"] == "skipped":
                print(f"[SKIP] {name}: {res.get('reason')}")
                continue
            mark = "PASS" if res["status"] == "ok" else "FAIL"
            print(f"[{mark}] {name}: nodes={res.get('nodes')} edges={res.get('edges')} "
                  f"dynamic={res.get('dynamic_nodes')} functions={res.get('function_nodes')} "
                  f"build={res.get('build_seconds')}s")
            for chk in res.get("checks", []):
                print(f"  {chk['cmd']} {chk['signal']}: precision={chk['precision']} "
                      f"dynamic={chk['dynamic_index']} func={chk['function_call']} "
                      f"count={chk['count']} {chk['failures'] or ''}")
            for fail in res.get("failures", []):
                print(f"  !! {fail}")
        if report["skipped"]:
            print(f"skipped: {report['skipped']}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
