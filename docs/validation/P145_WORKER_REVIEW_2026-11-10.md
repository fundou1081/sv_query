# P145 worker independent replay

**Worker**: `svq-p145-review2`（DeepSeek，独立 worktree）
**HEAD**: `770d3aa0`
**Verdict**: APPROVE WITH NITS

---

## 结果

```text
agent corpus: 15 tasks / 15 passed / 0 false_confident / 0 false_found
full gate: green in worker worktree (0 failed / 0 errors); final main: 2615 passed / 12 skipped after N3 coverage fix
```

## Worker 发现并修复

| # | 问题 | 修复 |
|---|---|---|
| F1 | foreign worktree pico fallback 缺失，full gate 1 failed | pico guard 检查 pilot/fallback |
| F2 | deadlock 整个模块被误标环境 skip | 标为命令退休（obsolete） |
| F3 | false metrics 由“全绿”推导，空洞 | 改为 observed negative |
| F4 | unknown task 接受任意 ok:false | pin `constraint endpoint not found` |
| F5 | 不校验任务名集合 | 精确 15 名称断言 |
| F6 | coverage 任务用不存在的 signal | 改为已有未覆盖 signal |
| F7 | benchmark skip 原因不准确 | 标为 failed/300s timeout |
| F8 | P145 提前标完成 | replay 前保持进行中 |
| N1 | main/foreign skip 数不同 | 文档记录 main/foreign 的 skip 差异 |
| N2 | false_confident 与 false_found 相同 | 增加 verify_unknown，独立统计 |
| N3 | coverpoints 接受未知 signal | 未知 signal 显式 ok:false |
| N5 | 7 个永久 skip 标 P145 | 保留历史，明确 command retired |
| N6 | iter459 标 ✅ 但 P145 进行中 | 新增 iter460 replay |

## 结论

P145 的“full gate 可复现 + agent 任务回归”成立；剩余 N4（测试与实际 fallback 逻辑重复）是低优先级维护项。
