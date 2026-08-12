"""unit test for sim.tests.manual.extract_target

[Plan 2026-08-12] 测核心 extract_target() 函数的语义, 不依赖完整 tracer 链.

覆盖:
- 顶层 module (简单 fixture)
- 顶层 wrapper (hierarchical fixture, 验证"取最后一个")
- #() 参数语法
- FileNotFoundError 处理
- 不存在 topInstances 时的 fallback (mock)
"""

from __future__ import annotations

import sys
from pathlib import Path

# 让 unit test 能找到 sim.tests.manual (不在 sys.path)
_REPO_ROOT = Path(__file__).resolve().parents[3]
_MANUAL = _REPO_ROOT / 'sim' / 'tests' / 'manual'
_SRC = _REPO_ROOT / 'src'
for p in (_MANUAL, _SRC):
    p_str = str(p)
    if p_str not in sys.path:
        sys.path.insert(0, p_str)

import pytest

from sim.tests.manual.extract_target import extract_target

FIX_DIR = _REPO_ROOT / 'sim' / 'tests' / 'fixtures' / 'golden_mini'


# ---- 顶层 module 提取正确性 ----

@pytest.mark.parametrize('fixture_file,expected_target', [
    # 简单 case: 一个 module, topInstances 长度 = 1
    ('golden_dataflow_1_op.sv', 'simple_op'),
    ('golden_dataflow_2_const.sv', 'with_const'),
    ('golden_dataflow_3_slice.sv', 'with_trunc'),
    ('golden_dataflow_5_combined.sv', 'combined'),
    # 带 #() 参数的 module
    ('golden_dataflow_27_generate_loop.sv', 'generate_loop'),
    # 4-module 层级: topInstances 长度 = 4, 取最后一个 = top wrapper
    ('golden_dataflow_26_hier_levels.sv', 'golden_hier_top'),
    # 其他复杂 case
    ('golden_dataflow_28_func_bitmix.sv', 'golden_func_bitmix'),
])
def test_extract_target_basic(fixture_file, expected_target):
    fix = FIX_DIR / fixture_file
    if not fix.exists():
        pytest.skip(f'fixture 缺失: {fix}')
    target = extract_target(fix)
    assert target == expected_target, (
        f'{fixture_file}: 期望 {expected_target}, 实际 {target}'
    )


# ---- 错误处理 ----

def test_extract_target_file_not_found(tmp_path):
    fake = tmp_path / 'nonexistent.sv'
    with pytest.raises(FileNotFoundError, match='SV file not found'):
        extract_target(fake)


# ---- 防御性 fallback ----

def test_extract_target_fallback_when_no_topinstances(tmp_path, monkeypatch):
    """当 root 没有 topInstances 属性时, 返 fix.stem (不 crash)"""
    fix = tmp_path / 'foo.sv'
    fix.write_text('module foo(); endmodule\n')

    # monkeypatch compile_sources 让它返一个没有 topInstances 的 root
    _ext_module = sys.modules["sim.tests.manual.extract_target"]; ext_mod = _ext_module

    class _FakeRoot:
        pass  # 没有 topInstances

    def fake_compile(sources):
        return (None, _FakeRoot())

    monkeypatch.setattr(ext_mod, 'compile_sources', fake_compile)
    target = extract_target(fix)
    assert target == 'foo', f'fallback 应返 stem, 实际 {target}'


def test_extract_target_fallback_when_all_bad_names(tmp_path, monkeypatch):
    """当 topInstances 全是 pyslang binary garbage 兜底名时, 返 stem"""
    fix = tmp_path / 'bar.sv'
    fix.write_text('module bar(); endmodule\n')

    _ext_module = sys.modules["sim.tests.manual.extract_target"]; ext_mod = _ext_module

    class _FakeRoot:
        def __init__(self):
            self.topInstances = [object(), object()]  # 任意 2 个, get_module_name 返 _bad_

    # 让 get_module_name 返 _bad_ 来触发 filter (patch 在 ext_mod 的 namespace)
    def fake_get_module_name(self, module):
        return '_bad_'

    monkeypatch.setattr(ext_mod.SemanticAdapter, 'get_module_name', fake_get_module_name)

    def fake_compile(sources):
        return (None, _FakeRoot())

    monkeypatch.setattr(ext_mod, 'compile_sources', fake_compile)
    target = extract_target(fix)
    assert target == 'bar', f'fallback 应返 stem, 实际 {target}'


# ---- Python 类型 ----

def test_extract_target_accepts_str_path():
    """应接受 str 而不只是 Path"""
    fix = FIX_DIR / 'golden_dataflow_1_op.sv'
    if not fix.exists():
        pytest.skip(f'fixture 缺失: {fix}')
    target = extract_target(str(fix))
    assert target == 'simple_op'


def test_extract_target_accepts_path_object():
    fix = FIX_DIR / 'golden_dataflow_2_const.sv'
    if not fix.exists():
        pytest.skip(f'fixture 缺失: {fix}')
    target = extract_target(fix)
    assert target == 'with_const'