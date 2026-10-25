"""[iter_282 / PLAN P0.3] GraphBuilder 声明式 pipeline 的单元测试。"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))

from trace.core.builder.graph_pipeline import GraphPipeline, Stage  # noqa: E402


def _stage(name, log=None, requires=(), provides=()):
    calls = log if log is not None else []

    def run():
        calls.append(name)

    return Stage(name, run, requires=frozenset(requires), provides=frozenset(provides)), calls


def test_order_follows_dependencies():
    a, _ = _stage("a", provides={"x"})
    b, _ = _stage("b", requires={"x"}, provides={"y"})
    c, _ = _stage("c", requires={"y"})
    assert GraphPipeline([a, b, c]).order == ["a", "b", "c"]


def test_declaration_order_breaks_ties():
    """无依赖关系的 stage 保持声明顺序（稳定排序）。"""
    first, _ = _stage("first", provides={"a"})
    second, _ = _stage("second", provides={"b"})
    assert GraphPipeline([second, first]).order == ["second", "first"]


def test_reordering_source_does_not_change_result():
    """声明顺序与依赖冲突时，依赖优先。"""
    late, _ = _stage("late", provides={"y"})
    depends, _ = _stage("depends", requires={"y"})
    early, _ = _stage("early", provides={"x"})
    # depends 声明在 late 之前，但仍必须排在其后
    assert GraphPipeline([depends, late, early]).order == ["late", "depends", "early"]


def test_missing_provider_raises():
    bad, _ = _stage("needs_missing", requires={"nope"})
    with pytest.raises(ValueError, match="未声明产出"):
        GraphPipeline([bad])


def test_cycle_raises():
    a, _ = _stage("a", requires={"b"}, provides={"a"})
    b, _ = _stage("b", requires={"a"}, provides={"b"})
    with pytest.raises(ValueError, match="循环依赖"):
        GraphPipeline([a, b])


def test_duplicate_names_raise():
    a, _ = _stage("dup", provides={"x"})
    b, _ = _stage("dup", provides={"y"})
    with pytest.raises(ValueError, match="重复"):
        GraphPipeline([a, b])


def test_run_executes_in_order_once():
    log: list[str] = []
    a, _ = _stage("a", log, provides={"x"})
    b, _ = _stage("b", log, requires={"x"})
    executed = GraphPipeline([a, b]).run()
    assert executed == ["a", "b"]
    assert log == ["a", "b"]
