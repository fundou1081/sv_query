# Iteration 315: 函数条件诚实标记（PLAN P19.1）

**Metadata**:
- **Iteration #**: 315
- **Task Tree Level**: L2（PLAN `P19.1`）
- **Created**: 2026-10-29 GMT+8
- **Author**: 方豆 / AI 助手（方豆: "函数出现在条件里且图上无结果，这个要改一下"）
- **Outcome**: ✅ 完成（条件/时钟里的函数也能标 unknown；2579 passed）

## 🎯 问题

P18.2 只从**函数结果节点**识别函数；函数只出现在条件里时，图上可能没有 `top.f`：

```systemverilog
if (f(a)) y = b; else y = c;
case (f(a)) ...
assign y = f(a) ? b : c;
```

实测三个叠加问题：

1. `get_signal` 没有 `CallExpression` 分支 → 条件文本变成
   `"Expression(ExpressionKind.Call)"`，函数名直接丢失。
2. 即使条件文本是 `f > 0`，`function_names` 只用于结果节点；条件目标 `y` 不标。
3. `always_ff @(posedge f(a))` 的时钟提取只认 NamedValue → **CLOCK 边整个丢失**。

## 🔧 修复

| 位置 | 改动 |
|---|---|
| `get_signal` | 新增 Call/Invocation 分支 → 返回函数名（`f`），条件文本不再占位 |
| `_extract_clock_from_event_ctrl` | Call 当时钟 → 返回函数名（`f(a)` → `f`），恢复 CLOCK 边 |
| `_mark_function_calls` | 收集 module + **package** 函数名；扫条件的 condition/effective/condition_chain，命中已知函数名 → 目标标 `function_call` |
| 传播 | 函数标记沿 DRIVER/CONNECTION/BRANCH/CASE **和 CLOCK/RESET** 下游 + 位子树 |
| 防误报 | 同 module 存在同名**真实信号**节点时跳过（跨 module 函数同名不误报） |
| 缓存 | 图 key **v7**（旧 v6 图缺条件函数标记） |

## 📊 效果

| 写法 | 修复前 | 修复后 |
|---|---|---|
| `if (f(a)) y=...` | `bus`，function_call=false | **unknown, function_call=true**（图上仍无 f 节点） |
| `if (f(a) > 0)` | bus | **unknown, function_call=true** |
| `f(a) ? b : c` | bus | **unknown, function_call=true** |
| `case (f(a))` | bus | **unknown, function_call=true** |
| `always_ff @(posedge f(a))` | **无 CLOCK 边**，bus | **unknown**，CLOCK 边恢复 |
| `package p; f(); if(f(a))` | bus | **unknown**（package 函数名也收集） |
| 其它 module 有函数 f；top 的 f 是真实信号 | — | `function_call=false`（不误报） |

## 🐛 过程中发现

1. 条件里的裸 Call 被 `get_signal` 变成 `Expression(...)` 占位（不是函数名）。
2. 函数作 clock 时 `_extract_clock_from_event_ctrl` 只认 symbol，CLOCK 边丢失。
3. package 函数 `hierarchicalPath` 是 `p::f`，按 `.` 取叶名会得到 `p::f`，需再按 `::` 切。

## 🧪 测试

`test_trace_function_call.py` +7（共 12）：
if 条件 / 比较条件 / ternary / case / 函数作 clock / 同名真实信号防误报 / package 函数。
全量：2572 → **2579 passed / 0 failed**。

## ✅ 验证

check_docs / check_plan / check_cli_layers / check_except_pass 全绿。

## 📌 边界

- **仍不做 inline**：函数体数据流不可查，只保证不伪装成精确结果
- 函数名检测基于 module/package 语义符号；完全动态/宏拼接的函数名可能漏
- 条件文本里的层次化显示仍可能退化（P18.1 已保证 dynamic 解析，不改显示文本）

## 🔗 相关

- 计划: [PLAN.md P19.1](../../../PLAN.md)
- 前序: [iter_313 函数诚实标记](iter_313_function_call_honesty.md)
