# Covergroup 联系规划 (Plan: covergroup ↔ signal / class rand var)

> **创建**: 2026-09-06 GMT+8
> **背景**: 方豆方向 — covergroup 需要和 **signal** 联系起来, 或和
> **class random var** 联系起来 (在 class 追踪体系 (C1~C5) 转正后, covergroup
> 是下一块例外域)。
> **状态**: ✅ 方案 B 已拍板 (2026-09-06 方豆 "按b 先更新文档, 再开始做") — G1 开工中 (iter_161~)。

---

## 1. 目标语义 (用户问题形态)

| # | 问题 | 类型 |
|---|---|---|
| Q1 | 这个 coverpoint **采样什么信号**? 该信号**谁驱动**? | covergroup → signal → fanin |
| Q2 | 信号 X 被**哪些 covergroup/coverpoint** 采样? (覆盖率挂在哪) | signal → covergroup (反向) |
| Q3 | class 内 covergroup 采样的 **rand 属性** → 受哪些约束/随机域? | covergroup → class rand → 约束 |
| Q4 | covergroup **实例** (p 的 cg) 采样绑定哪个实例的属性 (p.addr) | 实例绑定 |

## 2. 现状 (2026-09-06 实证)

| 域 | 状态 | 证据 |
|---|---|---|
| CovergroupExtractor (独立, 不进主图/追踪体系) | ✅ 提取 module 顶层 covergroup: name/clock/coverpoints/crosses/iff | 场景 1 (module 顶层) 输出正常 |
| **Coverpoint.signal** | ⚠️ = syntax **原始字符串** (无结构化/作用域解析): 'din' / '{din[3:0],en}' — 分不清 module 信号/class 属性/表达式 | CovergroupInfo.signal='din' 等 |
| **class 内 covergroup** | ❌ **提取缺失** (场景 2: class body 的 covergroup 返回空) | CovergroupExtractor 未递归 class |
| covergroup 实例化 (cg cg_inst = new()) | ❌ 未建模 (定义 vs 实例/绑定目标) | — |
| cross / iff / bins | ✅ 提取 (iter_062/122) | cross_items 合成名 |
| Accuracy Claim | covergroup 仍 **hybrid 例外域** | Claim 范围限定 |

## 3. 联系模型 (方案对比)

covergroup 采样 = **观察声明** (非数据流, 类比约束 iter_153 D4):
采样关系不该进数据 fanin (coverpoint 不是信号, 不产生数据边污染)。

| 方案 | 内容 | 利 | 弊 |
|---|---|---|---|
| A. 图节点+采样边 | covergroup/coverpoint 进主图 + SAMPLED_BY 观察边 (signal → cp) | 统一图基础设施 | 图混合观察节点; 需查询层守卫 (观察边非数据) |
| B. 独立结构 + 查询桥 (**✅ 拍板**) | CovergroupExtractor 增强 (signal 解析成图 id + class 覆盖) + **独立查询 API** 关联图/class (复用 D4 范式: query/covergroup.py) | 观察域隔离; 数据 fanin 零污染; pattern 复用 (constraint tracer) | 两套结构 (covergroup + graph) — 查询桥逻辑 |

**建议 B**: covergroup 是覆盖率观察域 — 独立 tracer (像 constraint), 查询时
经解析后的 signal id 桥接主图 (fanin) 与 class 结构 (约束/rand)。

### 为何 B 维护性更好 (2026-09-06 方豆问询 "哪个方案维护性更好" → 拍板 B)

代码实证 (全仓 grep):

1. **8 个现有消费方全部读独立结构** — `cli/commands/{verify,visualize,risk,
   sva,coverage,randomize,trace}.py` + `signal_graph_viewer.py` + 
   `covergroup_analyzer.py` (coverage gap) 全走 `CovergroupExtractor() →
   list[CovergroupInfo]`,不进主图。选 A 只有两条路: ①消费方继续调
   Extractor → 主图节点 + 独立结构**双份表示**要同步,必漂移;
   ②迁移 8 消费方走图查询 → 大面积返工。选 B: 消费方零改动,
   只在 `CovergroupInfo` 加"已解析信号目标"字段 + 新增查询模块 — 涟漪限
   在一个新文件。
2. **主图节点 kind 守卫已饱和** — `query/signal.py` 单文件 ~15 处 kind
   判断 (CLASS_PROPERTY / PORT_OUT / PORT_IN / SIGNAL / CONST...),
   iter_154 加 CLASS_PROPERTY 的教训 = 新增一种节点 kind → 所有遍历/查询/
   viewer 过一遍守卫。A 再加 coverpoint/covergroup 观察节点 → 守卫扩散面
   再翻一轮; B 不碰主图,守卫面零变化。
3. **数据 fanin 单一实现原则** — Q1 终点 ("采样信号谁驱动") 的 fanin 逻辑
   已存在且成熟 (signal.py, iter_154 打磨)。B 的查询桥直接**委托**;
   A 要在图遍历上加观察边豁免,两套语义搅在一起。
4. **G4 Claim 故事干净** — B: covergroup = 观察域,独立于数据流域,声明
   边界清晰; A: "图里混着例外节点",Accuracy Claim 的 hybrid 例外永久化。

**诚实的成本 (B 的两点)**:
- 约束 (D4) 的 CONSTRAINS 边实际存在主图 (class_graph_builder 建, 惰性
  边种, 数据 walker 按 EdgeKind 过滤天然不碰) — 若 L4 可视化需要原生图
  查询,可照此补惰性边种 — **YAGNI, 现不做**。
- Q2 反向 (信号 → 谁采样) 需 tracer 内部反向索引 (或扫描) — 一个模块内
  的局部成本; A 的成本摊在**每个通用遍历**上。局部 < 全局。

## 4. 差距清单 + 迭代路线

| 迭代 | 内容 | 验收 |
|---|---|---|
| **G1** | 提取补全: class 内 covergroup (递归 class body) + **signal 结构化解析** (coverpoint 表达式 → 图 id: 顶层信号 top.din / 实例属性 top.p.addr / this 成员 / 表达式信号集) | 场景 1/2 提取 + signal 解析正确 |
| **G2** | **实例化绑定**: covergroup 实例 (module 变量 / class 成员) 与定义关联 + 绑定上下文 (实例路径) | Q4: p.cg 采样 p.addr |
| **G3** | **查询 API** (query/covergroup.py, D4 范式): `trace_coverpoints(signal)` 反向 (Q2) / `trace_sampling_chain(cp)` → 采样信号 fanin (Q1) / `trace_rand_linkage(cp)` → rand 属性 + 约束 (Q3) | Q1-Q3 可查 |
| **G4** | Accuracy Claim covergroup **转正** (观察域: 采样关系独立于数据流; 仍边界: bins 命中语义不建模 — 运行时) | 文档 |

## 5. 设计决策点 (待拍板 → 2026-09-06 已定 1/3, 2/4 开工默认)

1. **signal 解析作用域** ✅ **定: 类型级为主** (与 class D3 一致 — cp_addr
   联系 packet.addr 结构, 实例 p.addr 经 G2 绑定得出)。class 内 cg 采样
   class 属性 → 类型级结构宿主; module 顶层 → top 域信号。
2. **表达式 coverpoint** ({din,en} / din[3:0]) — 默认拆到每个信号 (多信号
   观察, Q1/Q2 不漏信号); bins 表达式 (transitions) 不拆 (运行时语义)。
   G1 落地遇冲突再议。
3. **动态边界** ✅ **定: 编译期可定 = 静态绑定声明; 条件实例化
   (if (en) cg_inst = new()) = 文档标记** (同 class 动态分派原则 — 不硬猜)。
4. 与现有 coverage generate/gap (EXTRACTION_COVERAGE 域) 的衔接 — 默认
   **复用**: CovergroupInfo 增字段不影响 8 消费方; signal 链增强留给
   G3 查询 API 之后 (不新建域)。

## 6. 关联

- class 追踪先例: [class_tracing_plan.md](class_tracing_plan.md) (C1~C5 模式) /
  [class_tracing_architecture_decision.md](class_tracing_architecture_decision.md) (D4 独立 tracer 范式)
- Accuracy Claim: covergroup 现例外域 → G4 转正 (观察域)
- iter_122 (cross 合成名) / iter_062 (iff) / coverage_generator (EXTRACTION_COVERAGE)
