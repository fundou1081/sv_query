# Iteration 316: 宏/动态拼接函数条件核查（PLAN P20.1）

**Metadata**:
- **Iteration #**: 316
- **Task Tree Level**: L2（PLAN `P20.1`）
- **Created**: 2026-10-29 GMT+8
- **Author**: 方豆 / AI 助手（方豆: "再看看宏 动态拼接这里"）
- **Outcome**: ✅ 完成（宏/令牌拼接已覆盖；补 DPI/interface 两个真缺口；2585 passed）

## 🔎 先核查：哪些“动态”其实是编译期展开

SystemVerilog 没有运行期函数名；所谓“动态拼接”实际是预处理/作用域：

| 写法 | 实测 |
|---|---|
| `` `define FN f `` + ``if (`FN(a))`` | ✅ 条件文本 `f`，已标 unknown |
| `` `define CALL(x) f(x) `` | ✅ |
| 宏令牌拼接声明 `` `DECL(f) `` | ✅ |
| `` `ifdef `` 选择 f/g | ✅（语义树只留选中分支） |
| package 限定 `p::f(a)` / `import p::*` | ✅（iter_315 已修） |
| 层次函数 `u.f(a)` | ✅（条件文本 `f`，按函数名匹配） |

结论：宏展开/令牌拼接**不需要新机制**；补了回归测试锁住。

## 🐛 核查中发现的两个真缺口

### 1. DPI import 函数

```systemverilog
import "DPI-C" function int f(input int x);
if (f(a)) y = b;
```

DPI 函数不在 module body/package 里，而在 **compilation unit（`$unit`）**：
`SubroutineSymbol f` + `hierarchicalPath="f"`。旧收集逻辑看不到 → y 仍是 bus。
修：遍历 `compilation.getCompilationUnits()` + `visit` 收集。

### 2. interface 函数

```systemverilog
interface ifc; function bit f(...); ... endfunction endinterface
if (i.f(a)) y = b;
```

interface 函数不在 module body/package/CU 的常规 body 中。
修：`root.visit` 全量兜底收集 `SubroutineSymbol(Function)`。
实测 verilog-axi 177k symbols 只增加 **0.12s**（建图 24.7s），可接受。

## 📊 效果

| 写法 | 修复前 | 修复后 |
|---|---|---|
| DPI `if (f(a))` | bus / false | **unknown / true** |
| interface `if (i.f(a))` | bus / false | **unknown / true** |
| 宏 alias / wrapper / token paste / ifdef | 已正确 | 回归测试锁住（仍正确） |
| `$clog2(a)` 系统函数 | 不标（有意） | 不标（见边界） |

## 🧪 测试

`test_trace_function_call.py` +6（共 18）：
宏 alias / 宏调用包装 / 令牌拼接声明 / ifdef 选择 / DPI / interface。
全量：2579 → **2585 passed / 0 failed**。

## ✅ 验证

- check_docs / check_plan / check_cli_layers / check_except_pass 全绿
- 图 key v8 → **v9**（新增 DPI/interface 函数标记）

## 📌 边界

- **系统函数**（`$clog2`/`$bits` 等）不标 `function_call`：多数是 elaboration 常量/内建，
  统一标 unknown 会产生大量误报；`$random` 类运行期系统函数暂未建模
- 运行期**函数名**在 SV 中不存在；宏/`ifdef` 已在编译期解析
- 仍不做 inline

## 🔗 相关

- 计划: [PLAN.md P20.1](../../../PLAN.md)
- 前序: [iter_315 函数条件](iter_315_function_condition.md)
