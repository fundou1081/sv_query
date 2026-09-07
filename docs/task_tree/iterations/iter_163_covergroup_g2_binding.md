# Iteration 163: Covergroup G2 — 实例化绑定 (instance_rule + Q4)

**Metadata**:
- **Iteration #**: 163
- **Task Tree Level**: L1
- **Parent Task**: L1_covergroup_linkage (tasks/L1_covergroup_linkage.md)
- **Created**: 2026-09-06 GMT+8
- **Author**: AI 助手
- **Outcome**: ✅ 成功 (G2 完成)

## 🎯 本次目标

G2 (方案 B): 实例化绑定 — cg 实例 (module 变量 / class 成员) 与定义关联 +
绑定上下文 (实例路径)。验收 Q4: p.cg 采样 p.addr。

## 📊 当前状态 / 预期结果

- G1 ✅: in_class 归属 + SampledSignal (class_prop ref: addr host=packet)。
- 预期: 静态可定的实例化规则 + 定义 × 实例的绑定映射 (纯映射, 观察域隔离)。

## 🔬 实际结果

**实证 (语义形态)**:
- class 内 covergroup 声明 → slang 语义 = CovergroupType (name 恒空) + **同名
  ClassProperty** (类型 '<unnamed covergroup>') — 自动成员, 与 ctor 无关。
- ctor `cg = new()` 的语句**不在语义子树** (Subroutine 'new' 子成员只有
  this/FormalArgument) — 在 ctor **syntax** 层 (BinaryExpressionSyntax +
  NewClassExpressionSyntax)。→ 实例化检测必须走 ctor syntax。
- module 级 `cg cg_inst = new()` → Instance 下普通 Variable (类型为 cg)。

**LRM 事实 (web + 惯例)**: embedded covergroup 变量**只能在新方法 (ctor) 里
赋值** (LRM 片段 "An embedded covergroup variable may only be assigned in the
new method" + UVM 惯例 cov=new() 佐证) → class 内 cg 无 ctor new() = 实例不活。

**实现**:
- `CovergroupInfo.instance_rule`: 'module_scope' (module 顶层, 采样=module
  作用域信号, 实例无关) / 'ctor_new' (ctor 对成员 new()) / 'uninstantiated'
  (ctor 未 new — 不静态绑定)。条件化 new() (if en) 存在即 'ctor_new' —
  分支 = 运行时边界 (决策点 3, models 注释)。
- `_attach_instance_rules` 后处理 + `_collect_ctor_new_targets` (语义遍历找
  ClassType→Subroutine 'new'→syntax) + `_collect_new_assign_targets`
  (syntax 递归找 X = new(), 嵌套 if 仍可达) + `_last_identifier_name`
  (this.cg → cg)。
- `covergroup_binding.py`: `bind_class_covergroups(cgs, class_instances)` —
  纯映射 (输入实例表来自主图 trace_class_instances, 本模块不建图不查图,
  B 观察域隔离); `BoundCovergroupInstance(instance_path, coverpoints)` +
  G1 class_prop ref → 实例 ref (p.addr, kind='instance_prop'); module_scope/
  uninstantiated 不绑定。

**测试**: test_covergroup_instance_binding.py 12 (rules 6: module_scope/
ctor_new/uninstantiated/this.cg/条件 new/混合; binding 5: 逐实例绑定/cp 映射/
sampled 去重/不绑定; Q4 端到端 1: 绑定 top.p.cg → top.p.addr, fanin 经
p.set(din) 贯通)。

## 💡 关键发现 / 决策

- **class 域既有隐患 (主动告知)**: 方法调用的**实参端口类型** logic (4 态)
  时方法展开**不建实例成员** (din bit → 通 / logic → 断; clk 类型无关;
  与 covergroup/ctor 完全无关 — plain fixture 复现)。class truth 全部用 bit
  端口所以从未暴露。登记 class 域 backlog (诊断: 方法实参解析路径对 4 态
  端口的敏感点), G2 不修 (跨域)。
- **unified_tracer 连续重建状态性退化**: 同一 tracer 内 build → 查询 → 再
  target build, 第二次不再展开实例成员 (class 测试单 build 未暴露)。测试用
  独立 tracer 隔离; 建议 class 域后续专项 (build 幂等性)。
- 条件 new() 的"活/死实例"判定 = 运行时 → 决策点 3 已定文档标记, 不硬猜。
- module 级 cg 的多实例命名 (cg cg_inst = new()) 不影响采样信号映射
  (module 作用域) — 实例粒度留给 G3 Q1 (module 实例路径展开)。
