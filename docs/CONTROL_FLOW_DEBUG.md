# ControlFlow 调试分析记录

> 创建时间: 2026-05-26
> 更新: 2026-05-26 (修复完成)

---

## 问题修复状态

### Issue 1: always_comb + case 语句条件未提取 ✅ 已修复

**根因**: `StatementCollectorVisitor.visit_case_statement` 使用语义 `items` (ItemGroup)，但 ItemGroup 不包含 case item 条件信息 (0:, 1:, default:)。条件信息只存在于语法树 (syntax items) 中。

**修复方案**:
1. 修改 `visit_case_statement` 始终优先使用 syntax items（包含条件信息）
2. 添加 `_get_case_selector()` 提取 case selector 表达式
3. 添加 `_get_case_item_condition()` 提取 case item 条件值
4. 添加 `_expr_to_string()` 处理 `LiteralExpressionSyntax` 和 `IntegerVectorExpressionSyntax`

**验证**:
```bash
# 修复后输出
top.a → top.y: condition='sel == 0'
top.b → top.y: condition='sel == 1'
```

---

### Issue 2: 三元操作符条件未提取 ✅ 已修复

**根因**: 连续赋值边创建代码未处理 `ConditionalOp` (三元运算符)，没有提取条件表达式。

**修复方案**:
1. 在 `DriverExtractor` 添加 `_extract_ternary_condition()` 方法提取三元条件
2. 修改连续赋值边创建，添加 `condition=ternary_condition` 参数

**验证**:
```bash
# 修复后输出
top.en → top.y: kind=DRIVER, condition='en'
top.d → top.y: kind=DRIVER, condition='en'
0 → top.y: kind=DRIVER, condition='en'
```

**注意**: 三元操作符的条件提取还有改进空间。当前实现将条件同时应用于所有分支（en, d, 0），但语义上:
- `d → y` 条件应该是 `en` (true branch)
- `0 → y` 条件应该是 `!en` (false branch)

这是 `_get_all_signals` 设计的限制，需要进一步改进。

---

### Issue 3: 输出 `→` 空 ✅ 已修复

**根因**: CLI 用 `edge.to` 但字段名是 `edge.dst`。

**修复**: 修正为 `edge.get("dst", "")`

---

## 修改的文件

### src/trace/core/visitors/statement_collector_visitor.py
- `visit_case_statement`: 优先使用 syntax items，提取条件上下文
- `_get_case_selector()`: 新增方法
- `_get_case_item_condition()`: 新增方法
- `_expr_to_string()`: 新增 `LiteralExpressionSyntax` 和 `IntegerVectorExpressionSyntax` 处理

### src/trace/core/graph_builder.py
- `_extract_ternary_condition()`: 新增方法
- 连续赋值边创建: 添加 `condition=ternary_condition` 参数

### sim/tests/integration/test_complex_conditions.py
- `test_case_simple`: 更新期望值为 3 个驱动源 (包含 default case 的 0)

---

## 已知限制

### 三元操作符条件粒度
当前对三元操作符 `assign y = en ? d : 0;` 的处理：
- 所有分支 (en, d, 0) 都标记相同的条件 `en`
- 理想情况下:
  - `d → y` 条件应为 `en` (true branch)
  - `0 → y` 条件应为 `!en` (false branch)
  - `en → y` 不应存在 (en 是条件，不是驱动源)

这需要修改 `_get_all_signals` 来区分条件信号和驱动信号。

---

## 测试结果

```bash
cd ~/my_dv_proj/sv_query
python -m pytest sim/tests/ -v
# ================== 845 passed, 1 skipped, 1 warning ==================
```
