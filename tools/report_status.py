"""report_status.py — [P158.12.6 / R-028] 统一"绿色"口径

背景 (REVIEW_2026-11-11 §5.5 / P160 §7):
  canonical 报 `2744 passed / 0 failed`, opensource 报
  `112 passed / 11 skipped / 0 failed` —— 两个 `0 failed` 容易
  被读成"全绿", 但 123 deselected 是**deferred**（由 opensource 执行），
  11 skipped 才是显式未执行。报告必须分离 7 类状态 + deferred,
  "0 skipped / 0 failed" 不再是 KPI。

7 类状态:
  passed               : 执行且结果符合预期 (pytest passed / task exact)
  failed               : 执行且结果不符 (pytest failed / task exact=false)
  unknown              : 执行但无有效结论 (task 无解析答案; 不得计入 passed)
  truncated            : 执行被预算/时限截断 (timeout / budget exhausted)
  unexecuted           : 真正未执行 (task 异常未跑; deselected 不算)
  skipped_with_reason  : 显式 skip 且带 reason (pytest skip / retired exp)
  external_not_run     : 外部依赖缺失导致未跑 (openrtl corpus 等)

口径决策 (R-027 分母, **待方豆确认的当前默认**):
  false_confident 的分母 = answered_n (实际作答行数), 不含
  unknown / truncated / unexecuted / skipped / external_not_run;
  未执行单元既不算通过也不算失败, 但必须在报告中显式可见。
  pytest deselected 单独记 deferred, 不并入 unexecuted。

CLI:
  python3 tools/report_status.py --runs report.json
  python3 tools/report_status.py --tasks benchmark_results.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

STATUSES = (
    "passed", "failed", "unknown", "truncated",
    "unexecuted", "skipped_with_reason", "external_not_run",
)


def empty_status() -> dict[str, int]:
    return {s: 0 for s in STATUSES}


def classify_task(row: dict) -> str:
    """把一条 benchmark task 结果分到 7 类之一 (优先级从上到下)。"""
    if row.get("task_error") or row.get("rc") == 130:
        return "unexecuted"
    if row.get("external_missing") or row.get("env_skip"):
        return "external_not_run"
    if row.get("skipped") or row.get("skip_reason"):
        return "skipped_with_reason"
    if row.get("timeout") or row.get("truncated") or row.get("rc") == 124:
        return "truncated"
    if row.get("parsed") is False or not row.get("answer"):
        return "unknown"
    if row.get("exact") is True:
        return "passed"
    return "failed"


def classify_pytest_counts(counts: dict) -> dict[str, int]:
    """把 pytest 摘要计数 (passed/failed/skipped/deselected) 展开成 7 类。"""
    out = empty_status()
    out["passed"] = int(counts.get("passed", 0))
    out["failed"] = int(counts.get("failed", 0) + counts.get("errors", 0))
    out["skipped_with_reason"] = int(counts.get("skipped", 0))
    # P171.5: deselected is "not selected in this run", not "never executed".
    # It is commonly the complementary suite (canonical deselects opensource).
    out["unexecuted"] = int(counts.get("unexecuted", 0))
    out["deferred"] = int(counts.get("deselected", 0))
    out["external_not_run"] = int(counts.get("external_not_run", 0))
    return out


def summarize(rows: list[dict]) -> dict:
    """benchmark task rows -> 7 类计数 + 分母语义指标。"""
    counts = empty_status()
    for row in rows:
        counts[classify_task(row)] += 1
    answered_n = counts["passed"] + counts["failed"]
    false_confident = sum(
        1 for r in rows
        if classify_task(r) == "failed" and r.get("confidence") == "high"
    )
    return {
        **counts,
        "total": len(rows),
        "answered_n": answered_n,
        "false_confident": false_confident,
        # 分母 = 实际作答数; 未执行/未知不稀释 (口径待确认)
        "false_confident_rate": (
            round(false_confident / answered_n, 4) if answered_n else None
        ),
    }


def is_fully_green(statuses: dict[str, int]) -> bool:
    """只有 7 类中除 passed 外全部为 0 才算全绿。0 failed 不构成全绿。"""
    return (all(statuses.get(s, 0) == 0 for s in STATUSES if s != "passed")
            and statuses.get("deferred", 0) == 0)


def render_run(name: str, statuses: dict[str, int]) -> str:
    parts = " ".join(f"{s}={statuses.get(s, 0)}" for s in STATUSES)
    if "deferred" in statuses:
        parts += f" deferred={statuses['deferred']}"
    return f"run={name}: {parts}"


def render_report(report: dict) -> str:
    lines: list[str] = []
    totals = empty_status()
    totals["deferred"] = 0
    for run in report.get("runs", []):
        if "statuses" in run:
            statuses = {**empty_status(), **run["statuses"]}
        else:
            statuses = classify_pytest_counts(run)
        lines.append(render_run(run["name"], statuses))
        for s in STATUSES:
            totals[s] += statuses.get(s, 0)
        totals["deferred"] += statuses.get("deferred", 0)
    for task_run in report.get("task_runs", []):
        statuses = summarize(task_run["rows"])
        lines.append(render_run(task_run["name"], statuses))
        for s in STATUSES:
            totals[s] += statuses.get(s, 0)
        totals["deferred"] += statuses.get("deferred", 0)
    if not lines:
        lines.append("(no runs)")
    lines.append("-" * 60)
    lines.append(render_run("TOTAL", totals))
    not_executed = sum(totals.get(s, 0) for s in STATUSES
                       if s not in ("passed", "failed")) + totals["deferred"]
    if is_fully_green(totals):
        lines.append("VERDICT: fully green (all cells executed and passed)")
    else:
        lines.append(
            f"VERDICT: NOT fully green — 只看 failed 数不代表全绿; "
            f"未通过/未执行/未知单元 = {not_executed + totals['failed']} "
            f"(其中 unexecuted={totals['unexecuted']}, "
            f"deferred={totals['deferred']}，skipped/unknown 见上；"
            f"failed={totals['failed']})"
        )
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=Path, help="runs/pytest 摘要 JSON")
    ap.add_argument("--tasks", type=Path, help="benchmark task results JSON")
    args = ap.parse_args()
    if bool(args.runs) == bool(args.tasks):
        ap.error("需要且只需要 --runs 或 --tasks 之一")
    if args.tasks:
        data = json.loads(args.tasks.read_text(encoding="utf-8"))
        rows = data.get("results", data if isinstance(data, list) else [])
        print(render_report({"task_runs": [{"name": args.tasks.stem, "rows": rows}]}))
    else:
        data = json.loads(args.runs.read_text(encoding="utf-8"))
        print(render_report(data))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
