# Iteration 275: 尝试删除"孤儿节点清理" pass —— 失败并回滚

**Metadata**:
- **Iteration #**: 275
- **Task Tree Level**: L1
- **Parent Task**: `docs/task_tree/tasks/L1_core_review_and_cli_subtraction.md`
- **Created**: 2026-10-24 GMT+8
- **Author**: 方豆 / AI 助手（方豆: "做" —— 根治 `_drop_orphan_type_nodes`）
- **Outcome**: ❌ 尝试失败，**已完整回滚**（代码回到 iter_274 状态；全量 2308 passed）

## 🎯 目标

`_drop_orphan_type_nodes` 是"单一命名空间"的兜底：清掉其它 extractor 为**模块定义**
建的零度节点。目标是从根上去掉来源，再删掉这个 pass。

## 🔬 找到的根源

| 来源 | 行为 |
|---|---|
| `LoadExtractor.extract()` | 遍历 `adapter.get_modules()`，为**模块定义**建 PORT_IN/OUT 节点（`sub_adder.a`） |
| `ClockDomainExtractor.extract()` | 同上 + 给端口打 `is_clock` / `is_reset` 标记 |

两者**只建节点、不建边**（grep `result.edges` 为空），所以它们产出的就是那些零度影子节点。

## 🔧 尝试的改法

1. 把 `is_clock` / `is_reset` 标记移到 `ConnectionExtractor` 的**实例端口**节点上
2. 归档（删除）`LoadExtractor` + `ClockDomainExtractor`，从 `GraphBuilder._extractors` 移除
3. 删除 `_drop_orphan_type_nodes` 及其调用

关闭清理 pass 后会残留的"孤儿"只剩常量节点（`0` / `1'b0` / `2'b0`…），verilog-axi 58 个 —— 
说明**影子节点确实没了**，目标方向是对的。

## 💥 回归（1 个）

`test_accuracy_a1_a2.py::TestNestedGeneratePathCleanup::test_mid_fanin_reaches_leaf_driver`

```
期望: fanin(top.y[2]) 含 top.G[2].u_mid.u_leaf.a
实际: 只到 top.G[2].u_mid.y 就停
```

### 根因分析（关键发现）

`_trace_drivers_recursive` 的 **wrapper 跨实例逻辑**依赖"模块定义命名空间"的语义：

- 旧图里 `u_mid.y` 通过 `port_to_internal` 映射到 `mid.y`（module-def 节点），
  该节点带着 `leaf.y → mid.y` 的驱动链，于是递归能继续深入到 `u_leaf.a`
- 删掉两个 extractor 后，节点/边的**创建顺序**变了，`wrapper_passthrough` 后处理
  产出的边从 DRIVER 变成 CONNECTION → 该分支只在 `assign_type == "wrapper_passthrough"`
  时递归 → 深度停住

同时暴露出第二个问题：`u_mid.y` 被误判为"wrapper 端口"（判据只看 DRIVER 边），
于是跨到所有同 short-name 实例（`G[0..3].u_mid.y`），把 generate 各 entry 串进来。

### 试过的两个补丁

| 补丁 | 结果 |
|---|---|
| 收紧位提升条件（要求无任何 incoming） | 跨 entry 污染仍在（根因不在提升） |
| wrapper 跨实例守卫扩展到"同实例内部任意 incoming" | 跨 entry 消除，但深度仍停在 `u_mid.y` |

继续修需要重写 wrapper 跨实例遍历的判据（它本质上是为"双命名空间"设计的），
属于独立重构，**不在本迭代范围**。

## ✅ 处置

**完整回滚**：`LoadExtractor` / `ClockDomainExtractor` / `_drop_orphan_type_nodes` 全部恢复，
代码回到 iter_274 状态，全量 **2308 passed / 0 failed**。

## 💡 结论与建议

1. **`_drop_orphan_type_nodes` 不是坏味道，是必要的护栏**：在 wrapper 跨实例逻辑仍然
   依赖双命名空间语义时，它保证图里不出现影子节点。
2. 要真正删除它，正确顺序是：
   - **先**把 wrapper 跨实例遍历改成纯实例级判据（不依赖 `port_to_internal` /
     `wrapper_passthrough` 的旧语义）
   - **再**把 Load/Clock extractor 改成实例级（或直接删）
   - **最后**删清理 pass
   顺序颠倒会破坏跨模块深度（本次即如此）。
3. 建议把这条登记进 `KNOWN_LIMITATIONS`：当前"清理 pass"是**已知的临时护栏**，
   不是最终形态。

## 🔗 相关

- 前序: [iter_274 generate 作用域限定](iter_274_generate_scope_fix.md)
- 受影响逻辑: `src/trace/core/query/signal.py::_trace_drivers_recursive`（wrapper 跨实例块）
