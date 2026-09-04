# Iteration 122: covergroup cross 匿名名修复; constraint inline-with 诊断记录

**Metadata**:
- **Iteration #**: 122
- **Task Tree Level**: L2 (对抗 backlog 7-8)
- **Parent Task**: 对抗验证缺口修复
- **Created**: 2026-09-03 GMT+8
- **Author**: AI 助手
- **Outcome**: ⚠️ 部分 (#8 ✅; #7 诊断后记录 backlog, 需专项设计)

## 🎯 本次目标

修对抗 backlog 7-8:
- #8 covergroup cross 的 name 空串 (匿名 cross 合法但无 display 名)
- #7 constraint `randomize() with {}` inline 约束不产 CONSTRAINT 节点

## 🔬 实际结果

### #8 ✅ 已修 (covergroup_extractor._parse_cover_cross)

匿名 cross (`cross cp_a, cp_b {...}` 无 label) 合法, semantic name 恒空 —
probe 确认 CoverCrossSyntax name 为 NONE (具名/匿名都无 .name 语义)。
修复: 无 name 时按 items 合成 `cross_<item1>_<item2>...`。
验证: `cross_addr_data` 等; 既有 covergroup 套件 28 passed 零回归。

### #7 🚧 诊断后记录 (需专项设计, 未修)

现象: `it.randomize() with { x > 5; y < x*2; }` (模块级 initial) — class 图只有
CLASS + props, 无 CONSTRAINT_EXPR/CONSTRAINS。

诊断 (语义树深探):
- named constraint (`constraint c {...}`) 是 ClassType 的成员
  (ConstraintDeclarationSymbol) → _build_constraint_block 处理 ✓
- inline `with {}` 不在 class 成员层 — 挂在 randomize 调用处 (模块 initial /
  class 方法的过程体); 语义树在 procedural/BlockStatement 层**无直接
  ConstraintExpression 符号落点** (混合 syntax 对象, 迭代即 TypeError)
- 关键设计问题: **receiver 类解析** — inline 约束引用 x,y, 归属哪个 class
  需从 `it.randomize()` 的 receiver 变量类型 (item it) 推断; 多 class 同名
  rand 变量时歧义

结论: 修复需 (a) 过程体 syntax 扫描 randomize-with (SVA 同款 syntax 路径),
(b) receiver 变量 → 声明类型解析, (c) 约束表达式变量 → 类属性 CONSTRAINS 边 —
属中改 + owner 语义设计, 不 rush 脆 hack。记录 backlog 专项 (复现:
CONSTRAINT-inline, /tmp/adv_verify.py)。

## 📌 状态

- ✅ #8 (cross 匿名名合成) + 断言增强; covergroup 28 passed
- 🚧 #7 inline-with 诊断完成, backlog 待专项 (owner 解析设计)
- 全量回归结果见 commit
