# Iteration 304: capabilities 位精确性契约 + trace 输出元数据（PLAN P13.3）

**Metadata**:
- **Iteration #**: 304
- **Task Tree Level**: L2（PLAN `P13.3`）
- **Created**: 2026-10-27 GMT+8
- **Author**: 方豆 / AI 助手（方豆: "继续"）
- **Outcome**: ✅ 完成（agent 可发现契约 + 元数据；2508 passed）

## 🎯 问题

1. agent 先读 `capabilities`，但清单只有命令名——不知道**哪些位查询可信**、
   `one/full` 模式差异、哪些形态会回落。
2. P9/P11 已把 `is_signed`/`parent`/位段入图，但 trace JSON 只输出
   id/kind/module/width/distance/precision——agent 无法判断符号扩展/位段归属。

## 🔧 P13.3a capabilities.bit_precision

`svq capabilities --json` 新增 `bit_precision` 段（**附加字段，schema 仍为 1**）：

- `modes`: `one`（默认）/`full` 的语义说明
- `precise_forms`（12 项）：显式位/切片/寄存器位/generate/总线桥/直接拷贝/
  表达式/拼接/常量/符号扩展/integer 宽度/packed struct（聚合+成员+位桥）
- `coarse_forms`（6 项）：比较/逻辑/归约、变量移位、动态选择/动态 memory 索引、
  函数返回值、深层成员（`o.inner.a`）、非 packed struct、源位节点缺失回落
- `markers`: `node.precision` / `signal.precision` / `signal.coarse_fallback`
- 人类可读输出增加一行 `[bit precision] modes=... precise=12 coarse=6`

## 🔧 P13.3b trace 输出元数据

`_node_to_dict` 新增：

```json
{"is_signed": true|false|null, "parent": "top.a"|null, "bit_range": "[7:4]"|null}
```

同时让**位节点继承父信号 signedness**（F3/F4 合成位节点、bit-select 节点），
否则 `top.a[1]` 的 `is_signed` 恒为 null（signed 输入也看不出来）。

## 📊 效果

| 项 | 修复前 | 修复后 |
|---|---|---|
| capabilities | 只有命令表 | + `bit_precision` 契约（模式/精确/粗粒度/标记） |
| trace 节点 | 无符号/位段信息 | `is_signed`/`parent`/`bit_range` |
| `top.a[1]`（unsigned 端口） | `is_signed=null` | `false` |
| signed 端口位 | `is_signed=null` | `true` |
| packed 成员 | `bit_range=null` | `[7:4]` 等 |

## 🧪 测试

- 新增 `test_capabilities_bit_precision.py`（6）：契约存在/版本/精确形态/粗形态/标记/CLI JSON+human
- `test_trace_precision_markers.py` +2：节点元数据、signed 元数据
- 3 个 CLI golden **有意重生成**（新增字段）
- `scheduler_minimal` 图基线**有意重生成**（位节点 is_signed 由 null → false）

## ✅ 验证

- 全量：2500 → **2508 passed / 0 failed**
- check_docs / check_plan / check_cli_layers / check_except_pass 全绿

## 📌 契约说明

- `capabilities.bit_precision` 是**附加字段**（schema 版本仍 1；只增字段不破坏旧消费者）
- trace 节点新增字段同理；`coarse_fallback` 语义见 iter_303

## 🔗 相关

- 计划: [PLAN.md P13.3](../../../PLAN.md)
- 评审: [trace_capability_review_2026-10-27](../../architecture/trace_capability_review_2026-10-27.md)
- 前序: [iter_303 粒度标记](iter_303_trace_precision_markers.md)
