# P178 product fixes from skill/corpus review

**日期**: 2026-11-15
**状态**: ✅ 完成

## 1. verify consistency coverage

legacy snapshot 无 MIG 时：

```text
verified=false
unknown_checks=["connection"]
coverage_complete=true   # 旧语义，错误
```

现在 `coverage_complete = not partial_checks and not unknown_checks`：

```text
coverage_complete=false
```

新增回归：`test_consistency_unknown_check_is_not_coverage_complete`（本地有
`opentitan_uart` snapshot 时执行）。

## 2. trace evidence fallback

- source mode 之前只在 snapshot 模式用 edge fallback；现在 bus/null evidence 也回退到
  `_snapshot_edge_evidence`（functional edge，非 const/空表达式）；
- `params.file` 从字符串 `"None"` 改为 JSON null。

## 3. class / constraints 无输入 JSON 错误

- `class` 无 `-f/--filelist`：JSON `{ok:false,error:...}` rc1；
- `trace constraints` 无输入：JSON `{ok:false,error:...}` rc1；
- 不再 traceback/空 stdout。

## 4. 未修（记录）

- `driver_count` 仍是 DRIVER-edge 源计数，不是 `len(drivers)`；skill 已教用
  `count/drivers[].id`；
- `trace evidence` 可能指向 reset branch；skill 教用
  `trace profile.source.driver`；
- `graph subgraph --edge-kinds control` 命名问题保留；
- `trace profile` 个别 bus 声明行可能 off-by-one；
- 这些是已知限制，不是 skill 文案能修的。

## 5. 验证

```text
canonical: 2746 passed / 0 failed / 123 deferred
full gate: green
new tests: test_p178_contract.py (3) + verify unknown-check (1)
```
