# Iteration 379: 交互式 debug 场景 pilot（PLAN P74）

**Metadata**:
- **Iteration #**: 379
- **Task Tree Level**: L2（PLAN `P74`）
- **Created**: 2026-11-06 GMT+8
- **Outcome**: ✅ 3 场景 + 6 agent pilot；发现路径粒度/mux/bin 名称问题

## 🎯 场景

1. deep drive chain；
2. class rand constraints；
3. rand var ↔ coverage mapping。

## 🧪 运行

- 2 模型 × 3 场景，T2，隔离 workspace；
- 每 agent 至少 4 轮；实际 7–20 轮；
- 第一次 DeepSeek 读到 fixture 下 ground truth，已作废并重跑；
- 清理后 6/6 agent 都完成多轮查询。

## 🔧 修复

- `trace covergroups` / `trace covergroup` 增加 `bin_details`：
  name/kind/values/bin_type；不再只给 bins 计数。
- contract `class_covergroup` 同步为对象数组。

## 📋 结果

- deep chain：MiniMax 完整（11 节点 variant），DeepSeek 字段类型错（register/xor 布尔）；
- constraints：DeepSeek 完整；MiniMax 共同 block 误答 covergroup；
- coverage：两模型完整；
- 共同缺口：`paths` 粒度、mux 未建模、class relative name、class instance scope。

## ✅ 门禁

- 全量 **2535 passed / 0 failed**；
- 新增 `bin_details` 测试；
- `check_docs` / `check_plan` / 其他机械检查全绿。

## ⚠️ 不做结论

- 6 agents / 1 seed / T2 only；
- 不是真实 bug benchmark；不作模型排名。
