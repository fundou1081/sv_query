# Iteration 144: gate G-2/G-3 + SVA semantic 消歧 — 方豆拍板暂缓记录

**Metadata**:
- **Iteration #**: 144
- **Task Tree Level**: L2 (backlog 管理 / Accuracy Claim L3 #4 #6 处置)
- **Parent Task**: [signal_graph_accuracy_audit.md](../../architecture/signal_graph_accuracy_audit.md)
- **Created**: 2026-09-05 GMT+8
- **Author**: AI 助手
- **Outcome**: ✅ 决策落档 (无代码改动)

## 🎯 本次目标

方豆: "gate 和 sva 就先不做了。先用文档记录一下。" — L3 反例剩余 2 项
拍板暂缓, 记录触发条件。

## 📊 决策

| 项 | 性质 | 暂缓理由 | 触发条件 (记录) |
|---|---|---|---|
| **#4 gate G-2/G-3** (drive strength/delay 进图 + UDP table) | 增强型 | 对"谁驱动"查询**无影响** (门级驱动答案已正确, iter_115 端子方向 + iter_112 原语); 纯门级语义完整化 | 需要 delay/strength 分析 (timing 类) 或 UDP 内部逻辑可视化时 |
| **#6 iter_121 SVA semantic 消歧重构** | 架构整洁型 | 无用户可见收益; syntax 症状修当前工作; 动 SVA 83 测试风险高 (iter_121 对抗 6 缺口全绿是现状基线) | SVA 提取再次出现 syntax 症状修堆叠 / 新语义消歧需求时 |

## 📌 落档位置

- audit doc L3 反例 #4/#6: 🕐 暂缓标注 + 触发条件
- CURRENT_TODO backlog #1/#2: 🕐 暂缓标注 (保留任务文件引用)
- 无代码改动

## 状态小结 (Accuracy Claim 反例表)

- ✅ 闭环 5 项: inout (#1) / interface (#2) / A2 位对位 (#3) / slang (#5) /
  CVA6 编译 (#7 主部, 建图 = 内存环境边界)
- 🕐 暂缓 2 项: gate (#4) / SVA semantic 消歧 (#6) — 触发条件已记录
- 反例表无"进行中待修"项 — 剩余全部为已闭环或已暂缓
