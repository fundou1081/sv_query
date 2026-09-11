#!/usr/bin/env python3
"""
regen_baselines.py — 重新生成 `baselines/*.json` [iter_187]

为什么需要它: 2026-08 的三个 baseline 全部与当前行为不符 (且都不是当前输入可
复现的): 它们采集于 iter_145 (`top_modules=[target]`) 之前 —— 那时 pyslang 会
pre-elaborate filelist 里所有 free-floating 模块, 节点数/IM 数被虚高 (实测
picorv32 708→438 / IM 2→0; verilog-axi 8,221→715)。baseline 与行为漂移后,
`check_regression.py` 会对用户报**假 regression**。

本脚本用 `inputs.py` 现场构建输入, 跑 `run_benchmark.py` (含 `--runs 3`
flakiness 阶段, iter_185 后应 stdev=0), 写回 baseline JSON。

用法:
    python3 tools/benchmark/regen_baselines.py                 # 全部可复现目标
    python3 tools/benchmark/regen_baselines.py picorv32        # 指定目标
    python3 tools/benchmark/regen_baselines.py --check         # 只对比不写 (漂移检测)

退出码: 0 = 成功/无漂移; 1 = 输入缺失或任一目标失败; 2 = --check 检出漂移。
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import inputs  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
BENCH = Path(__file__).resolve().parent / "run_benchmark.py"
BASELINES = Path(__file__).resolve().parent / "baselines"

# 可复现目标: name → (输入构建函数, target, depth, traces)
TARGETS: dict[str, tuple] = {
    "picorv32": (
        lambda: {"--files": [inputs.picorv32_file()]},
        "picorv32",
        2,
        ["picorv32.clk", "picorv32.resetn", "picorv32.mem_busy"],
    ),
    "verilog_axi": (
        lambda: {"--filelist": inputs.ensure_verilog_axi_filelist()},
        "axi_dp_ram",
        4,
        ["axi_dp_ram.clk"],
    ),
    "pr5_wrap": (
        lambda: {"--filelist": inputs.ensure_pr5_wrap_filelist()},
        "pr5_wrap",
        4,
        ["pr5_wrap.clk_i", "pr5_wrap.rst_ni"],
    ),
}


def _run_one(name: str, runs: int) -> dict | None:
    build, target, depth, traces = TARGETS[name]
    spec = build()
    if not all(spec.values()) or any(v is None for v in spec.values()):
        print(f"[{name}] 输入缺失 (开源语料未 clone?) — 跳过")
        return None
    if "--files" in spec and None in spec["--files"]:
        print(f"[{name}] 文件缺失 — 跳过")
        return None

    out = BASELINES / f"{name}.json"
    args = [sys.executable, str(BENCH)]
    for flag, value in spec.items():
        args.append(flag)
        args.extend(value if isinstance(value, list) else [value])
    args += [
        "--target", target, "--depth", str(depth), "--runs", str(runs),
        "--traces", *traces, "--output", str(out),
    ]
    print(f"[{name}] {' '.join(args[2:])}")
    proc = subprocess.run(args, capture_output=True, text=True, cwd=REPO, timeout=1800)
    if proc.returncode != 0 or not out.exists():
        print(f"[{name}] ❌ 失败 rc={proc.returncode}\n{(proc.stderr or proc.stdout)[-800:]}")
        return None
    data = json.loads(out.read_text(encoding="utf-8"))
    l2 = data["L2_graph_topology"]
    flk = data.get("flakiness", {})
    print(
        f"[{name}] ✅ L1={data['L1_module_extraction'].get('instance_count')} "
        f"nodes={l2['nodes']} IM={l2['instantiated_modules']} "
        f"stdev={flk.get('node_stdev', 'n/a')}"
    )
    return data


def _compare(name: str, fresh: dict) -> bool:
    """对比 baseline 与刚采集的数据 (L2 关键量), 返回是否有漂移。"""
    path = BASELINES / f"{name}.json"
    if not path.exists():
        print(f"[{name}] baseline 不存在 → 视为漂移")
        return True
    old = json.loads(path.read_text(encoding="utf-8"))
    o, n = old["L2_graph_topology"], fresh["L2_graph_topology"]
    drift = False
    for key in ("nodes", "edges", "instantiated_modules"):
        if o.get(key) != n.get(key):
            print(f"[{name}] ⚠️ 漂移 {key}: baseline={o.get(key)} 当前={n.get(key)}")
            drift = True
    if not drift:
        print(f"[{name}] ✅ 无漂移 (nodes={n['nodes']} IM={n['instantiated_modules']})")
    return drift


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("targets", nargs="*", help="默认: 全部可复现目标")
    ap.add_argument("--runs", type=int, default=3, help="flakiness 阶段运行次数")
    ap.add_argument("--check", action="store_true",
                    help="只对比现有 baseline 与当前行为 (检测漂移, 不写文件)")
    args = ap.parse_args()

    names = args.targets or list(TARGETS)
    unknown = [n for n in names if n not in TARGETS]
    if unknown:
        print(f"未知目标: {unknown}; 可用: {list(TARGETS)}")
        return 1

    failed, drifted = False, False
    for name in names:
        if args.check:
            build, target, depth, traces = TARGETS[name]
            spec = build()
            if any(v is None for v in spec.values()):
                print(f"[{name}] 输入缺失 — 跳过 (不算漂移)")
                continue
            # --check 模式: 采集到临时文件后对比, 不覆盖 baseline
            out = Path("/tmp") / f"regen_check_{name}.json"
            cmd = [sys.executable, str(BENCH)]
            for flag, value in spec.items():
                cmd.append(flag)
                cmd.extend(value if isinstance(value, list) else [value])
            cmd += ["--target", target, "--depth", str(depth), "--runs", "1",
                    "--skip-flakiness", "--output", str(out)]
            proc = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO, timeout=1800)
            if proc.returncode != 0 or not out.exists():
                print(f"[{name}] ❌ 采集失败 rc={proc.returncode}")
                failed = True
                continue
            drifted |= _compare(name, json.loads(out.read_text(encoding="utf-8")))
        else:
            data = _run_one(name, args.runs)
            if data is None:
                failed = True

    if failed:
        return 1
    return 2 if drifted else 0


if __name__ == "__main__":
    raise SystemExit(main())
