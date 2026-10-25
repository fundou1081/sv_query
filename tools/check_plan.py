#!/usr/bin/env python3
"""check_plan.py — `PLAN.md` 计划树格式校验（唯一计划源）

[iter_279] 方豆要求："用一个全局唯一的计划树管理目前以及将来所有的代码修改计划"。
本工具是它的**机械守卫**，避免计划树漂移成"随便写的 markdown"。

校验项（任一失败 = 非 0 退出）:
  P1 恰好一条 `current item : ...` 行
  P2 current item 必须能在计划树里找到，且 content / status 完全一致
  P3 计划项格式: `[-- ]P<数字>[.<数字>...] <内容> <状态>`
  P4 id 全局唯一
  P5 子项 (`-- `) 的父项必须存在（且父项是顶层项）
  P6 状态词只能是: 待做 / 进行中 / 已完成 / 阻塞 / 放弃
  P7 最多一项 `进行中`，且必须是 current item（current 可为 `待做` = 即将开始）
  P8 至少 1 个计划项

用法:
    python3 tools/check_plan.py            # 校验 PLAN.md
    python3 tools/check_plan.py --quiet    # 只报错误
退出码: 0 = 通过; 1 = 有问题
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PLAN = REPO / "PLAN.md"

STATUSES = ("待做", "进行中", "已完成", "阻塞", "放弃")
STATUS_ALT = "|".join(STATUSES)
ITEM_RE = re.compile(
    rf"^(?P<dash>-- )?(?P<id>P\d+(?:\.\d+)*) (?P<content>\S.*?) <(?P<status>{STATUS_ALT})>$"
)
CURRENT_RE = re.compile(
    rf"^current item : (?P<id>P\d+(?:\.\d+)*) (?P<content>\S.*?) <(?P<status>{STATUS_ALT})>$"
)


def _items(text: str) -> list[dict]:
    """收集计划项行（去掉首尾空白；跳过代码块/表格等不匹配行）。"""
    items = []
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if line.startswith("```") or line.startswith("|") or line.startswith(">"):
            continue
        m = ITEM_RE.match(line)
        if not m:
            continue
        item = {k: m.group(k) for k in ("dash", "id", "content", "status")}
        item["line"] = lineno
        items.append(item)
    return items


def _parent_of(item_id: str) -> str | None:
    return item_id.rsplit(".", 1)[0] if "." in item_id else None


def check(text: str) -> list[str]:
    errors: list[str] = []
    lines = [ln.strip() for ln in text.splitlines()]
    currents = [ln for ln in lines if ln.startswith("current item :")]

    # P1
    if len(currents) != 1:
        errors.append(f"P1: 需要恰好 1 条 `current item :` 行，实际 {len(currents)}")
        return errors

    cm = CURRENT_RE.match(currents[0])
    if not cm:
        errors.append(
            "P1: current item 行格式错误（应为 `current item : P0.1 内容 <状态>`）: "
            f"{currents[0]!r}"
        )
        return errors

    items = _items(text)

    # P8
    if not items:
        errors.append("P8: 计划树里没有任何计划项")
        return errors

    # P3 / P6：格式与状态词（非计划项的普通行不报错；这里只报"像计划但格式错"的行）
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith(("```", "|", ">", "#", "current item")):
            continue
        if re.match(r"^(-- )?P\d", line) and not ITEM_RE.match(line):
            errors.append(f"P3: 第 {lineno} 行计划项格式不合法: {line!r}")
        if "<" in line and ">" in line:
            m = re.search(r"<([^<>]*)>$", line)
            if m and re.match(r"^(-- )?P\d", line) and m.group(1) not in STATUSES:
                errors.append(f"P6: 第 {lineno} 行状态词非法 {m.group(1)!r}（只允许 {STATUSES}）")

    ids = [it["id"] for it in items]

    # P4
    dup = {i for i in ids if ids.count(i) > 1}
    if dup:
        errors.append(f"P4: 计划 id 重复: {sorted(dup)}")

    bye = {it["id"]: it for it in items}
    current_id = cm.group("id")

    # P2
    if current_id not in bye:
        errors.append(f"P2: current item {current_id} 不在计划树中")
    else:
        it = bye[current_id]
        if (it["content"], it["status"]) != (cm.group("content"), cm.group("status")):
            errors.append(
                "P2: current item 与计划树不一致: "
                f"current=({cm.group('content')!r}, {cm.group('status')}) "
                f"tree=({it['content']!r}, {it['status']})"
            )

    # P7: 父项可以整体标"进行中"(表示该组在做)，但**叶子项**最多一项 进行中，
    # 且当 current 标为 进行中 时，它必须是那个叶子项。
    parent_ids = {_parent_of(it["id"]) for it in items if it["dash"]}
    leaf_doing = [it["id"] for it in items
                  if it["status"] == "进行中" and it["id"] not in parent_ids]
    if len(leaf_doing) > 1:
        errors.append(f"P7: 叶子项最多一项 进行中，实际: {leaf_doing}")
    if cm.group("status") == "进行中" and current_id not in leaf_doing:
        errors.append(f"P7: current 标 进行中，但叶子进行中项是 {leaf_doing or '（无）'}")
    if cm.group("status") not in ("待做", "进行中"):
        errors.append(f"P7: current item 状态只能是 待做/进行中，实际 {cm.group('status')}")

    # P5
    tops = {it["id"] for it in items if not it["dash"]}
    for it in items:
        if it["dash"]:
            parent = _parent_of(it["id"])
            if not parent or parent not in tops:
                errors.append(f"P5: 子项 {it['id']} 缺少父项 {parent}（父项须为顶层项）")

    return errors


def main() -> int:
    ap = argparse.ArgumentParser(description="校验 PLAN.md 计划树格式")
    ap.add_argument("--quiet", action="store_true", help="只输出错误")
    args = ap.parse_args()

    if not PLAN.exists():
        print(f"❌ 缺少 {PLAN}", file=sys.stderr)
        return 1

    errors = check(PLAN.read_text(encoding="utf-8"))
    if errors:
        print("❌ PLAN.md 校验失败:", file=sys.stderr)
        for e in errors:
            print(f"   - {e}", file=sys.stderr)
        return 1

    if not args.quiet:
        items = _items(PLAN.read_text(encoding="utf-8"))
        print(f"✅ PLAN.md 通过 ({len(items)} 个计划项)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
