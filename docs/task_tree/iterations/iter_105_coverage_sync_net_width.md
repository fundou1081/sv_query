# Iteration 105: EXTRACTION_COVERAGE 同步 + 无 init net 宽度

**Metadata**:
- **Iteration #**: 105
- **Task Tree Level**: L1 (A-F 修复后续)
- **Parent Task**: 缺陷修复收尾
- **Created**: 2026-09-02 GMT+8
- **Author**: AI 助手 (方豆 "继续")
- **Outcome**: ✅ 成功

## 🎯 本次目标

收尾 A-F 修复的遗留项:
1. EXTRACTION_COVERAGE 文档同步 (修复后矩阵已过时)
2. 无 init 模块级 net 宽度 (iter_101 记录: `wire prod;` 无初始化器仍 (1,0))

## 📊 当前状态 / 预期结果

- 文档: #11 LHS concat / #15 ternary 行过时; 无 A-F 修复记录
- 代码: 无 init net 节点由 ensure_signal_node 惰性创建 (1,0) 假宽度

## 🔬 实际结果

### 1. EXTRACTION_COVERAGE 同步

- #11 LHS 拼接: 更新 fixture (36) + 备注 iter_102 位置对齐修复 (原笛卡尔积)
- #15 ternary: 备注 iter_102 分支 localparam 常量值解析
- 状态变更日志: 新增 iter_101~104 A-F 完整记录 (根因 + 修复摘要)

### 2. 无 init net 宽度 (net_decl_extractor)

- 根因: net_decl_extractor 循环 1 只在 `init is not None` 后建节点; 无 init 的
  `wire [N:M] x;` 由 ensure_signal_node 惰性创建 (1,0) 假宽度
- 修复:
  - 节点创建/补宽移到 init 检查**之前** (所有 net 都处理)
  - `_ensure_net_node`: 已存在节点若是 ensure_signal_node 的 (1,0) 且声明
    宽度已知 → 补成真宽度 (不新增未引用 net 的节点)
- 验证: case27 `wire [W-1:0] prod;` (无 init) width (1,0) → **(7,0)**;
  acc 数组保持 (1,0) (数组宽度歧义, 合理); 节点集无新增 (只补宽不改结构)

## 💡 关键发现 / 决策

1. **惰性节点创建的宽度盲区**: ensure_signal_node (无 decl 上下文) 硬编码
   (1,0) — 修复方式是"先建/补宽再跳过 init", 不新增未引用节点 (保持节点集契约)。
2. **文档与实现同步是闭环的最后一步**: A-F 修复后 EXTRACTION_COVERAGE 的
   #11/#15 行与实现不符 — 同步后矩阵恢复可信。

## 📌 状态

- ✅ EXTRACTION_COVERAGE 同步 (#11/#15 + 变更日志)
- ✅ 无 init net 宽度修复 (case27 prod (7,0)) + 补宽逻辑
- 下一步候选: picorv32 ELK 修复 (iter_086 根因已定位, 方豆此前拍板暂缓 —
  待确认是否现在做)
