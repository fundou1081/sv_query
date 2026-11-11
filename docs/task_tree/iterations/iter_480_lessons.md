# Iteration 480: P159 history lessons

**状态**: ✅
**日期**: 2026-11-11

## 目标

把 P139~P158 的多 agent 过程中踩过的坑、误判和有效做法沉淀成可对外分享的本地历史。

## 执行

- 主会话整理 86 行历史摘要 `/tmp/svq-lessons/history_digest.md`；
- 独立 worker `svq-lessons` 阅读摘要、iterations、validation、DISCIPLINE/SEMANTIC_CONTRACTS、git log；
- worker 写 1367 行复盘，主会话复核并修正一处测试路径；
- 不修改业务代码，不改变 P158.7 待做状态。

## 结果

- `docs/lessons/2026-11-11_pitfalls.md`
- 22 个坑、10 条正面经验、20 条反模式、10 个重来决策、三段式故事、未解问题
- worker 独立复核 opensource 失败率：38 failed / 97 passed / 6 skipped (~27%)
