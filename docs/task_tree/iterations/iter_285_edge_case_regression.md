# Iteration 285: 边缘场景 drive-load 回归（PLAN P2.1）

**Metadata**:
- **Iteration #**: 285
- **Task Tree Level**: L2（[L1_edge_case_regression](../tasks/L1_edge_case_regression.md) / PLAN `P2.1`）
- **Created**: 2026-10-25 GMT+8
- **Author**: 方豆 / AI 助手（方豆: "继续"）
- **Outcome**: ✅ 完成（15 个边缘用例 + 2 个真 bug 修复；2348 passed）

## 🎯 目标

iter_278 的结论是"主干稳、边缘薄"。本迭代给 5 类边缘形态补回归，
并修掉过程中暴露的真实缺陷。

## 🐛 暴露并修复的 2 个缺陷

### 1. interface 设计直接崩溃（高严重度）

`GraphBuilder._bridge_interface_member_signals()` 在补"顶层未引用的 interface 成员"占位节点时：

```python
TraceNode(id=..., name=..., module=..., kind=NodeKind.SIGNAL)   # 漏 width
```

`TraceNode.width` 是必填字段 → **任何带 interface 的设计构建时 TypeError**。
修法：沿用实例侧成员位宽，退化用 `(0, 0)` sentinel。

> 这个缺陷说明 interface 路径长期无测试覆盖（原有 modport 测试走的是别的 fixture 形态）。

### 2. `fanout(<bit>)` 与 `fanin(<bit>)` 不对称

纯总线直连（`sub .y(y)`）没有 per-bit 节点：

| 查询 | 修复前 | 修复后 |
|---|---|---|
| `fanin(top.dout[3])` | 回退父总线（iter_126 契约） | 不变 |
| `fanout(top.din[3])` | **`[]`（假"无负载"）** | 回退父总线 |

修法：新增 `SignalTracer._lift_missing_bit()`，`trace_fanout` 入口统一应用；
带 `:` 的 part-select 保持空答（与 fanin 一致）。

## 🧪 新增测试（15 个）

`sim/tests/regression/test_edge_case_driveload.py`

| 组 | 覆盖 | 关键断言 |
|---|---|---|
| 位选跨模块 | 4 | fanin/fanout 都回退总线；part-select 保持空；fanout(bit)==fanout(bus) |
| interface 成员 | 4 | writer fanin / reader fanout / slave 驱动成员 / clk 不混进数据 |
| inout 三态 | 2 | `fanin(sda)={data}`（不含 en）；`fanout(sda)={seen}` |
| struct 成员 | 3 | 成员 fanin/fanout；聚合体 fanin 能追到成员驱动 |
| class 属性 | 2 | 类型级 CLASS_PROPERTY fanin 为空；方法体驱动仍可 fanout 看到 |

## 📊 量化

| 指标 | 值 |
|---|---|
| 全量门禁 | **2330 → 2348 passed / 0 failed**（+15 边缘用例 +3 benchmark 恢复） |
| 跳过 | 10 → **7**（benchmark 3 个不再失败——iter_283 修好 benchmark import 的连带效果） |
| 边缘测试耗时 | 0.3s（全部内存 fixture） |

## 💡 结论

- 位选/interface/inout/struct/class 五类形态的**当前语义已固化为回归**
- interface 从"构建即崩"变为可用；三态/struct/class 的语义符合直觉
- 位选仍是**总线粒度**（无 per-bit 逻辑时），这是 iter_126 的既定契约，已在测试中写明

## 🔗 相关

- 计划: [PLAN.md P2.1](../../../PLAN.md)
- 审计: [iter_278](iter_278_distance_and_audit.md)
