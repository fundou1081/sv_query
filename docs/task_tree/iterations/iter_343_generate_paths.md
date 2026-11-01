# Iteration 343: generate 路径/类型（PLAN P43.1）

**Metadata**:
- **Iteration #**: 343
- **Task Tree Level**: L2（PLAN `P43.1`）
- **Created**: 2026-11-01 GMT+8
- **Author**: 方豆 / AI 助手（方豆: "来看 generate 这个"）
- **Outcome**: ✅ 完成（exact path + scope type；2691 passed）

## 🎯 目标

确认波形完整 path 的 generate 场景：
- 未命名 `genblk1[0]`；
- 命名 generate；
- generate scope 内信号的 type。

## 🔧 实现

- lookup：exact 已验证（不新增猜测性别名）；
- type lookup 递归 GenerateBlockArray entries / GenerateBlock:
  - 修正 `nid.split("[")[0]` 会截断 generate index 的 bug；
  - 改成只剥离尾部位选择 `[...]$`；
  - generate scope 内 `x` 能解析 `logic`。

## 🧪 测试

- `test_unnamed_generate_paths_and_type`：
  - `top.genblk1[0].x` / `top.genblk2.y` exact；
  - profile type known=true name=logic。
- 全量 **2691 passed / 0 failed**。

## ⚠️ 边界

- 使用 LRM/pyslang 命名；若波形工具使用零填充/供应商私有 genblk 命名，
  当前不猜，需真实样例再加别名；
- generate scope 节点本身 type unknown；
- 命名 generate 的 type 解析与未命名共用同一路径索引。

## 🔗 相关

- 计划: [PLAN.md P43.1](../../../PLAN.md)
