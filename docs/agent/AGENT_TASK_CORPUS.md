# Agent task regression corpus (P145)

**用途**: 用可执行任务验证 agent 工作流，而不是只验证命令能跑。

## 运行

```bash
python3 tools/agent/agent_task_regression.py
python3 tools/agent/agent_task_regression.py --json
```

全部通过时退出 0；任一任务失败退出 1。

## 15 个任务

| # | task | 验证 |
|---|---|---|
| 1 | `deep_path` | 三模块 6-hop from/to |
| 2 | `deep_reverse` | 反向 directed 明确 not_found |
| 3 | `dataflow_deep` | dataflow 与 path 一致 |
| 4 | `verify_deep` | verify claim path verified |
| 5 | `constraint_chain` | a→d 3-hop constraint 链 |
| 6 | `constraint_not_random` | 非 random 端点显式拒绝 |
| 7 | `constraint_unknown` | 未知端点显式失败，不伪造 found |
| 8 | `verify_unknown` | 未知端点必须 unknown，不能 verified/contradicted |
| 9 | `frontier` | generic frontier，不分类 FIFO |
| 10 | `boundary_trace` | 显式 boundary map 拼接，`proven:false` |
| 11 | `boundary_empty` | 空 map 停在 frontier |
| 12 | `schema_envelope` | envelope/write_scope 合同 |
| 13 | `neighborhood_truncated` | 预算命中 `truncated=true` |
| 14 | `coverage_unknown` | 未知 coverage 信号显式失败 |
| 15 | `coverage_reason` | 已有但未覆盖的信号 reason |

## 指标

```text
tasks / passed / failed
false_confident  (negative task answered verified/contradicted/found)
false_found      (negative path task returned found=true)
```

负例任务失败时，不会被 exit 0 掩盖。
这是一组回归任务，不是性能 benchmark，也不是统计证明。
