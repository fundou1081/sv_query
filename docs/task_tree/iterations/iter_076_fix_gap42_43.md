# Iteration 076: 修功能缺口 #42/#43 — task 调用站点完整形参映射

**Metadata**:
- **Iteration #**: 076
- **Task Tree Level**: L2
- **Parent Task**: C 组功能缺口修复 (方豆 "一起做" — A+B+C)
- **Created**: 2026-09-01 GMT+8
- **Author**: AI 助手
- **Outcome**: ✅ 完成 (#42/#43 已修 + 2 新测试 + 1 测试升级; #44 维持期望行为记录)

## 🎯 本次目标

修 EXTRACTION_COVERAGE #42/#43:
- #42: task 调用输出参数不生成 `din→dout` 边 (生成 EmptyArgument 占位边)
- #43: task 多语句体内部赋值不生成边

## 📊 当前状态 / 预期结果

- #42: `my_task(din, dout)` (task: `b = a`) 应生成 `din → dout` DRIVER 边
- #43: `my_task(din, mode, dout, flag)` (task: `b = a; f = a & m`) 应生成
  `din→dout`, `din→flag`, `mode→flag` 三条边 (按内部驱动关系独立映射),
  且**无** `mode→dout` 串扰边

## 🔬 实际结果

### ✅ 根因 (两处, 探针逐层确认)

**根因 1 — token 过滤器误吞 output 实参** (`_parse_invocation_call`):
```python
is_semantic = hasattr(expr, "symbol")
if not hasattr(expr, "expr") and not is_semantic:
    continue   # ← AssignmentExpression 无 .symbol 也无 .expr, 被当 syntax-tree token 跳过
```
探针确认: pyslang 语义 AST 的 AssignmentExpression (output 实参)
`symbol=False, expr=False` — 直接被 `continue` 丢弃, 永远到不了
`elif "Assignment" in kind_str:` 分支。

**根因 2 — flattener 拆分 Call 丢失 input 关联** (`statement_flattener`):
旧逻辑把 `my_task(din, dout)` 拆成 output 赋值元组, 只记录单个 input_sig,
多参数时关联错误, 且产生 `EmptyArgument → dout` 占位边。

### ✅ 修复 (三处, 均为根因层)

1. **statement_flattener**: Call 分支不再拆分, `result.append((expr, condition_chain))`
   保留整体, 交给 handle_invocation 做完整形参映射。
2. **always_extractor**: 新增 stmt 本身是 CallExpression (无 `.expr` 包装) 时
   直接 `h.handle_invocation(stmt, ...)` (探针确认 CallExpression `has_expr=False`)。
3. **function_extractor._parse_invocation_call**: token 过滤器放行 Assignment 类型;
   无条件 `continue` 改为仅 NamedArgument (name 非空 + arg_expr) 才 continue;
   Assignment 分支 LHS (NamedValue) 直接 `h.get_signal(lhs)` 提取实参。

**原 EmptyArgument 过滤** (always_extractor) 验证后不再需要 — 不拆 Call 后
该路径不触发, 已移除 (避免死代码)。

### ✅ 验证结果

- #42 单对: `my_task(din, dout)` → `din → dout` DRIVER 边, 无占位边
- #43 多参数: `din→dout`, `din→flag`, `mode→flag` 三条边, **无** `mode→dout`
- 命名实参 `.b(dout), .a(din)` 与位置调用等价 (语义 AST 已规范化)
- 测试: test_task_function.py 升级 test_task_output_param (占位边断言 → 真边
  `din→dout` + 无 EmptyArgument), 新增 TestTaskMultiParamExpansion 2 测试
  (位置/命名混合)。7 passed
- 回归: **766 passed** (764 + 2 新), unit 套件无新增失败
- ruff clean

## 💡 关键发现 / 决策

1. **pyslang 语义 AST 的 AssignmentExpression 无 `.symbol` 也无 `.expr`** —
   是 #42 被吞的真正入口, 不是 `.name` 为空的问题 (iter_075 判断部分修正:
   `.name` hasattr 为 False, 不是空字符串)。
2. **命名实参由语义 AST 规范化为位置形式** — `.b(dout), .a(din)` 展开为
   按声明序的 [a←din, b←dout], 无需额外分支。
3. **`h.get_signal` 对 NamedValue lhs 直接可用** — 不需要 adapter fallback
   (移除 silent fallback, 符合纪律)。
4. **#44 DPI 维持 iter_075 结论**: 函数体外部不可见, "调用无边"是正确行为。

## 📌 状态

- #42 ✅ / #43 ✅ / #44 🚫 (期望行为, 记录不修)
- 提交: statement_flattener + always_extractor + function_extractor +
  test_task_function + EXTRACTION_COVERAGE
