"""[P164] check_docs 计数基准提取的回归测试。

背景：原实现从**整份** INDEX.md 提取 `N passed/测试` 作为合法基准，
于是 INDEX 里一条历史条目 `2571 passed` 把 README 的旧数字"背书"了，
计数漂移检查恒过。基准必须只来自「当前基线」章节，且只认 `N passed`。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "tools"))

from check_docs import baseline_numbers  # noqa: E402

INDEX_WITH_HISTORY = """# INDEX

## 📌 当前基线 (单一真相源)

| 项 | 值 |
|---|---|
| 源码规模 | 137 文件 / 49,377 行 |
| 全量 (canonical) | **2678 passed / 0 failed** |
| 测试规模 | 378 测试文件 / 64,311 行 |

---

## 历史条目

| 文档 | 说明 |
|---|---|
| A_D_TEST | 8-task matrix；当时全量基线 2571 passed |
"""


def test_baseline_only_from_current_section():
    nums = baseline_numbers(INDEX_WITH_HISTORY)
    assert "2678" in nums
    assert "2571" not in nums, "历史条目不得成为基准（否则旧数字互相背书）"


def test_scale_counts_are_not_baseline():
    nums = baseline_numbers(INDEX_WITH_HISTORY)
    assert "378" not in nums, "`N 测试文件` 是规模计数，不是通过数"


def test_baseline_without_section_falls_back_to_whole_text():
    nums = baseline_numbers("全量: 2678 passed")
    assert nums == {"2678"}
