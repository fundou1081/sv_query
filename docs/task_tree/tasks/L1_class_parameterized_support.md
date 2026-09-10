# L1: 参数化 class 支持 (GenericClassDef)

> **Created**: 2026-09-06 GMT+8
> **Status**: ✅ CLOSED (iter_170) — P1-P3 全通 (统一成员访问面)
> **方豆**: "按A，开专项做" (iter_169 发现 → 专项支持)
> **结果**: [iter_170](../iterations/iter_170_class_param_support.md)

## 背景

iter_169 实证: 参数化 class (`class packet #(int W=8)`) 语义符号 =
**`SymbolKind.GenericClassDef`** (非 ClassType), **不可迭代、无 .body** →
3+1 断点:
1. CovergroupExtractor walker 'ClassType' 子串不设 scope → cg 提取空
2. semantic_adapter.get_classes 含 GenericClassDef, 但 class_graph_builder
   遍历 `for member in cls` 空 → 成员节点不建 (packet.data 缺)
3. 方法调用 receiver 解析/_find_class_method 找不到成员 → p.set 不展开
4. 逐特化宽度 (W=16 vs def 8) 无建模 (宽度语义, 结构追踪主域)

## 结果 (iter_170)

- 突破: 实例变量 p.type 的特化 ClassType **可迭代 13 成员** (defaultSpecialization
  是坏绑定 property — 绕行实例类型); baseClass 链收参数化父类。
- 统一成员访问面 `SemanticAdapter.get_class_members(cls)`: ClassType 迭代
  def; GenericClassDef → 特化成员 (_scan_class_specializations + baseClass 链)。
- 改造 4 处: class_graph_builder ×3 / function_extractor / covergroup_extractor
  (提取 + ctor 分析 GenericClassDef 归属)。
- 测试 11 (test_class_parameterized.py); class+covergroup 回归 159; 全量待确认。
- 边界记录: 类型级宽度取首见特化 (逐特化宽度建模 = 未来项)。

## 验收

- ✅ P1/P2/P3 提取 + 图 (成员节点/方法展开) + Q1-Q3 通
- ✅ 非参数化 class 回归 (159 passed)

## 关联

- iter_169: GenericClassDef 缺口诊断
- class 追踪: semantic_adapter.get_classes / class_graph_builder /
  function_extractor / covergroup_extractor
