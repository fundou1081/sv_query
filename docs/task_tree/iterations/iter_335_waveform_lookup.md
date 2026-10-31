# Iteration 335: waveform path lookup（PLAN P39.1）

**Metadata**:
- **Iteration #**: 335
- **Task Tree Level**: L2（PLAN `P39.1`）
- **Created**: 2026-11-01 GMT+8
- **Author**: 方豆 / AI 助手（方豆: "波形工具需要提供完整 rtl hier path，围绕这个展开"）
- **Outcome**: ✅ 完成（strict lookup；2676 passed）

## 🎯 目标

波形工具按完整 RTL hier path 查询；本工具严格映射到 canonical graph id，
不做模糊后缀（避免把 A 的值贴到 B 上）。

## 🔧 实现

`svq trace lookup --path ... --paths-file ...`

- 归一化 `$root.` 前缀 / 首尾空白；
- `exact`：完整 id 命中；
- `bit_parent`：`y[3]` 无位节点但 `y` 存在 → canonical=父总线 + `bit_suffix`；
- `not_found`：**严格**不匹配，给 suggestions；
- aliases：port↔internal（MIG）；
- 批量 file / 重复 --path；`found=false` 不算命令错误。

## 🧪 测试

- `test_trace_lookup.py` 3：exact/$root/bit_parent、strict not_found、generate path；
- 契约 +1：lookup_path 字段；
- 全量 **2676 passed / 0 failed**。

## ⚠️ 边界（联调时必须知道）

- **interface/modport 路径别名未覆盖**；graph 没有 interface 实例时无法映射；
- generate 使用图中真实 label（如 `gen_accum[0]`）可命中；若波形工具用 `genblk1` 需加别名；
- escaped identifier 仅支持 exact/空白归一化，不做语义反转义；
- **type/enum/array/struct 解码元数据、clock 边沿/复位极性/stage 尚未补**（P39.2）。

## 🔗 相关

- 计划: [PLAN.md P39.1](../../../PLAN.md)
