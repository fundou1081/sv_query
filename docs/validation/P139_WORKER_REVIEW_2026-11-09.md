# P139 worker independent review

**Worker**: `svq-p139-review2`（MiniMax，独立 worktree）
**HEAD**: `17690019`
**Verdict**: **APPROVE WITH NITS**

---

## Findings and fixes

| # | Severity | Finding | Fix |
|---|---|---|---|
| A | Major | 纯环 `frontier_count=0` 静默漏报 | 新增 `cycle_or_all_seen` |
| B | Major | `instance_boundary` 的 `instance` 指向父作用域 | instance 指向实例本身 |
| C | Major | `max_frontier` 按方向而不是全局 | 改为全局预算 |
| D | Moderate | frontier 行未去重 | 按 `(direction,node)` 保留最短 path |
| E | Moderate | instance_boundary 的 next_probes 不可执行 | 指向实例路径 |
| F | Minor | `path` 字段未文档化 | 文档补齐 |
| G | Minor | note 含 FIFO 字样 | 改为 `no semantic classification` |
| H | Minor | graph backend 异常被吞成 no_structural_edge | 改为显式 ValueError |
| I | Minor | max_depth=0 语义 | 校验 >=1，按最大 hop 定义 |
| J | Minor | params 缺 max_frontier | 补齐 |

## Tests

```text
test_frontier.py: 5 passed
check_*: all green
```

## 结论

P139 的核心承诺成立：

```text
generic
non-classifying
non-mutating
explicit-failure
```

没有 BLOCK 级问题。
