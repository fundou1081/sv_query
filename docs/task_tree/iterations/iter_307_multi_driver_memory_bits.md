# Iteration 307: 多驱动标记 + 静态 memory 位精度（PLAN P13.6）

**Metadata**:
- **Iteration #**: 307
- **Task Tree Level**: L2（PLAN `P13.6`，P13 backlog 最后一项）
- **Created**: 2026-10-28 GMT+8
- **Author**: 方豆 / AI 助手（方豆: "继续"）
- **Outcome**: ✅ 完成（drivers 统计 + 静态 memory 位桥；2528 passed）

## 🎯 两个问题

1. `assign y=a; assign y=b;` → `drivers(y[3])={a,b}` 但输出没有"多驱动/条件分支"标记。
2. `logic [7:0] mem [0:3]; assign mem[1]=d; assign y=mem[1]; assign z=y[3];`
   → `fanin(z)={y[3]}`：`mem[1]` 宽度是 `(1,0)`，位查询停住。

## 🔧 P13.6a 多驱动/条件分支标记（CLI）

`drivers` 的 signal 条目新增：

| 字段 | 含义 |
|---|---|
| `driver_count` | 直接 DRIVER 边的不同源数（含条件分支） |
| `multi_driver` | ≥2 个**无条件**直接源（潜在冲突；条件 mux 不算） |
| `conditional_drivers` | 存在带条件的直接驱动（ternary/case/if） |

位查询用**父总线**统计（多驱动是总线级事实；位节点可能只建了部分边）；
unpacked array 元素例外（本身是完整元素）。

效果：
```
assign y=a; assign y=b;   → driver_count=2, multi_driver=true,  conditional=false
assign m=sel?a:b;         → driver_count=2, multi_driver=false, conditional=true
assign y=a;               → driver_count=1, multi_driver=false, conditional=false
```

## 🔧 P13.6b 静态 indexed memory 位精度

| 修复 | 说明 |
|---|---|
| 元素宽度 | `extract_data_width` 对 `FixedSizeUnpackedArrayType` 取 `elementType.bitWidth`（`mem`/`mem[1]` → 8 位） |
| 元素 signedness | 取 `elementType.isSigned` |
| 元素节点标记 | 变量节点 `extra.is_array`；GraphBuilder `_fix_array_element_widths` 回填元素节点宽度 |
| F4 位桥 | `mem[1]` 是完整元素（`[1]` 不是位索引），允许作为 F4 端点；`mem[1][k]` 由 F4 合成 |
| 查询层 | `_bit_index_of`/`_rel_bit`/`_bit_base`/表达式映射把 array 元素当**全宽节点**（不是位节点） |

效果：
```
fanin(z)      = {y[3], mem[1][3], d[3]}
fanout(d[3])  = {mem[1][3], y[3], z}
mem / mem[1] 宽度 = (7,0)
```

## 🐛 顺带修的真 bug

1. `wire_init_extractor` 对非 array 变量传了 `extra=None`（`{}` 才是默认）——
   导致后续 `node.extra.get(...)` 在 CLI/查询层偶发 `NoneType.get`。
2. `_fix_array_element_widths` / `_bit_base` 等 early-access 对 `extra=None` 缺守卫（已加）。
3. `except (TypeError, ValueError): pass` 两处（纪律 2.5 违规）→ 改为显式 `logger.debug`。

## 🧪 测试

- 新增 `test_trace_driver_stats.py`（4）：无条件多驱动/条件 mux/单驱动/位查询父统计
- 新增 `test_memory_bit_precision.py`（5）：元素宽度/位节点合成/fanin/fanout/不跨元素
- 3 个 CLI golden **有意重生成**（drivers 新增统计字段）
- 全量：2519 → **2528 passed / 0 failed**

## ✅ 验证

check_docs / check_plan / check_cli_layers / check_except_pass 全绿；
`CACHE_VERSION` 1.4 → **1.5**（旧图缺 array 元素宽度/位桥）。

## 📌 边界

- **动态索引** `mem[i]` 仍是粗粒度（运行期决定），未做逐位
- `multi_driver` 只统计无条件直接源，不做 SV 解析/冲突求解
- array 元素 signedness 取元素类型；packed array 元素内部位段仍按普通总线处理

## 🔗 相关

- 计划: [PLAN.md P13.6](../../../PLAN.md)
- 前序: [iter_306 条件分支](iter_306_conditional_bit_mapping.md)
