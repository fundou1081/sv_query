# Bug 优先级清单（2026-05-22）

当前状态：97 失败，702 通过  
目标：修复所有 bug，恢复测试通过率

---

## P0 — 阻塞性基础设施 Bug（一次修完可解锁多个测试）

| # | Bug | 文件 | 错误类型 | 影响 |
|---|-----|------|---------|------|
| 1 | `semantic_adapter.py:177` `UnboundLocalError: path_str` | `src/trace/core/semantic_adapter.py` | 变量作用域 bug，generate 实例遍历时 path_str 未定义 | 6 个测试 |
| 2 | `test_generate_if.py` `_make_tracer` 传了 `SyntaxTree` 对象 | `sim/tests/regression/test_generate_if.py` | 新 API 应接收 source string，但传了 SyntaxTree | 3 个测试 |

---

## P1 — Fixture 语法仍有问题（12 个 CompilationError）

| # | 测试 | 文件 | 根因 |
|---|------|------|------|
| 3 | 8 个 `test_advanced_features` 测试 | `sim/tests/regression/test_advanced_features.py` | fixture 里引用未定义的 module/task/interface（如 `my_task`、`my_interface`）|
| 4 | `test_modport_direction` | `sim/tests/regression/test_cross_module_tracking.py` | SV fixture 编译不过（interface/modport 语法问题）|
| 5 | `test_four_level_hierarchy` | `sim/tests/regression/test_cross_module_tracking.py` | SV fixture 编译不过 |
| 6 | `test_three_level_hierarchy` | `sim/tests/regression/test_cross_module_tracking.py` | SV fixture 编译不过 |
| 7 | `test_task_multiple_stmts` | `sim/tests/regression/test_task_function.py` | 参数名 `dout1, dutput2` 笔误（应为 `a, b`）|

---

## P2 — 逻辑/功能缺失（AssertionError，SV 编译通过但行为不对）

| # | Bug | 影响 | 说明 |
|---|-----|------|------|
| 8 | constraint 解析返回空（8 tests）| `test_constraint_derivative` 8 个 | 约束块/表达式节点未正确建立，期望 len(classes)=1 但实际为 0 |
| 9 | modport_dir 属性为 None（4 tests）| `test_modport_direction` 4 个 | `TraceNode.modport_dir` 字段没有正确设置 |
| 10 | 端口/节点 Graph 中不存在（8 tests）| `test_cross_module_tracking` 多个 | 端口解析、generate 实例、路径解析未完整实现 |
| 11 | concat/replication 结果缺失（2 tests）| `test_concat_and_hierarchy`, `test_replication` | 拼接/复制操作结果数量不对（实际 0，期望 ≥1）|
| 12 | ValueError: Unsupported signal type | `test_function_in_expression` | `ExpressionKind.Case` 在信号提取中不支持 |

---

## 错误类型分布总览

| 错误类型 | 数量 | 说明 |
|---------|------|------|
| CompilationError: Elaboration errors | 12 | fixture SV 语法问题（P1）|
| AssertionError: 0 != 1 | 8 | constraint 解析为空（P2-8）|
| UnboundLocalError: path_str | 6 | semantic_adapter bug（P0-1）|
| TypeError: fromText incompatible | 3 | test_generate_if.py API 用错（P0-2）|
| AssertionError: node None | 4 | modport_dir 未设置（P2-9）|
| AssertionError: 节点不存在 | 8 | 端口/generate/路径解析问题（P2-10）|
| ValueError: Unsupported signal | 1 | ExpressionKind.Case 不支持（P2-12）|

---

## 建议执行顺序

1. **P0-1**: `semantic_adapter.py:177` — UnboundLocalError path_str
2. **P0-2**: `test_generate_if.py` — _make_tracer 传参错误
3. **P1-3~7**: 修 5 处 fixture 语法问题（12 个测试）
4. **P2-8**: constraint 解析为空
5. **P2-9**: modport_dir 为 None
6. **P2-10**: 端口/节点 Graph 不存在
7. **P2-11**: concat/replication 结果缺失
8. **P2-12**: Unsupported signal type
---

## 2026-05-22 修复进度

### P0 ✅ 完成
- P0-1: semantic_adapter.py path_str UnboundLocalError → 已修复 (commit 3186525)
- P0-2: test_generate_if.py _make_tracer 传 SyntaxTree → 已修复 (commit 3186525)

### P1 ✅ 完成
- P1-3: test_advanced_features.py 8 个测试 fixture 语法 → 已修复 (commit fd22650)
- P1-4: test_cross_module_tracking.py modport_direction → 已修复 (commit fd22650)
- P1-5/6: test_cross_module_tracking.py hierarchy → 已修复 (commit fd22650)
- P1-7: test_task_function.py dutput2 笔误 → 已修复 (commit fd22650)

### 当前状态
- P0: 2/2 完成
- P1: 5/5 完成
- P2: 待处理（74 个失败测试）
- 测试结果: 74 failed, 725 passed（从 97 failed, 702 passed 改善）
