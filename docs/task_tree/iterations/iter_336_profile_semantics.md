# Iteration 336: profile clock/reset/bit semantics（PLAN P39.2）

**Metadata**:
- **Iteration #**: 336
- **Task Tree Level**: L2（PLAN `P39.2`）
- **Created**: 2026-11-01 GMT+8
- **Author**: 方豆 / AI 助手（方豆: "继续"）
- **Outcome**: ✅ 完成（clock edge/reset 语义/bit metadata；2678 passed）

## 🎯 目标

波形工具拿到值后，需要知道：
- clock 是 posedge/negedge；
- reset 是否 async/active_low；
- bit path 的 select/offset/parent width。

## 🔧 实现

- `trace profile` 新增：
  - `type.kind/type.known`（known=false，不伪装语义类型）；
  - `bit.select/kind/offset/parent_width`；
  - `clocks[].edge`；
  - `resets[].edge/async/active_low`；
  - `sequential.always`（enclosing always file/line）。
- 边沿/复位语义从 evidence 的 enclosing always 文本解析；
  无证据 → null；active_low 先查条件，再查 `_n` 命名。
- `bit_base_fallback` profile 使用父总线 + 请求 suffix，不再报 not_found。

## 🧪 测试

- `test_trace_profile.py` +2：clock/reset semantics、bit fallback metadata；
- 契约：profile_type/bit 扩展字段；
- 全量 **2678 passed / 0 failed**。

## ⚠️ 边界

- clock edge 从 always 文本解析，不是独立语义字段；无 always 证据时为 null。
- reset async 依据 sensitivity list；sync reset 可能显示 async=false（符合定义）。
- `type.known=false`：enum/struct/array 类型解析仍待 P39.3/后续。
- stage 仍未计算（stage=null/stage_known=false）。

## 🔗 相关

- 计划: [PLAN.md P39.2](../../../PLAN.md)
