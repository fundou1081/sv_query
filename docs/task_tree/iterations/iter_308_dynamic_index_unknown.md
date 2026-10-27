# Iteration 308: 动态索引显式 unknown（PLAN P14.1）

**Metadata**:
- **Iteration #**: 308
- **Task Tree Level**: L2（PLAN `P14`）
- **Created**: 2026-10-28 GMT+8
- **Author**: 方豆 / AI 助手（方豆: "先做第一个"）
- **Outcome**: ✅ 完成（动态 memory 索引显式 unknown；2533 passed）

## 🎯 问题

`assign y = mem[i];`（动态 memory 读）在图上表示为
`mem --(expr="mem[i]")--> y`（**目标节点仍是数组**），查询只能给"可能来源"：

```
fanin(y) = {mem, d}      # d 还是写数据，语义上"整个数组内容"
```

但输出与普通总线答案同形，agent 可能误读为精确结果。

## 🔧 实现（CLI 输出契约，不改图）

新增识别：
- `is_dynamic_index(id)`：`[...]` 内含字母/`?`（`mem[i]`、`bus[?:?]`）
- `has_dynamic_index(graph, root, incoming)`：扫查询根的直接入/出边的
  `expression`（动态读的 `mem[i]` 只出现在边上，不出现在目标节点 id）

输出字段：
| 字段 | 含义 |
|---|---|
| `signal.dynamic_index` | 本次查询涉及运行期索引 → `true` |
| `signal.precision` | 动态索引时强制 `"unknown"` |
| `node.dynamic_index` | 节点自身是动态索引（`mem[i]`） |
| `node.precision` | 动态索引节点 → `"unknown"` |

`resolve_node_id` 对动态索引节点**不再回退父数组**（回退会丢掉动态事实）。

## 📊 效果

| 查询 | 修复前 | 修复后 |
|---|---|---|
| `fanin(y)`（`y=mem[i]`） | `precision=bus` | **`precision=unknown, dynamic_index=true`** |
| `fanin(y[3])` | `precision=bus, coarse=true` | **`unknown, dynamic=true`** |
| `fanout(mem)` | `precision=bus` | **`unknown, dynamic=true`** |
| `fanin(mem[i])` | `bus` | **`unknown, dynamic=true`** |
| 静态 `mem[1]` 位查询 | `bit` | `bit`（dynamic=false，不变） |

## 🧪 测试

新增 `test_trace_dynamic_index.py`（5）：
动态读 fanin / 动态位查询 / 动态 fanout / 动态元素节点 / 静态 memory 不被误标。

`capabilities.bit_precision.markers` 增加 `signal.dynamic_index`；
3 个 CLI golden **有意重生成**（新增 `dynamic_index` 字段）。

## ✅ 验证

- 全量：2528 → **2533 passed / 0 failed**
- 图结构不变（纯 CLI 输出层）；无缓存版本变更
- check_docs / check_plan / check_cli_layers / check_except_pass 全绿

## 📌 边界

- `precision=unknown` 表示"运行期决定，别当精确答案"，不是"没有来源"
- `dynamic_index` 只标直接查询根相关边；更深层的动态索引需要递归扫描（当前不做）

## 🔗 相关

- 计划: [PLAN.md P14](../../../PLAN.md)
- 前序: [iter_307 memory 位精度](iter_307_multi_driver_memory_bits.md)
