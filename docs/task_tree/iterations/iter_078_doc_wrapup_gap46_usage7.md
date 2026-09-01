# Iteration 078: #7 遗留文档收尾 — 补登记 GAP + 更新 USAGE 文档

**Metadata**:
- **Iteration #**: 078
- **Task Tree Level**: L1
- **Parent Task**: ARCHITECTURE_TODOLIST #7 迁 pyslang 11.0 native API
- **Created**: 2026-09-01 GMT+8
- **Author**: AI 助手
- **Outcome**: ✅ 成功 (2 项文档收尾, 无代码改动)

## 🎯 本次目标

方豆 "先做 1 2 这两项" — 梳理 #7 时发现的 2 个文档遗留:
1. 补登记 `get_generate_instances` 覆盖率不一致 (iter_056 承诺登记但未登记)
2. 更新 `PYSLANG_SEMANTIC_USAGE.md` §7 (仍写"暂不做", 但 #7 已完成)

## 📊 当前状态 / 预期结果

- iter_056 明确写 "附带发现 get_generate_instances 覆盖率不一致 (conditional+loop
  返 0) — 记入已知清单, 非本轮范围", 但 grep 全仓 docs 找不到该记录 — 失联
- PYSLANG_SEMANTIC_USAGE.md §7 写 "⚠️ 暂不做, 等用户指示" — 与已完成事实矛盾

## 🔬 实际结果

### 1. EXTRACTION_COVERAGE.md — 补登记 #46

已知缺陷补充表 (iter_068) 新增一行:
- **#46**: `get_generate_instances` 覆盖率不一致 (conditional+loop generate 返回 0),
  位置 semantic_adapter.get_generate_instances, 备注含 iter_056 出处 + 影响面
  (connection_extractor L123/L147 generate 实例补集可能漏报)
- 主矩阵 🔸 计数 (33 语法类别) 不受影响 — 补充表独立编号

### 2. PYSLANG_SEMANTIC_USAGE.md — §7 更新为已实施

- 标题 "未实施" → "✅ 已实施 (iter_053~059, 2026-08-29)"
- 保留原始 API 清单 (topInstances/hierarchicalPath/body/portConnections/visit)
- 新增"实施结果"段: 5 调用方 native + 死代码删除 + GAP-1~7 + 等价性 3/6
- **诚实修正**: 性能实测 2.14x 而非预估 4x (CVA6 编译不过无法复测);
  namespace rewrite 消除的实际机制是 target_module auto-filter (arch.py
  2026-07-11) 而非 native API 本身

## 💡 关键发现 / 决策

1. **承诺"记入已知清单"≠ 已登记**: iter_056 的附带发现没落到任何持久文档,
   直到本轮梳理 grep 才发现失联。教训: 迭代记录里的"记入已知清单"应视为
   **TODO 动作**, 需要显式执行到 EXTRACTION_COVERAGE 等集中表。
2. **文档诚实性**: §7 的 4x 预估保留但标注实测 2.14x + 原因 (CVA6 编译阻塞),
   不抹掉历史预期, 只加修正 — 符合"如实记录"纪律。

## 📌 状态

- ✅ #46 已登记 / PYSLANG_SEMANTIC_USAGE.md §7 已更新
- 提交: 仅 2 个文档文件 (无代码改动)
