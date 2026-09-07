# L1: Covergroup 联系 (covergroup ↔ signal / class rand var)

> **Created**: 2026-09-06 GMT+8
> **Status**: 🟡 ACTIVE — **G1 ✅ (iter_162) / G2 ✅ (iter_163)**; G3 待启动
> **方豆指令**: "来规划一下 covergroup 的问题。主要是要能和signal 联系起来,
> 或能和 class random var 联系起来。你整体看看。" → "哪个方案维护性更好"
> → "按b 先更新文档, 在开始做吧。"
> **规划**: [covergroup_tracing_plan.md](../../architecture/covergroup_tracing_plan.md)

## 背景

class 追踪体系 (C1~C5) 转正后, covergroup 是下一个例外域。目标: covergroup
采样关系与 signal / class rand var 联系, 让验证工程师能问:

- Q1: 这个 coverpoint 采样什么信号 → 该信号谁驱动?
- Q2: 信号 X 被哪些 covergroup/coverpoint 采样?
- Q3: class 内 cg 采样的 rand 属性 → 受哪些约束/随机域?
- Q4: covergroup 实例 (p 的 cg) 采样绑定哪个实例的属性?

## 决策

- **方案 B 拍板** (2026-09-06): 独立结构 + 查询桥 — covergroup 采样 =
  观察声明 (非数据流), 数据 fanin 零污染; 判据见 plan 第 3 节 (8 消费方
  零涟漪 / kind 守卫饱和 / 单一 fanin 实现 / Claim 干净)。
- 决策点 1 ✅ 类型级为主 (D3 一致); 3 ✅ 动态 = 文档标记 (class 同原则);
  2/4 开工默认 (拆到每信号 / 复用 coverage 域)。

## 迭代路线

| 迭代 | 内容 | 状态 |
|---|---|---|
| G1 | 提取实证修正 (class 内 cg 遍历可达 — 原"提取缺失"前提错误, iter_162 复证) + **in_class 归属** (遍历记父 class) + **signal 结构化解析** (SampledSignal: module/class_prop 类型级/select; 表达式拆到每信号) | ✅ iter_162 (24 新测试) |
| G2 | 实例化绑定: instance_rule (module_scope/ctor_new/uninstantiated, LRM embedded 只能新方法赋值) + bind_class_covergroups 纯映射 (class cg × 主图实例 → p.cg 采样 p.addr); 条件 new = 运行时边界 | ✅ iter_163 (12 测试) |
| G3 | 查询 API (query/covergroup.py, D4 范式): trace_coverpoints(signal) 反向 / trace_sampling_chain(cp) / trace_rand_linkage(cp) | 待 |
| G4 | Accuracy Claim covergroup 转正 (观察域; bins 命中语义 = 运行时, 仍边界) | 待 |

## 子任务 (G2)

- [x] 实证: class 内 cg = CovergroupType + 同名 ClassProperty; ctor 语句只在
      syntax 层; embedded cg 只能新方法赋值 (LRM)
- [x] instance_rule 提取 (module_scope / ctor_new / uninstantiated;
      this.cg + 条件 new() 均识别)
- [x] covergroup_binding.py: bind_class_covergroups 纯映射 (B 隔离不建图),
      class_prop ref → p.addr (Q4)
- [x] 测试 12 (rules/binding/Q4 端到端) + 回归
- [x] 文档同步 (plan G2 ✅ / iter_163 / overview) + commit
- [ ] G3 (查询 API) 待方豆确认

## 子任务 (G1)

- [x] 场景实证: class 内 cg 遍历可达 (提取缺失前提错误 — 修正 plan §2);
      真缺口 = in_class 恒空 (coverage.py --class 过滤静默失效) + signal 原始串
- [x] in_class 归属: _find_covergroups 带 scope_class, ClassType 下钻记父 class
- [x] signal 结构化解析: SampledSignal (name/kind/host/select/raw) +
      syntax 走查器 (非 string fallback): identifier/select/concat/member/
      ternary/bitwise/array/array-of-struct/调用 callee 跳过/常量跳过/去重
- [x] 测试 24 (test_covergroup_signal_refs.py) + 回归 (covergroup 72 + CLI 67)
- [ ] 文档同步 (plan §2/§4 + iter 记录) + commit ← 本步

## 关联

- 先例: [class_tracing_plan.md](../../architecture/class_tracing_plan.md) (C1~C5)
- 决策范式: [class_tracing_architecture_decision.md](../../architecture/class_tracing_architecture_decision.md) (D4 独立 tracer)
- 现状: CovergroupExtractor (module 顶层 ✅ / class 内 ❌ / signal 原始串 ⚠️)
