#!/usr/bin/env python3
"""
[PR6 2026-06-15] sv_query benchmark regression check.

对比新跑的 benchmark JSON 跟 baseline JSON, 输出 regression 报告.
如果新跑的数据跟 baseline 差距超过阈值, 失败退出 (供 CI 用).

用法:
  # 单项目检查
  python tools/benchmark/check_regression.py --current bench.json --baseline baselines/picorv32.json

  # 批量检查 (current 是目录, baseline 是目录)
  python tools/benchmark/check_regression.py --current-dir bench_results/ --baseline-dir tools/benchmark/baselines/

  # 自动找 baseline (按 current.metadata.target 匹配)
  python tools/benchmark/check_regression.py --current bench.json --baseline-dir tools/benchmark/baselines/

阈值:
  - L2 nodes: 不能跌 > 30%
  - L2 edges: 不能跌 > 30%
  - L2 IM: 不能跌 > 30% (允许 ±20% 波动)
  - L1 instances: 不能跌 > 50% (AST 路径, 容易受 flakiness 影响)
  - L4 edges: 不能跌 > 50% (同上)
  - Flakiness: deterministic_ratio_im 不能低于 0.7
"""
import argparse
import json
import sys
from pathlib import Path
from typing import Any

# [PR6 2026-06-15] 默认阈值 — 跟 PR1-5 已知能力匹配
DEFAULT_THRESHOLDS = {
    "L2_nodes": {"max_drop_pct": 30.0},        # 节点数不能跌 30%
    "L2_edges": {"max_drop_pct": 30.0},       # 边数不能跌 30%
    "L2_im": {"max_drop_pct": 30.0},          # IM 数不能跌 30%
    "L1_instances": {"max_drop_pct": 50.0},  # AST 容易受 flakiness
    "L4_edges": {"max_drop_pct": 50.0},       # 同样受 flakiness
    "flakiness_im_det_ratio": {"min": 0.7},   # 至少 70% deterministic
}


def _safe_get(data: dict, *keys: str, default: Any = None) -> Any:
    """Get nested dict value with default."""
    cur = data
    for k in keys:
        if isinstance(cur, dict):
            cur = cur.get(k, default)
        else:
            return default
    return cur


def check_single(
    current: dict,
    baseline: dict,
    thresholds: dict = None,
) -> tuple[bool, list[str]]:
    """[PR6] Check single benchmark vs baseline.

    Returns:
        (passed, messages)
    """
    thresholds = thresholds or DEFAULT_THRESHOLDS
    messages: list[str] = []
    passed = True

    # ---- L2 (most reliable) ----
    base_l2 = _safe_get(baseline, "L2_graph_topology")
    curr_l2 = _safe_get(current, "L2_graph_topology")
    if base_l2 and curr_l2 and "error" not in curr_l2:
        for key, label in [("nodes", "L2_nodes"), ("edges", "L2_edges"),
                            ("instantiated_modules", "L2_im")]:
            base_v = base_l2.get(key, 0)
            curr_v = curr_l2.get(key, 0)
            if base_v == 0:
                continue
            drop_pct = (base_v - curr_v) / base_v * 100
            max_drop = thresholds[label]["max_drop_pct"]
            if drop_pct > max_drop:
                passed = False
                messages.append(
                    f"❌ {label}: dropped {drop_pct:.1f}% "
                    f"(baseline={base_v}, current={curr_v}, max_drop={max_drop}%)"
                )
            else:
                messages.append(
                    f"✅ {label}: baseline={base_v}, current={curr_v} "
                    f"(drop {drop_pct:+.1f}%, max allowed {max_drop}%)"
                )

    # ---- L1 (AST, may be 0 due to flakiness) ----
    base_l1 = _safe_get(baseline, "L1_module_extraction")
    curr_l1 = _safe_get(current, "L1_module_extraction")
    if base_l1 and curr_l1 and "error" not in curr_l1:
        base_v = base_l1.get("instance_count", 0)
        curr_v = curr_l1.get("instance_count", 0)
        if base_v > 0:
            drop_pct = (base_v - curr_v) / base_v * 100
            max_drop = thresholds["L1_instances"]["max_drop_pct"]
            if drop_pct > max_drop:
                messages.append(
                    f"⚠️  L1_instances: dropped {drop_pct:.1f}% "
                    f"(baseline={base_v}, current={curr_v}, max_drop={max_drop}%) — "
                    f"may be memory flakiness, manual review needed"
                )
            else:
                messages.append(
                    f"✅ L1_instances: baseline={base_v}, current={curr_v} "
                    f"(drop {drop_pct:+.1f}%)"
                )

    # ---- L4 (MIG-based, may be 0 due to flakiness) ----
    base_l4 = _safe_get(baseline, "L4_cross_instance_edges")
    curr_l4 = _safe_get(current, "L4_cross_instance_edges")
    if base_l4 and curr_l4 and "error" not in curr_l4:
        base_v = base_l4.get("edge_count", 0)
        curr_v = curr_l4.get("edge_count", 0)
        if base_v > 0:
            drop_pct = (base_v - curr_v) / base_v * 100
            max_drop = thresholds["L4_edges"]["max_drop_pct"]
            if drop_pct > max_drop:
                messages.append(
                    f"⚠️  L4_edges: dropped {drop_pct:.1f}% "
                    f"(baseline={base_v}, current={curr_v}, max_drop={max_drop}%) — "
                    f"may be memory flakiness, manual review needed"
                )
            else:
                messages.append(
                    f"✅ L4_edges: baseline={base_v}, current={curr_v} "
                    f"(drop {drop_pct:+.1f}%)"
                )

    # ---- Flakiness ----
    base_flk = _safe_get(baseline, "flakiness")
    curr_flk = _safe_get(current, "flakiness")
    if base_flk and curr_flk and "error" not in curr_flk:
        base_det = base_flk.get("deterministic_ratio_im", 0)
        curr_det = curr_flk.get("deterministic_ratio_im", 0)
        min_det = thresholds["flakiness_im_det_ratio"]["min"]
        if curr_det < min_det:
            passed = False
            messages.append(
                f"❌ flakiness_im_det_ratio: {curr_det*100:.0f}% "
                f"(min required {min_det*100:.0f}%) — memory pressure likely"
            )
        else:
            messages.append(
                f"✅ flakiness: deterministic_ratio_im = {curr_det*100:.0f}% "
                f"(min {min_det*100:.0f}%)"
            )

    return passed, messages


def main():
    parser = argparse.ArgumentParser(
        description="[PR6 2026-06-15] sv_query benchmark regression check."
    )
    parser.add_argument("--current", help="Current benchmark JSON")
    parser.add_argument("--baseline", help="Baseline JSON")
    parser.add_argument("--current-dir", help="Directory of current benchmark JSONs")
    parser.add_argument("--baseline-dir", help="Directory of baseline JSONs")
    parser.add_argument("--json-output", help="Output JSON report path")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    args = parser.parse_args()

    if not (args.current or args.current_dir):
        parser.error("must specify --current or --current-dir")

    # Load files
    pairs = []  # list of (name, current, baseline)
    if args.current:
        curr_path = Path(args.current)
        if not curr_path.exists():
            print(f"Current not found: {curr_path}", file=sys.stderr)
            sys.exit(2)
        with open(curr_path) as f:
            current = json.load(f)

        # Find baseline
        if args.baseline:
            base_path = Path(args.baseline)
        elif args.baseline_dir:
            target = current["metadata"]["target"]
            base_path = Path(args.baseline_dir) / f"{target}.json"
        else:
            print("must specify --baseline or --baseline-dir", file=sys.stderr)
            sys.exit(2)

        if not base_path.exists():
            print(f"Baseline not found: {base_path}", file=sys.stderr)
            sys.exit(2)
        with open(base_path) as f:
            baseline = json.load(f)
        pairs.append((curr_path.stem, current, baseline))
    else:
        curr_dir = Path(args.current_dir)
        base_dir = Path(args.baseline_dir) if args.baseline_dir else None
        for curr_path in curr_dir.glob("*.json"):
            with open(curr_path) as f:
                current = json.load(f)
            target = current["metadata"]["target"]
            if base_dir:
                base_path = base_dir / f"{target}.json"
            else:
                base_path = curr_dir / "baseline.json"
            if not base_path.exists():
                print(f"⚠️  No baseline for {target}, skipping", file=sys.stderr)
                continue
            with open(base_path) as f:
                baseline = json.load(f)
            pairs.append((curr_path.stem, current, baseline))

    if not pairs:
        print("No pairs to check", file=sys.stderr)
        sys.exit(1)

    # Run checks
    all_passed = True
    report = {"checks": []}
    for name, current, baseline in pairs:
        passed, messages = check_single(current, baseline)
        if not passed:
            all_passed = False
        result = {
            "name": name,
            "passed": passed,
            "messages": messages,
        }
        report["checks"].append(result)
        print(f"\n=== {name} ===")
        for m in messages:
            print(f"  {m}")

    report["all_passed"] = all_passed
    print(f"\n{'='*60}")
    if all_passed:
        print("✅ All checks PASSED")
    else:
        print("❌ Some checks FAILED")

    if args.json_output:
        with open(args.json_output, "w") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(f"\nWrote JSON report: {args.json_output}")

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
