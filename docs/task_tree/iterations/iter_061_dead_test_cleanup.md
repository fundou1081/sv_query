# Iteration 061: 废弃测试核实与清理 (removed_features + sim/ 根 golden)

**Metadata**:
- **Iteration #**: 061
- **Task Tree Level**: L2
- **Parent Task**: 测试地图 (TEST_MAP.md) 筛选后的清理
- **Created**: 2026-08-29 GMT+8
- **Author**: AI 助手
- **Outcome**: ✅ 成功 (删除 14 个废弃/孤儿测试文件, 零影响)

## 🎯 本次目标

方豆 "先做核实清理这一步" — 核实并清理 TEST_MAP.md 标注的两个问题区域:
1. `sim/tests/usage/removed_features/` (11 文件 236 测试, 全 skip)
2. `sim/` 根 3 个 golden 孤儿 (不在 pytest testpaths)

## 📊 当前状态 / 预期结果

- removed_features: V6.9 移除 SignalExpressionVisitor 后的测试尸体, 模块级 pytestmark.skip
- sim/ 根 golden: 早期 (铁律7/13) 测试, 不在收集范围
- 预期: 核实无活引用后删除, 零回归

## 🔬 实际结果

### 1. 核实结论

**removed_features (11 文件)**:
- 全部 11 文件有**模块级** `pytestmark = pytest.mark.skip` (reason: V6.9 removed)
- 无代码引用 (仅历史文档 SIGNAL_EXPRESSION_VISITOR_TEST_STATUS.md /
  RANDOMIZE_COVERGROUP.md 提及)
- **额外发现**: `pytest --collect-only` 报 **11 个收集错误**
  (ModuleNotFoundError: trace.core — 文件直接 import 但缺 sys.path),
  删除后这些收集错误一并消失

**sim/ 根 golden (3 文件)**:
- test_golden.py / test_golden_cases.py / test_gold_comprehensive.py
- 仅 docs/archive/ 归档文档引用 (非活引用)
- 不在 pyproject testpaths=["sim/tests"] → 从未被 pytest 收集

### 2. 清理

- `git rm -r sim/tests/usage/removed_features/` (11 测试 + __init__.py)
- `git rm sim/test_golden.py sim/test_golden_cases.py sim/test_gold_comprehensive.py`
- 更新 docs/TESTING.md (删 test_signal_expression_visitor_*.py 引用,
  替换为 signal_normalizer/signal_tracer)
- 更新 docs/TEST_MAP.md (清理状态标注)

### 3. 验证 (零影响)

- usage 收集: **298 tests collected** (11 个收集错误消失)
- unit+cli 回归: **1435 passed + 24 failed** (与清理前完全一致, 24 = 沙箱 cache artifact)

## 💡 关键发现 / 关键技术 / 决策

1. **"全 skip"≠"无害"**: removed_features 虽 skip 但仍被 pytest 收集 (import 执行),
   且因缺 sys.path 产生 11 个收集错误 — 垃圾测试不但占地方还污染收集。
2. **git rm 而非物理删除**: 历史可恢复 (git log/blame), 删除符合"废弃测试不该留在
   收集路径"的原则。
3. **删除前核实三件事**: skip 完整性 / 外部引用 / 收集影响 — 全部确认后才动手。

## 📌 后续 (可选)

- scripts/debug/ 2 个探索脚本 (0 测试函数) — 保留 (可能调试有用)
- docs/openchip_qa_test.py — QA 脚本, 保留
- TEST_MAP.md 中 127 个无 docstring 文件 — 可后续补 docstring 提升可维护性
