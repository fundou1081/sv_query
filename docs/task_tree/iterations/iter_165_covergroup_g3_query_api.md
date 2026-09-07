# Iteration 165: Covergroup G3 — 查询 API (Q1-Q3)

**Metadata**:
- **Iteration #**: 165
- **Task Tree Level**: L1
- **Parent Task**: L1_covergroup_linkage (tasks/L1_covergroup_linkage.md)
- **Created**: 2026-09-06 GMT+8
- **Author**: AI 助手
- **Outcome**: ✅ 成功 (G3 完成)

## 🎯 本次目标

G3 (方案 B / D4 范式): 查询 API — Q1 采样链 fanin / Q2 反向 / Q3 rand-约束。
验收: Q1-Q3 可查 (方豆 "切回g3 继续 coverage 相关的任务")。

## 📊 当前状态 / 预期结果

- G1 ✅ (in_class + SampledSignal) / G2 ✅ (instance_rule + 绑定)。
- 预期: query/covergroup.py 独立 tracer + UnifiedTracer 薄委托, 不建观察边。

## 🔬 实际结果

**实现**:
1. **extractor host 锚点** (G3a): `CovergroupInfo.host_module` — module 顶层
   cg 的宿主实例路径 (elaboration: 'top' / 'top.u_sub'), _find_covergroups
   带 scope_path 下钻; 另 `compiler` 可选注入 (查询桥复用主图编译器 —
   同源不双编译, get_root 缓存)。
2. **query/covergroup.py** (G3b): `CovergroupTracer(cgs, tracer)`:
   - Q1 `trace_sampling_chain(cg, cp?, instance?)`: 每 cp 采样引用 → 图 id
     (module: host.ref; class: instance.ref) → 委托 trace_fanin (数据 fanin
     单一实现)。class cg 数据端点 = 实例 (D3): 显式 instance / 单实例自动 /
     多实例歧义 → missing (不臆测)。
   - Q2 `trace_coverpoints(signal_id)`: 反向匹配三域 — module 顶层 (宿主锚) /
     class 类型级 (packet.addr, instance='') / 实例级 (top.p.addr)。
   - Q3 `trace_rand_linkage(cg, cp?, instance?)`: class cg 采样 class_prop →
     委托 ConstraintTracer (trace_constraints, 实例自动解析类型级)。
3. **UnifiedTracer 委托** (trace_constraints 同款薄方法 ×3) + 惰性
   `_get_covergroup_cgs` (复用本 tracer compiler)。

**测试**: test_covergroup_query_api.py 11 — module Q1 (cp_d → top.din →
drivers {top.a}; cp_c 拆两信号) / Q2 module (top.din → cp_d+cp_c) /
class Q1 (单实例自动 top.p → p.addr → {din}; 显式) / Q2 类型级 (instance='')
vs 实例级 / Q3 (cp_addr → packet.c_addr; cp_both → addr+tag 各自约束;
实例自动解析) / 多实例边界 (Q1 歧义 → missing; 显式 p1/p2 各得其所; 未
调用 set 的 p2.addr 无驱动 — 正确)。

## 💡 关键发现 / 决策

- **Q2 类型级 vs 实例级是分开的查询域** (D3): 模板匹配 (packet.addr,
  instance='') ≠ 实例匹配 (top.p.addr)。初版测试误把类型级查询当实例
  展开 — 修正: 各自查询, 语义清晰 (结构 vs 数据端点)。
- 多实例歧义 (Q1 无 instance): 返回 missing 而非臆测任一实例 — 与 class
  域 C2 "未用实例成员不臆造"同原则。
- 委托而非复制: Q1 fanin / Q3 约束全走既有单一实现 (signal.py /
  constraint.py) — 方案 B 的维护性判据兑现 (无第二套 fanin)。
- module cg 多实例模块 = 逐实例记录 (host 每 elaboration 一份) — 定义级
  去重 = 未来项 (plan 记录)。
