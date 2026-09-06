# L1: Covergroup 联系 (covergroup ↔ signal / class rand var)

> **Created**: 2026-09-06 GMT+8
> **Status**: 🟡 ACTIVE — G1 开工中 (iter_161~)
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
| G1 | 提取补全: class 内 covergroup (递归 class body) + signal 结构化解析 (coverpoint 表达式 → 图 id / class 属性 / 表达式信号集) | 🟡 iter_161~ |
| G2 | 实例化绑定: cg 实例 (module 变量 / class 成员) 与定义关联 + 绑定上下文 (实例路径) | 待 |
| G3 | 查询 API (query/covergroup.py, D4 范式): trace_coverpoints(signal) 反向 / trace_sampling_chain(cp) / trace_rand_linkage(cp) | 待 |
| G4 | Accuracy Claim covergroup 转正 (观察域; bins 命中语义 = 运行时, 仍边界) | 待 |

## 子任务 (G1)

- [ ] 场景实证: class 内 covergroup 提取缺失根因定位
- [ ] class 内 covergroup 提取 (递归 class body, in_class 归属)
- [ ] coverpoint.signal 结构化解析 (module 顶层 / class 属性 / 表达式拆信号)
- [ ] 测试 (场景 1/2 + 解析正确) + 回归
- [ ] 文档同步 + commit

## 关联

- 先例: [class_tracing_plan.md](../../architecture/class_tracing_plan.md) (C1~C5)
- 决策范式: [class_tracing_architecture_decision.md](../../architecture/class_tracing_architecture_decision.md) (D4 独立 tracer)
- 现状: CovergroupExtractor (module 顶层 ✅ / class 内 ❌ / signal 原始串 ⚠️)
