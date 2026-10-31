# Iteration 322: 运行期系统调用诚实标记（PLAN P26.2）

**Metadata**:
- **Iteration #**: 322
- **Task Tree Level**: L2（PLAN `P26.2`）
- **Created**: 2026-10-31 GMT+8
- **Author**: 方豆 / AI 助手（方豆: "回到主线任务"；第 3 项）
- **Outcome**: ✅ 完成（$random 等标记 + 修对象 repr 节点 id；2609 passed）

## 🎯 问题

P26 批准的第 3 项：`$random` 类运行期系统函数之前没有标记，结果看起来是确定值。

实测还发现一个更严重的问题：

```systemverilog
assign y = $random;
```

图上节点 id 是 **`<pyslang...SystemCallInfo object at 0x...>`**（对象 repr）：
- 每次构建地址不同 → 图不可复现；
- 缓存/基线不可比；
- fanin 返回的函数源不是一个可读信号。

根因：`ConversionExpression` 里包 `CallExpression`，系统调用的 `subroutine` 是
`SystemCallInfo`（没有 `.name`），旧分支 `return str(sub)` 把对象 repr 当名字。

## 🔧 实现

| 项 | 做法 |
|---|---|
| 节点 id | `get_signal` Conversion-Call 分支优先 `subroutine.name` / `subroutineName`；都没有返回 `None`，禁止对象 repr |
| 运行期集合 | `$random/$urandom/$urandom_range/$time/$stime/$realtime/$value$plusargs/$test$plusargs` |
| 识别 | 节点 id / 边 expression / condition / condition_chain |
| 传播 | DRIVER/CONNECTION/BRANCH/CASE/CLOCK/RESET 下游 + 位子树 |
| 输出 | node `runtime_system_call` + precision=unknown；signal 同名字段 + unknown |
| 持久化 | `SignalGraph._runtime_system_nodes` 进 to_dict/from_dict；图缓存 key **v11** |
| 不标 | `$clog2/$bits` 等 elaboration/常量内建 |

## 📊 效果

| 写法 | 修复前 | 修复后 |
|---|---|---|
| `assign y=$random` | node id 是对象 repr，precision=bit | `$random` 节点 + **runtime_system_call=true, unknown** |
| `if ($random) q=a` | q=bus | **unknown, runtime=true** |
| `z=y[3]` | bus/bit | **unknown, runtime=true**（位子树传播） |
| `$clog2(a)` | bus | bus，runtime=false（不误标） |
| `$urandom_range(...)` | bus | **unknown, runtime=true** |

## 🧪 测试

- 新增 `test_trace_runtime_system_call.py`（5）：$random 表达式/条件/位传播、$clog2 不标、$urandom_range
- 序列化测试 +1：`runtime_system_nodes` to_dict/from_dict
- 3 个 CLI golden **有意重生成**（新增 runtime_system_call 字段）
- 真实工程 smoke 全 PASS
- 全量：2603 → **2609 passed / 0 failed**

## 📌 边界

- 只覆盖常见运行期系统函数；`$fopen/$readmemh` 等副作用调用/DPI 不在集合
- 系统函数名集合是白名单，未知系统调用不标（宁可漏，不误标常量内建）
- signal 级只标 bool；不区分具体是哪个系统函数（节点 id 可见）
- `$random` 作为时钟/复位等极端用法暂未单测

## 🔗 相关

- 计划: [PLAN.md P26.2](../../../PLAN.md)
- 前序: [iter_321 遍历完整性](iter_321_traversal_integrity.md)
