# Iteration 408: Worker 辅助 BFS 测试（P102）

**状态**: ✅
**日期**: 2026-11-08

## Worker

- `svq-bfs-dev` 隔离 worktree，1 turn；
- 抽出 `neighborhood.js`，注入 queryFn；
- 7 个 BFS 测试，总计 22 Node tests。

## 验证

- Node 22/22；
- 重装后 3-cell smoke 6/6；
- 未改 core/RTL。

## 边界

fake query tests，非真实 snapshot 集成；maxNodes 软上限。
