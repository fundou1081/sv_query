"""[iter_282 / PLAN P0.3] GraphBuilder 声明式 pipeline 的单元测试。"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))

from sv_query.trace.core.builder.graph_pipeline import GraphPipeline, Stage  # noqa: E402


def _stage(name, log=None, requires=(), provides=()):
    calls = log if log is not None else []

    def run():
        calls.append(name)

    return Stage(name, run, requires=frozenset(requires), provides=frozenset(provides)), calls


def _context_stage(name, log=None, requires=(), provides=()):
    calls = log if log is not None else []

    def run(context):
        calls.append((name, context))

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


def test_run_keeps_noarg_stage_call_shape():
    """无参 stage 仍以 `run()` 调用，不因新增 context 参数而改变。"""
    log: list[str] = []
    a, _ = _stage("a", log)
    executed = GraphPipeline([a]).run()
    assert executed == ["a"]
    assert log == ["a"]


def test_run_passes_context_to_context_stage():
    log: list[tuple[str, object]] = []
    context = object()
    a, _ = _context_stage("a", log)
    executed = GraphPipeline([a]).run(context)
    assert executed == ["a"]
    assert log == [("a", context)]


def test_run_defaults_context_to_none_for_context_stage():
    log: list[tuple[str, object]] = []
    a, _ = _context_stage("a", log)
    GraphPipeline([a]).run()
    assert log == [("a", None)]


def test_mixed_stages_receive_matching_arguments_and_keep_order():
    log: list[object] = []
    context = object()
    a, _ = _stage("a", log, provides={"x"})
    b, _ = _context_stage("b", log, requires={"x"}, provides={"y"})
    c, _ = _stage("c", log, requires={"y"})
    executed = GraphPipeline([a, b, c]).run(context)
    assert executed == ["a", "b", "c"]
    assert log == ["a", ("b", context), "c"]


def test_context_support_does_not_change_dependency_order():
    late, _ = _context_stage("late", provides={"y"})
    depends, _ = _context_stage("depends", requires={"y"})
    early, _ = _stage("early", provides={"x"})
    assert GraphPipeline([depends, late, early]).order == ["late", "depends", "early"]


def test_duplicate_names_still_raise_with_context_stages():
    a, _ = _context_stage("dup", provides={"x"})
    b, _ = _stage("dup", provides={"y"})
    with pytest.raises(ValueError, match="重复"):
        GraphPipeline([a, b])


def test_missing_dependency_still_raises_with_context_stages():
    bad, _ = _context_stage("needs_missing", requires={"nope"})
    with pytest.raises(ValueError, match="未声明产出"):
        GraphPipeline([bad])


def test_ambiguous_stage_signature_rejected_at_construction():
    """>1 个位置参数是非法形态；必须在 Stage 构造期报错，而不是运行期试探。"""

    def run(context, extra):
        raise AssertionError((context, extra))

    with pytest.raises(ValueError, match="0 或 1 个位置参数"):
        Stage("ambiguous", run)


def test_typeerror_in_stage_body_is_not_retried():
    """No runtime TypeError fallback: a body TypeError must surface once."""
    calls: list[str] = []

    def run() -> None:
        calls.append("ran")
        raise TypeError("body boom")

    with pytest.raises(TypeError, match="body boom"):
        GraphPipeline([Stage("boom", run)]).run()
    assert calls == ["ran"]


def test_required_keyword_only_stage_signature_rejected():
    def run(*, required):
        raise AssertionError(required)

    with pytest.raises(ValueError, match="keyword-only"):
        Stage("kwonly", run)


def test_uninspectable_stage_callable_rejected():
    class Uninspectable:
        @property
        def __signature__(self):
            raise ValueError("no signature")

        def __call__(self):
            raise AssertionError

    with pytest.raises(ValueError, match="无法内省签名"):
        Stage("opaque", Uninspectable())


def test_optional_positional_stage_receives_context_not_default():
    seen = []

    def run(flag="default"):
        seen.append(flag)

    context = object()
    GraphPipeline([Stage("opt", run)]).run(context)
    assert seen == [context]
