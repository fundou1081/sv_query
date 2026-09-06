# Iteration 161: Covergroup 方案 B 拍板 + G1 开工

**Metadata**:
- **Iteration #**: 161
- **Task Tree Level**: L1
- **Parent Task**: L1_covergroup_linkage (tasks/L1_covergroup_linkage.md)
- **Created**: 2026-09-06 GMT+8
- **Author**: AI 助手 (方豆确认)
- **Outcome**: 🚧 部分完成 (方案 B 落档 ✅; G1 代码进行中)

## 🎯 本次目标

方豆问 "哪个方案维护性更好" → 拍板 "按b 先更新文档, 在开始做吧"。
把 B 的维护性判据落档 plan 文档, 建任务文件 + 挂 overview, 然后开工 G1。

## 📊 当前状态 / 预期结果

- iter_160 规划稿提交 (de93489), 4 决策点待拍板。
- 预期: B 论证 + 决策状态入档; CURRENT_TODO/overview/tasks 同步; G1 启动。

## 🔬 实际结果

- **维护性判据 (代码实证, 落档 plan §3)**: ① 8 个现有消费方
  (cli/commands/{verify,visualize,risk,sva,coverage,randomize,trace}.py +
  signal_graph_viewer + covergroup_analyzer) 全读独立 CovergroupInfo —
  B 零涟漪, A = 双份表示或大迁移; ② query/signal.py ~15 处 kind 守卫已
  饱和 — A 加观察节点 = 全遍历返工; ③ 数据 fanin 单一实现 (signal.py) —
  B 委托不复制; ④ G4 Claim 故事干净 (观察域独立于数据流域)。
  诚实成本: 约束 D4 CONSTRAINS 边存主图 (惰性边种) 是 YAGNI 后补项; Q2
  反向索引成本局域在一个模块。
- **决策点**: 1 ✅ 类型级为主 (D3 一致); 3 ✅ 动态=文档标记 (class 同原则);
  2/4 开工默认 (拆到每信号 / 复用 coverage 域)。
- 文档: plan §3/§5 更新 + tasks/L1_covergroup_linkage.md 新建 + overview
  挂树 + 2 汇总行 + CURRENT_TODO 当前任务切到 G1。

## 💡 关键发现 / 决策

- 约束 (D4) 的边实际存主图 (class_graph_builder 建) — "独立 tracer" 的
  精确形态 = 惰性边种 + 专用查询模块; covergroup 现不照抄 (提取独立、
  采样目标跨 module/class 不在层次), 需要时 (L4 可视化) 再补惰性边。
- overview.md 行欠账: iter_146~159 (class 时代) 未补行 — class 时代主追踪
  在 CURRENT_TODO + 架构文档; covergroup 同模式 (tree 已标注欠账待补)。
