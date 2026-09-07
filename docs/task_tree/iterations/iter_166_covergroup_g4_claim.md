# Iteration 166: Covergroup G4 — Accuracy Claim 转正 (观察域)

**Metadata**:
- **Iteration #**: 166
- **Task Tree Level**: L1
- **Parent Task**: L1_covergroup_linkage (tasks/L1_covergroup_linkage.md)
- **Created**: 2026-09-06 GMT+8
- **Author**: AI 助手
- **Outcome**: ✅ 成功 (G4 完成 — covergroup 联系闭环)

## 🎯 本次目标

G4 (方案 B 最后一步, 纯文档): Accuracy Claim covergroup 从 hybrid 例外域
**转正为观察域** — 采样关系独立于数据流; bins 命中语义 = 运行时边界。
方豆 "开工!"。

## 📊 当前状态 / 预期结果

- G1 (归属+采样引用) / G2 (实例绑定) / G3 (查询 API Q1-Q4) ✅;
  audit §3 仍列 covergroup 为 hybrid 例外。
- 预期: audit 分层声明 + 关联文档同步; 无代码改动。

## 🔬 实际结果

**audit (signal_graph_accuracy_audit.md) 更新**:
- 演进注: + iter_162~166 covergroup 联系转正轮 (G1-G4)。
- §1 建模决策表 +3 行: covergroup 观察域 (采样=观察声明非数据流, 不进主
  图 — 方案 B; 数据 fanin 零污染, 联系经查询桥委托) / covergroup class
  数据端点 = 实例 (D3 同 class) / covergroup bins 命中 = 运行时 (不建模)。
- §2 分层: L1 结构层 + covergroup 观察结构 (提取/采样引用/in_class/
  host_module/instance_rule — truth 24+12+11); L2 查询层 + covergroup 联系
  查询 (Q1 采样链→fanin / Q2 反向三域 / Q3 rand-约束委托 / Q4 实例绑定);
  L3 仍不承诺 (观察域与数据域分离后数据反例表不动)。
- §3 范围: covergroup 移出 hybrid 例外 (剩 SVA / procedural / inline);
  + 观察域语义域段 + **运行时边界 (观察域不承诺)**: 实例活/死 (条件
  new() 分支)、bins 命中语义/覆盖率; 验证语料数更新 (2009 passed)。

**关联同步**:
- plan §2 Claim 行 + §4 G4 行 ✅ + header (G1-G4 闭环)。
- README 追踪范围: covergroup 联系纳入 (原 "单独规划")。
- class_tracing_architecture_decision / class_tracing_plan: 历史句保留 +
  演进注 (决策在转正前作出 — 如实不篡改)。

## 💡 关键发现 / 决策

- **观察域 vs 数据域分离让 Claim 更干净**: covergroup 不进主图 (B) →
  L1/L2 的"图结构/数据流"承诺无需为观察节点加例外; covergroup 的承诺
  以独立结构 + 查询桥形态给出 — 数据反例表 (L3) 不因观察域污染。
- **运行时边界明写而非硬建模** (方豆原则): 实例活/死 (条件 new 分支) 与
  bins 命中语义静态不可知 → 声明"不承诺"比造假数据诚实。
- 历史决策文档只加演进注不改原句 — 决策记录是时间快照, 篡改破坏可追溯。
