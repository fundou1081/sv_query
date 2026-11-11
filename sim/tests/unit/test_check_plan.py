"""[iter_279] PLAN.md 计划树校验器测试。

方豆要求：全局唯一计划树管理所有代码修改计划；本测试保证校验器本身可靠。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "tools"))

from check_plan import check  # noqa: E402

VALID = """# PLAN

## 当前项

current item : P0.1 图快照基线工具 <待做>

## 计划树

P0 建图层结构化拆分 <进行中>
-- P0.1 图快照基线工具 <待做>
-- P0.2 拆巨型函数 <待做>
"""


def test_valid_plan_passes():
    assert check(VALID) == []


def test_missing_current_fails():
    errs = check(VALID.replace("current item : P0.1 图快照基线工具 <待做>\n", ""))
    assert any(e.startswith("P1") for e in errs)


def test_current_must_match_tree():
    text = VALID.replace(
        "current item : P0.1 图快照基线工具 <待做>",
        "current item : P0.1 图快照基线工具 <进行中>",
    )
    errs = check(text)
    assert any(e.startswith("P2") for e in errs), errs


def test_duplicate_id_fails():
    text = VALID + "-- P0.1 重复项 <待做>\n"
    errs = check(text)
    assert any(e.startswith("P4") for e in errs), errs


def test_orphan_sub_item_fails():
    text = VALID + "-- P9.1 没有父项 <待做>\n"
    errs = check(text)
    assert any(e.startswith("P5") for e in errs), errs


def test_bad_status_fails():
    text = VALID.replace("-- P0.2 拆巨型函数 <待做>", "-- P0.2 拆巨型函数 <快好了>")
    errs = check(text)
    assert any(e.startswith("P3") or e.startswith("P6") for e in errs), errs


def test_two_leaf_in_progress_fails():
    text = VALID.replace(
        "current item : P0.1 图快照基线工具 <待做>",
        "current item : P0.1 图快照基线工具 <进行中>",
    ).replace("-- P0.1 图快照基线工具 <待做>", "-- P0.1 图快照基线工具 <进行中>").replace(
        "-- P0.2 拆巨型函数 <待做>", "-- P0.2 拆巨型函数 <进行中>"
    )
    errs = check(text)
    assert any(e.startswith("P7") for e in errs), errs


def test_current_in_progress_must_be_leaf_doing():
    text = VALID.replace(
        "current item : P0.1 图快照基线工具 <待做>",
        "current item : P0.1 图快照基线工具 <进行中>",
    )
    errs = check(text)
    assert any(e.startswith("P7") for e in errs), errs


def test_all_done_allows_completed_current():
    """全部完成时 current 可标 已完成 —— 但仍有未完成项时必须报错。"""
    text = VALID.replace("current item : P0.1 图快照基线工具 <待做>",
                         "current item : P0.2 拆巨型函数 <已完成>")
    text = text.replace("-- P0.1 图快照基线工具 <待做>", "-- P0.1 图快照基线工具 <已完成>")
    text = text.replace("-- P0.2 拆巨型函数 <待做>", "-- P0.2 拆巨型函数 <已完成>")
    text = text.replace("P0 建图层结构化拆分 <进行中>", "P0 建图层结构化拆分 <已完成>")
    assert check(text) == []


def test_completed_current_with_unfinished_item_fails():
    text = VALID.replace("current item : P0.1 图快照基线工具 <待做>",
                         "current item : P0.1 图快照基线工具 <已完成>")
    text = text.replace("-- P0.1 图快照基线工具 <待做>", "-- P0.1 图快照基线工具 <已完成>")
    errs = check(text)
    assert any(e.startswith("P7") for e in errs), errs


def test_real_plan_file_passes():
    plan = Path(__file__).resolve().parents[3] / "PLAN.md"
    assert plan.exists(), "PLAN.md 必须存在（全局唯一计划树）"
    assert check(plan.read_text(encoding="utf-8")) == []


# --- [P164] 计划树校验器加固：不可见项 / 字母后缀 / 多层父项 -----------------


def test_deep_dash_indent_is_rejected():
    """3 个以上短横线的项不会被解析；必须报 P9，而不是静默跳过。"""
    text = VALID + "---- P0.1.1 深缩进项 <待做>\n"
    errs = check(text)
    assert any(e.startswith("P9") for e in errs), errs


def test_letter_suffix_id_allowed():
    """P158.11.2a / 2b 这类拆分项是合法 id。"""
    text = """# PLAN

current item : P0.2a 拆分项 <待做>

P0 父项 <进行中>
-- P0.2a 拆分项 <待做>
"""
    assert check(text) == []


def test_nested_parent_allowed():
    """父项可以是中间层（P0.1），不再要求必须是顶层项。"""
    text = """# PLAN

current item : P0.1.1 深项 <待做>

P0 顶层 <已完成>
-- P0.1 中层 <已完成>
-- P0.1.1 深项 <待做>
"""
    assert check(text) == []


def test_nested_parent_must_exist():
    text = """# PLAN

current item : P0.9.1 孤儿深项 <待做>

P0 顶层 <已完成>
-- P0.9.1 孤儿深项 <待做>
"""
    errs = check(text)
    assert any(e.startswith("P5") for e in errs), errs
