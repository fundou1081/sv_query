# Iteration 170: 参数化 class 专项支持 (GenericClassDef — 统一成员访问面)

**Metadata**:
- **Iteration #**: 170
- **Task Tree Level**: L1
- **Parent Task**: L1_class_parameterized_support
- **Created**: 2026-09-06 GMT+8
- **Author**: AI 助手
- **Outcome**: ✅ 成功 (P1-P3 全通, 11 测试)

## 🎯 本次目标

方豆 "按A，开专项做" — 支持参数化 class (iter_169 发现: GenericClassDef
无成员面 → 提取/图/方法 3+1 断点)。验收: P1 宽度参数 / P2 多特化 / P3
参数 extends (继承约束) 提取+图+Q1-Q3 全通; 非参数化零回归。

## 📊 当前状态 / 预期结果

- iter_169 诊断: GenericClassDef 不可迭代无 body; 4 处消费定义符号成员。
- 预期: 探到成员面 → 统一入口改造。

## 🔬 实际结果

**关键突破 (探 pyslang)**: `defaultSpecialization` 是坏绑定 property; 但
**实例变量 `p.type` 的特化 ClassType 可迭代, 13 成员齐全** (Parameter W /
ClassProperty data / CovergroupType / Subroutine set + 隐式方法) — 特化符号
经实例变量/成员属性的 .type 可达; 其 `baseClass` 也指向可迭代的父类特化
(参数化父类只被继承无实例变量时, 从子类特化的 baseClass 收)。

**设计 (统一成员访问面)**: `SemanticAdapter.get_class_members(cls)` —
ClassType → 迭代 def 本身 (原行为); GenericClassDef → 特化符号成员
(`_scan_class_specializations` 全树扫 class 类型变量/属性 .type + baseClass
链, 首见保, 惰性缓存)。未实例化的参数化 class → [] (显式, 无假成员)。

**改造 4 处** (全走统一入口):
1. class_graph_builder: `_iter_class_properties` / `_iter_constraints` /
   `_build_method_assignments` (iter_145 的 GenericClassDef 跳过注释退役)
2. function_extractor._find_class_method (成员扫找 Subroutine)
3. covergroup_extractor: `_scan_class_specializations` (自扫) +
   _find_covergroups GenericClassDef (scope 归属 + 特化成员递归) +
   _collect_ctor_new_targets (GenericClassDef 归属 + 特化成员 ctor 分析)
4. semantic_adapter 本尊 (get_class_members 供上述)

**测试**: test_class_parameterized.py 11 — P1 (提取/成员节点/方法链 Q1/
Q2) / P2 (双特化逐实例隔离 p16←din p8←din8 / auto 歧义 missing / Q2) /
P3 (baseClass 链成员+约束建成 / 继承 cp Q1 / Q3 继承约束 packet.c_len /
约束 API)。class+covergroup 回归 159 passed。

## 💡 关键发现 / 决策

- **"定义无成员、实例化符号有成员"** 是参数化 class 的核心语义面 — 图结构
  走类型级 (packet 单节点), 数据端点/方法/约束走特化成员; 宽度取首见特化
  (p16 先见 → data 16 位; p8 共享类型级节点 — 逐特化宽度建模 = 未来项,
  iter_170 记录)。
- **extends 父类参数化** (base #(W) 只被继承): 无实例变量 → baseClass 链
  收录解决; 继承约束传播 (packet.c_len) 现成复用 class_graph_builder 原
  机制, 只缺父类成员 — 补上即通。
- pybind 深水 (defaultSpecialization 坏绑定) → 绕行实例类型 — "从使用点
  拿特化" 比 "从定义点实例化" 更贴合 slang 惰性实例化模型。
