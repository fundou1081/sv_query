#!/usr/bin/env python3
"""[P69] 对 long_range_pilot JSON 做确定性评分（不调用模型）。"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from scoring import score_answer


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
        summary[key] = {
            "n": n,
            "exact": sum(x["exact"] for x in items),
            "semantic": sum(1 for x in items if x.get("semantic") is True),
            "semantic_n": sum(1 for x in items if x.get("semantic") is not None),
            "false_confident_high": sum(
                1 for x in items if not x["exact"] and x.get("confidence") == "high"),
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
            print(f"{key}: exact={v['exact']}/{v['n']} {sem}"
                  f"false_conf_high={v['false_confident_high']}/{v['n']} "
                  f"mean={v['mean_seconds']}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
