# Iteration 313: 函数调用诚实标记（PLAN P18.2）

**Metadata**:
- **Iteration #**: 313
- **Task Tree Level**: L2（PLAN `P18.2`）
- **Created**: 2026-10-29 GMT+8
- **Author**: 方豆 / AI 助手（方豆: "按顺序做1 2 3"）
- **Outcome**: ✅ 完成（函数调用 unknown 标记，不做 inline；2564 passed）

## 🎯 问题（实测）

```systemverilog
function automatic [7:0] f(input [7:0] x); f = x + 1; endfunction
assign y = f(a);
```

图上是伪信号：

```
a --(expr="f(a)")--> f --(expr="f")--> y
```

`fanin(z)` 返回 `{y[3], top.f, top.a}`，`top.f` 是 **SIGNAL、width=(1,0)**，
precision=`bus`，`coarse_fallback=false` —— agent 会把它当普通 1 位信号。

## 🔧 实现（只标记，不 inline）

| 项 | 做法 |
|---|---|
| 函数节点识别 | ① 语义 `SubroutineSymbol`（`subroutineKind=Function`）的 `hierarchicalPath` ② 边表达式 `f(...)` 且目标叶名匹配（兜底 package/外部函数） |
| 节点标记 | `extra["function_call"]=True`；node precision=`unknown` |
| 传播 | 沿 DRIVER/CONNECTION/BRANCH/CASE 下游 + 位子树（`y → y[3] → z`） |
| CLI 输出 | node `function_call`；signal `function_call`；precision 强制 `unknown` |
| 持久化 | `SignalGraph._function_nodes` 随 `to_dict/from_dict`；图缓存 key **v4**、AST cache **1.9** |

## 🐛 过程中发现的 2 个坑

1. **无参函数没有调用边**：`y = f() + a` 图上只有 `f -> y`（expr 空），
   纯边表达式检测漏掉 → 增加语义符号路径检测。
2. **图缓存没有 schema 版本**：`-v2-` 是固定段，旧图缺新 metadata 仍会被复用
   （本次实测无参函数标记被旧缓存吞掉）。已把图 key 提到 **v4**（旧缓存显式失效），
   AST cache 同步 1.9。

## 📊 效果

| 查询 | 修复前 | 修复后 |
|---|---|---|
| `fanin(y)` | `bus`, f 像普通信号 | **`unknown, function_call=true`**，f 节点 unknown |
| `fanin(z)`（`y[3]`） | bus（位节点分开建） | **unknown + function_call=true**（位子树传播） |
| `fanout(a)` | bus，f 普通 load | **unknown + function_call=true** |
| 无参 `f()` | 完全漏标 | **unknown + function_call=true** |
| 普通信号 | — | `function_call=false`（不变） |

## 🧪 测试

- 新增 `test_trace_function_call.py`（5）：带参/位查询/fanout/无参/普通信号
- 序列化测试 +1：`function_nodes` 进 `to_dict/from_dict`
- 3 个 CLI golden **有意重生成**（node 新增 `function_call` 字段）
- 全量：2558 → **2564 passed / 0 failed**

## ✅ 验证

check_docs / check_plan / check_cli_layers / check_except_pass 全绿。

## 📌 边界

- **不做 inline**（方豆明确第 4 项不做）：函数体内部数据流仍不可查；
  现在只是“不伪装成普通总线”
- 函数出现在**条件**里（`if (f(a))`）且图上没有调用结果节点时，可能只影响条件文本，
  不产生 function_call 节点
- package/外部函数靠边表达式兜底；完全无表达式的极端形态可能漏判

## 🔗 相关

- 计划: [PLAN.md P18.2](../../../PLAN.md)
- 前序: [iter_312 层次条件](iter_312_hierarchical_condition_scope.md)
