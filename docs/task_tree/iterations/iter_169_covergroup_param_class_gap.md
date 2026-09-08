# Iteration 169: Covergroup 参数化/高级形态对抗 — GenericClassDef 缺口发现

**Metadata**:
- **Iteration #**: 169
- **Task Tree Level**: L1
- **Parent Task**: L1_covergroup_linkage (tasks/L1_covergroup_linkage.md)
- **Created**: 2026-09-06 GMT+8
- **Author**: AI 助手
- **Outcome**: ⚠️ 部分完成 (验证 6 形态通过 + 锁测试; **参数化 class 缺口 = 新
  class 域功能面, 决策待方豆**)

## 🎯 本次目标

方豆 "可以再挖一些, 参数class 等等" — 参数化 class (宽度/类型参/extends/
多特化) + 高级形态 (typedef 前置/虚方法/static/option/cross/$rose/enum/
参数 interface) 找盲点。

## 📊 当前状态 / 预期结果

- 混合对抗 iter_168 ✅。预期: 参数化等形态扫描分类。

## 🔬 实际结果

**参数化 class (P1-P3) = 真缺口 (class 域新形态)**:
- 语义形态: 参数化 class = **`SymbolKind.GenericClassDef`** (非 ClassType!),
  **不可迭代、无 .body** — 成员面与 ClassType 不同。
- 3+1 断点同源: ① CovergroupExtractor walker 只认 'ClassType' (scope_class
  不设, cg 不达 → 提取空) ② semantic_adapter.get_classes 已含 GenericClassDef
  但 class_graph_builder 遍历 `for member in cls` 空 → 成员节点不建
  (P1 图只有 packet/top.p, 无 packet.data) ③ 方法调用 receiver 类型解析/
  _find_class_method 找不到成员 → p.set 不展开 ④ 特化实例宽度 (W=16 vs
  def 8) 无逐特化建模。
- 可行性探: `defaultSpecialization(scope)` 是**方法需 Scope 参数** —
  特化成员可达需走 slang 特化机制; 支持 = 独立小项目级 (get_classes/
  class_graph_builder/function_extractor/covergroup_extractor 4 处 +
  特化语义研究)。**决策待方豆** (开专项 vs 登记边界)。

**高级形态 (X 组) — 6 通过 + 锁测试**:
- X1 typedef 前置 class: 全链 (提取/图/方法调用/Q1) ✅
- X5 cg 体内 option/type_option 语句: 无幽灵 cp ✅
- X6 class 内 cross: 提取正常 ✅
- X7 $rose(din) 边沿: 采样引用 = din ✅
- X8 enum 成员: class_prop 引用正确 ✅
- X9 static 成员 + 双实例: auto 歧义 missing (设计正确), 显式可用 ✅
- X2 虚方法: fixture 非法的部分; 动态分派 = class 域已文档边界 (不追踪)
- X4 参数化 interface 端口: fixture 语法非法 (DefinitionUsedAsType) —
  slang 需非参数端口声明 — 未深入 (语料罕见)

**测试**: test_covergroup_adversarial.py +6 (18 全过)。

## 💡 关键发现 / 决策

- **GenericClassDef 是 class 域第 4 种符号形态盲区** (前: ClassType 可迭代/
  StatementList 不可迭代/Module 预 elab) — pyslang 语义面随形态而异,
  任何 "kind 子串 + 迭代" 假设都可能静默空。参数化 class 支持前, 需把
  "get_classes 含 GenericClassDef 但成员面不同" 显式化 (现在 adapter 返回
  它会让下游误以为有成员 — 静默空, 违反失败可见)。
- typedef 前置/static/option/cross/$rose/enum 等非参数高级形态全健壮 —
  观察域提取走查器 (syntax) 与语义分类配合良好。
