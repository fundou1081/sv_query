#!/usr/bin/env python3
"""[P69] 对 long_range_pilot JSON 做确定性评分（不调用模型）。"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# [P158.12.6] tools/ 顶层模块 (report_status) — 本脚本从 tools/benchmark/ 运行
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scoring import score_answer
from report_status import STATUSES, empty_status, summarize, classify_task  # [P158.12.6 / R-028]


def _match(field, got, want) -> bool:
    if field in ("path", "count"):
        return got == want
    if not isinstance(got, (list, tuple, set)) or not isinstance(want, (list, tuple, set)):
        return False
    return set(got) == set(want)


def score(data: dict) -> dict:
    tasks = {t["id"]: t for t in data["tasks"]}
    rows = []
    for item in data["results"]:
        ans = item.get("answer") or {}
        s = score_answer(tasks[item["task_id"]], ans)
        rows.append({**item, "exact": s["canonical"],
                     "semantic": s["semantic"],
                     "canonical_checks": s["canonical_checks"],
                     "semantic_checks": s["semantic_checks"]})
    groups = {}
    for item in rows:
        key = f"{item['model']} / {item['arm']}"
        groups.setdefault(key, []).append(item)
    summary = {}
    for key, items in groups.items():
        n = len(items)
        # [P158.12.6 / R-028] 状态分类分离: 未执行/未知/截断不得混进 n
        # 再拿 "exact/n" 冒充整体通过率; false_confident 分母 = 实际作答数。
        statuses = empty_status()
        rows_for_status = []
        for x in items:
            row = {
                "parsed": x.get("parsed"),
                "answer": x.get("answer"),
                "exact": x["exact"],
                "confidence": x.get("confidence"),
                "timeout": x.get("timeout", False),
                "truncated": x.get("truncated", False),
                "rc": x.get("rc"),
                "task_error": x.get("task_error", False),
                "skipped": x.get("skipped", False),
                "external_missing": x.get("external_missing", False),
            }
            statuses[classify_task(row)] += 1
            rows_for_status.append(row)
        status_summary = summarize(rows_for_status)
        summary[key] = {
            "n": n,
            "statuses": {s: statuses[s] for s in STATUSES},
            "answered_n": status_summary["answered_n"],
            "exact": sum(x["exact"] for x in items),
            "semantic": sum(1 for x in items if x.get("semantic") is True),
            "semantic_n": sum(1 for x in items if x.get("semantic") is not None),
            "false_confident_high": sum(
                1 for x in items if not x["exact"] and x.get("confidence") == "high"),
            "false_confident_denominator": status_summary["answered_n"],
            "mean_seconds": round(sum(x["duration_ms"] for x in items) / n / 1000, 1),
        }
    return {"rows": rows, "summary": summary}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("input", type=Path)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    result = score(json.loads(args.input.read_text(encoding="utf-8")))
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        for key, v in result["summary"].items():
            sem = (f"semantic={v['semantic']}/{v['semantic_n']} "
                   if v["semantic_n"] else "semantic=n/a ")
            st = " ".join(f"{s}={v['statuses'][s]}" for s in STATUSES
                          if v["statuses"][s])
            print(f"{key}: exact={v['exact']}/{v['n']} {sem}"
                  f"false_conf_high={v['false_confident_high']}/"
                  f"{v['false_confident_denominator']}(answered) "
                  f"mean={v['mean_seconds']}s | {st or 'all cells passed'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
