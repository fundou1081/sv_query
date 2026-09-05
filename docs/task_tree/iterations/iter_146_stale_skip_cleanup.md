# Iteration 146: coverage_generator stale skip 测试清理

**Metadata**:
- **Iteration #**: 146
- **Task Tree Level**: L3 (测试债务)
- **Parent Task**: 长 skip 测试深挖 (iter_145 教训延续)
- **Created**: 2026-09-05 GMT+8
- **Author**: AI 助手
- **Outcome**: ✅ 成功 (2 stale skip 测试移除, 路径已被新测试覆盖)

## 🎯 本次目标

方豆 "继续" → 清理长期 skip 测试债务 (iter_145 教训: 长 skip 挖真因)。
全量回归残留 2 个 coverage_generator skip:
`[V6.9] SignalExpressionVisitor 已删除，改用 _get_signal`。

## 🔬 实际结果

### 分析

2 个 skip 测试 (TestASTParsing.test_parse_via_real_pyslang_ast /
TestASTConditionExtraction.test_extract_via_real_pyslang_ast) 引用已删除的
syntax AST visitor 类 (SignalExpressionVisitor) — V6.9 架构演进删类后测试
被 @skip 搁置。验证其验证的路径是否已被覆盖:
- AST 提取路径 (`_extract_atomics_from_ast` → `_extract_signals_from_expr`):
  已被 test_extract_ast_path_preferred (FakeAST, 走 AST 不 fallback) +
  mock adapter 测试覆盖
- visitor.extract(syntax AST) 的 syntax→语义演进 = 架构决策 (V6.9),
  测试应随删

### 处置

用 AST 级精确删除 2 个 stale 测试方法 (含 @skip 装饰器), 注释引用保留。
coverage_generator: 2 skip → **0 skip, 177 passed**。

## 📌 状态

- ✅ 2 stale skip 测试移除 (路径已被新测试覆盖, 无覆盖弱化)
- ✅ coverage_generator 套件 177 passed / 0 skip
- 无代码改动 (纯测试清理)
