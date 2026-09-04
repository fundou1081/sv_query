# Iteration 125: Inline 约束语义不可达确认 — 决策落档 (不做, 文档维护)

**Metadata**:
- **Iteration #**: 125
- **Task Tree Level**: L2 (架构决策)
- **Parent Task**: 对抗验证缺口 #7 处置
- **Created**: 2026-09-03 GMT+8
- **Author**: AI 助手
- **Outcome**: ✅ 成功 (决策落档, 无代码变更)

## 🎯 本次目标

方豆质问 "为什么用 syntax 不是 semantic" → 要求先确认 semantic 侧可行性 (不可
妥协)。确认后拍板: inline 约束分析不做, 结论文档化维护。

## 🔬 实际结果

### 验证 (全语义树 kind 盘点)

含 named + inline 约束的源码:
- `SymbolKind.ConstraintBlock` ×1 — 只有命名的 `constraint c {}` 建符号
- 语句是 `StatementKind.*` (非 SymbolKind) — 语义树不把过程体语句/表达式细化成
  symbol; inline randomize-with 产生 **0 符号**

结论: pyslang 语义模型对"声明级约束有符号 / 调用点 inline 约束无符号"是**固有
不对称** — 非 API 用法问题。syntax 是唯一入口, 但受 pyslang import-order 环境
bug 制约 (iter_124 记录)。

### 决策 (方豆)

暂缓 inline 分析; 结论落 `docs/architecture/inline_constraint_semantic_unavailable.md`
维护; 未来业务改善信号列在文档"未来改善观察"。

## 💡 关键发现 / 决策

1. **语义模型边界**: Semantic-only (2026-08-26 D1) 适用于 RTL 顶层提取域;
   SVA 信号/断言语句/procedural 内部/inline 约束 = 例外域 (语义无符号, 既定 hybrid)。
   本决策正式划定该边界。
2. **iter_121 4 补丁定性**: syntax 层症状修; 更干净 = syntax 取标识符 + semantic
   symbol kind 消歧 (函数/参数/信号) — 列为未来改进。
3. 验证方法价值: "语义树 kind 盘点" 能一锤定音地证明信息存在性 — 比反复试 API
   更接近根因。

## 📌 状态

- ✅ 决策文档 (docs/architecture/) + 本迭代记录; 无代码/测试变更; 工作树干净
