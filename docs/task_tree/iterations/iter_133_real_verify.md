# Iteration 133: iter_131/132 真实项目复验 + 嵌套 generate 假节点 backlog 登记

**Metadata**:
- **Iteration #**: 133
- **Task Tree Level**: L2 (审计链 → 真实复验)
- **Parent Task**: [signal_graph_accuracy_audit.md](../../architecture/signal_graph_accuracy_audit.md)
- **Created**: 2026-09-05 GMT+8
- **Author**: AI 助手
- **Outcome**: ✅ 成功 (修复复验通过 + 新 backlog 登记)

## 🎯 本次目标

方豆 "继续" (取消方向提问) → 按推荐路径: 用真实项目验证 iter_131
(dataflow bus 聚合) 与 iter_132 (per-entry fanin 隔离) 两个查询修复的
实际效果, 顺带暴露深层嵌套 generate 边界。

## 🔬 实际结果

### 复验 1: fanin 隔离在真实 AES (4834 节点 / 272 实例) 生效

- `ROUND[0..2].U_ROUND.data_out` fanin 各 5 drivers, **零跨 entry**
  (iter_132 修复前会串入相邻 ROUND 实例内部源)
- Round 级联验证: ROUND[1] fanin 不含 ROUND[2] (向后隔离 ✓)

### 复验 2: dataflow bus 聚合

- aes plain_text→cipher_text unreachable 是已知限制 (cross-module dataflow
  未支持, test_dataflow_latency skip 注明), 非修复问题
- dataflow 修复已在 usage OpenTitan 真实 RTL 验证 (arbiter 8 paths)

### 新 backlog: 嵌套 generate 深层路径重复段假节点 (aes 型)

复验暴露 3+ 层 generate 嵌套 (Top_PipelinedCipher→ROUND[i]→Round→U_SUB→
SubBytes→ROM[i]→ROM) 的路径拼接边界:
- 假路径: `aes_top.ROUND[1].U_ROUND.ROUND[1].U_SUB` (内层重复外层 generate 段)
- aes 实测 351/4834 节点 (7.3%) 含重复段; 正常路径 U_SUB 4377 边 vs 假路径
  14 边 — connection/driver 两层 namespace 部分分裂
- baseline (iter_132 前) 同现 → 非 iter_131/132 引入, 是 iter_109/110
  宿主作用域处理的更深嵌套边界 (Round 内实例拼接时 ctx 又带外层 ROUND[i])
- fanin 主链实测不受扰 (U_SUB.data_out fanin 19 源 0 重复段) — 假节点是
  冗余污染, 非主链断裂
- 登记 audit 🐛 区, 修复方向: 实例路径拼接逐层段归属去重 (iter_117 通用化)

## 💡 关键发现

1. **iter_131/132 修复在真实设计有效**: 272 实例 / 嵌套 generate 的真实
   AES 上 fanin 位隔离成立 — 修复不是 fixture 特例。
2. **假节点 ≠ 主链断裂**: aes 7.3% 重复段节点但 fanin 主链 0 污染 — 需
   区分"图污染"与"查询错误"两个严重度; 前者待专项清理, 后者已修。
3. 复验方法延续: 真实项目 (非 fixture) 是查询修复的最终裁判; baseline
   worktree 对比区分"本次引入" vs "既有边界"。

## 📌 状态

- ✅ iter_131/132 真实复验通过 (fanin 隔离 / dataflow 聚合)
- 🐛 新 backlog: 嵌套 generate 深层重复段假节点 (aes 型, 351/4834)
  登记 audit — 修复方向: 路径段逐层去重
- ✅ **backlog 已闭环**: iter_134 以 gen_block 直接宿主判定修复
  (aes 279/1116→0, cordic 105→0) — 见 iter_134 记录
