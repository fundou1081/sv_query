# L1 — 整数类型位宽提取（PLAN P10）

**Status**: ✅ 完成（P10.1~P10.3，iter_298）
**Created**: 2026-10-26
**Owner**: 方豆 / AI

## 问题

`integer i;` 的节点宽度提取是 `(1,0)`（假 1 位），导致：
- 位查询 `fanin(i[5])` 走错路径（把 integer 当 1 位）
- signedness 虽正确（P9），但加宽/表达式映射基于错误宽度

## 范围

1. **P10.1** 位宽提取：
   - syntax `IntegerTypeSyntax`：`byte` 8 / `shortint` 16 / `int` 32 /
     `integer` 32 / `longint` 64 / `time` 64
   - semantic 类型：优先 `type.bitWidth`（若存在）
2. **P10.2** 懒建节点（`_ensure_signal_node` 的 `(1,0)`）在声明已知时回填宽度
   （与 net 的 width 回填同规则）；缓存版本 1.2（旧图宽度错误）
3. **P10.3** 类型矩阵测试 + 图基线更新 + 文档

## 验收

- [x] `integer i` → width (31,0), signed True
- [x] `int`, `shortint`, `longint`, `byte`, `time` → 对应宽度（time unsigned）
- [x] `logic [7:0]` / 端口宽度不变
- [x] 图基线若有变化：有意重生成 + 迭代记录说明
- [x] 全量门禁 0 failed

## 非目标

- packed struct/union 位宽/ signedness（另一项）
- 数组/动态类型宽度
