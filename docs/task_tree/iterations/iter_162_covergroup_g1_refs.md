# Iteration 162: Covergroup G1 — in_class 归属 + 采样信号结构化解析

**Metadata**:
- **Iteration #**: 162
- **Task Tree Level**: L1
- **Parent Task**: L1_covergroup_linkage (tasks/L1_covergroup_linkage.md)
- **Created**: 2026-09-06 GMT+8
- **Author**: AI 助手
- **Outcome**: ✅ 成功 (G1 完成)

## 🎯 本次目标

G1 (方案 B 首步): 提取补全 + signal 结构化解析, 为 Q1-Q4 查询桥铺路。
验收: 场景 1/2 提取 + in_class 归属正确 + signal 解析正确。

## 📊 当前状态 / 预期结果

- plan §2 前提: "class 内 covergroup 提取缺失 (场景 2 空)" — 待实证。
- 预期: class 内 cg 提取补全 + coverpoint 表达式拆到结构化信号引用。

## 🔬 实际结果

**实证推翻 plan 前提** (如实修正): class 内 covergroup **遍历可达且提取正确**
(继承/时钟层次引用/表达式/位选全形态可达, iter_160 规划的"提取缺失"是
错误前提 — 可能源自当时非典型 fixture)。真缺口两个:

1. **in_class 恒空** — 语义树 CovergroupType 嵌在 ClassType 下, 旧遍历
   _find_covergroups 不记录父 class → in_class 永远 ""。后果实证:
   coverage.py --class 过滤 (Line 329) / randomize.py in_class 显示静默失效
   (非 crash, 是假数据 — 无测试捕获因为断言是 `if cg.in_class:` 条件式)。
2. **Coverpoint.signal = syntax 原始串** — 'din' / 's.x + b[1]' / '{addr,tag}'
   无结构化, 无法桥主图 fanin / class 结构。

**实现**:
- `_find_covergroups(node, results, scope_class)` — ClassType 下钻记父 class
  (嵌套 class 覆盖), _parse_covergroup/_parse_coverpoint 透传 →
  CovergroupInfo.in_class + SampledSignal.host。
- 新模型 `SampledSignal(name, kind, host, select, raw)` +
  `CoverpointInfo.sampled` (signal 原文保留 — 8 消费方零改动)。
- syntax 走查器 (非 string fallback, 走 coverpoint syntax.expr AST 子树):
  IdentifierName / IdentifierSelectName (base Token + ElementSelect) /
  ScopedNameSyntax 段折叠 (中段 select a[0].b 内嵌 path, 末尾 select 单列) /
  组合节点 (Concat/Binary/Conditional/位运算/三元) 逐子递归; 常量/字面量
  跳过; **调用 callee 跳过** (InvocationExpressionSyntax — 坑: 无 "Call"
  字样, 首版漏 → get(w) 泄漏 'get', 对抗测试捕获) 实参引用保留。
- kind 分类: scope_class 有 → class_prop + host=class (类型级, D3 决策);
  无 → module。跨域引用 (class 内采样 module 层次名) = 边界, G3 按图纠正。

**测试**: test_covergroup_signal_refs.py 24 新测试 (identifier/select/
indexed-select/concat/去重/struct 成员/成员位选/表达式/三元/位运算常量跳过/
数组元素/array-of-struct 中段 select/函数调用/系统调用/cast/unary/inside/
class in_class 归属/class_prop host/select/继承成员/匿名 cp 不崩/cp 内 bins
不受影响)。回归: covergroup 套件 72 passed + CLI randomize/coverage 67
passed (in_class 消费方)。

## 💡 关键发现 / 决策

- **"提取缺失"类前提必须先实证再规划** — iter_160 规划依据的场景 2 空是
  错误探测 (plan §2 已修正); 本次以真实语义树 dump + 多形态 fixture 复证,
  把 G1 收敛到真缺口 (归属 + 解析), 避免在不存在的问题上做无用提取重构。
- **coverage.py --class 过滤此前静默空答** — in_class 恒空使功能形同虚设
  但无 crash; 现有断言 `if cg.in_class` 条件式 (test_covergroup_in_class
  L240) 掩盖了它。修后该断言真正生效。同类"条件式断言 + 空字段"组合
  值得警惕 (查同类: constraint tracer 等已在 class 域收过)。
- **syntax class 名无 "Call" 字样的调用节点** (InvocationExpressionSyntax)
  — callee 泄漏由对抗测试 (函数调用 cp) 捕获, 提醒走查器要覆盖调用形态。
- CovergroupInfo.in_class 修复后 randomize.py/coverage.py 输出开始显示
  class 名 — CLI 测试无断言差异 (只显示字段), 回归干净。
