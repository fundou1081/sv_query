# Iteration 276: 单一命名空间收口 —— 删干净双命名空间遗留

**Metadata**:
- **Iteration #**: 276
- **Task Tree Level**: L1
- **Parent Task**: `docs/task_tree/tasks/L1_core_review_and_cli_subtraction.md`
- **Created**: 2026-10-25 GMT+8
- **Author**: 方豆 / AI 助手（方豆: "继续投入这个迭代。我想要一个足够干净的架构。底座要稳定。"）
- **Outcome**: ✅ 成功（影子节点归零、双命名空间映射全删；全量 2305 passed）

## 🎯 目标

iter_275 尝试删除 `_drop_orphan_type_nodes` 失败，根因是 **wrapper 跨实例遍历依赖
双命名空间语义**。本次按正确顺序重构：

1. 先把 wrapper 直通边改成**纯实例级**（不再依赖模块定义端口节点）
2. 再删 `LoadExtractor` / `ClockDomainExtractor`（它们只产影子节点）
3. 最后删清理 pass + `port_to_module_type` 映射

## 🔧 改动（四个层面）

### ① `_elaborate_wrapper_passthroughs()` —— 纯图实现

| 维度 | 旧 | 新 |
|---|---|---|
| 输入 | 模块定义端口（`axi_ram_wr_rd_if.s_axi_awready`） | 图里的实例端口节点（`top.G[0].u_mid.y`） |
| 配对依据 | `port_to_module_type` 的 short name 字符串相等 | 同一实例子树下**同名**端口 |
| 前提 | 需要模块定义端口节点存在（→ 影子节点删不掉） | 只需图节点 |

### ② wrapper 跨实例遍历 —— MIG module_type 判据

`_trace_drivers_recursive` 里 "跨到其它同 short-name 实例" 改为
`_sibling_ports(inst_path, port_name)`：用 **MIG 的 module_type** 找兄弟实例，
不再读 `port_to_module_type`。

### ③ 删除两个"只产影子节点"的 extractor

| 文件 | 行为 | 处置 |
|---|---|---|
| `load_extractor.py` | 遍历模块定义，建 PORT_IN/OUT 节点，**不建任何边** | 归档 |
| `clock_domain_extractor.py` | 同上 + `is_clock`/`is_reset` 标记 | 归档；标记移到 `ConnectionExtractor` 的实例端口节点 |

### ④ 删除遗留映射与清理 pass

- `_drop_orphan_type_nodes`（及其 `_instance_namespaces` / `_instance_path_list`）—— **不再需要**
- `SignalGraph._port_to_module_type`（写入点 + 字段）—— 无消费者
- `_trace_drivers_recursive` 里 3 处依赖模块定义短名的回退分支（`short_name in graph` 永远 False）

## 📊 量化

| 指标 | iter_274 | 现在 |
|---|---|---|
| 全量门禁 | 2308 passed | **2305 passed / 0 failed** |
| 影子节点（非实例命名空间） | 17~30 个（靠 pass 清掉） | **0**（只剩常量 `0` / `1'b0` 等字面量节点） |
| 双命名空间映射 | `port_to_module_type` + `port_to_internal` 双轨 | 只剩 `port_to_internal`（实例端口→内部，仍被 `get_internal_signal` 使用） |
| extractor 数量 | 4（driver/load/connection/clock） | **2（driver/connection）** |
| verilog-axi 图 | 13,188 节点 / 26,230 边 / 25.8s | 13,629 节点 / 27,302 边 / **23.4s** |

> verilog-axi 节点 +3%：新 wrapper 直通 pass 按实例补边 + 常量节点不再被清理 pass 删除。
> 构建时间反而下降（少了两个 extractor 的全模块遍历）。

## 🧪 测试调整

| 文件 | 调整 |
|---|---|
| `test_connection_extractor.py` | 删除 `port_to_module_type` 断言，改断言 `port_to_internal`（实例端口存在且互不串） |
| `test_golden_chain_anomalies.py` | 删除 2 个依赖**已退役 exp timing** 的用例（此前靠 /tmp 残留文件假绿） |

## 🏗️ 得到的架构

```
elaborated instance tree (slang)
   └─ instance-scoped 节点 id  (top.u_mid.y / top.G[0].u_mid.u_leaf.a)
        ├─ DriverExtractor      (实例级驱动边)
        └─ ConnectionExtractor  (实例端口 ↔ 父网边, 含 clock/reset 标记)
   └─ _elaborate_wrapper_passthroughs (纯图: wrapper 端口 ↔ 内部同名子端口)
   └─ 无影子节点 / 无清理 pass / 无双命名空间映射
```

## 💡 经验

1. **顺序决定成败**：先改遍历判据 → 再删 extractor → 最后删 pass。iter_275 反着来，1 个回归就卡住。
2. **"只建节点不建边"的 extractor 是纯负担**：它们的存在让双命名空间看起来"有人用"，实际只是清理 pass 的输入。
3. **死代码会伪装成前提**：`port_to_module_type` 看似被 wrapper pass 使用，实际是那条 pass 的**依赖倒置**——先有映射才需要模块定义节点。

## 🔗 相关

- 前序（失败尝试）: [iter_275](iter_275_orphan_cleanup_attempt.md)
- 再前: [iter_274 generate 作用域限定](iter_274_generate_scope_fix.md)
