# P182.5 — snapshot / cache / Session 评估

> **状态**: 评估完成；**不改变 CLI 行为，不做 serve，不全局改 cache 默认**。
> **方法**: `tools/eval_p1825_snapshot_surface.py` + 现有 snapshot 往返测试。
> **日期**: 2026-11-19

## 1. 结论

```text
0.3.x：保持 CLI + Session 库入口；
不引入本地 serve；
不扩大 --from-snapshot 到 source-dependent 命令；
不把 build_graph 默认改为 cache。
```

理由：snapshot 覆盖是**显式局部契约**，不是“所有命令都支持”；source/evidence
和 cache 语义各有已知边界，先把边界写清比扩大入口更重要。

## 2. `--from-snapshot` 覆盖

静态盘点（45 listed / 39 core）：

```text
支持（13/39 core）：
connections, dataflow analyze, drivers, hierarchy, instances, loads, paths,
ports, trace evidence, trace frontier, trace tb-join, verify claim,
verify consistency
```

不支持（26/39 core）包括：

```text
stats, scope, class, params, search, graph nodes/edges/subgraph,
controlflow analyze/list-conditioned, trace profile/lookup/manifest,
trace constraints/constraint-neighborhood/constraint-chain,
trace covergroups/coverpoints/covergroup, verify structural,
snapshot save/list/compare/delete, filelist prune
```

`--no-cache` 仅 3 个 core 命令暴露：

```text
drivers, loads, trace evidence
```

判断：不支持的命令大多依赖 **SV 源文本/class/constraint/coverage 语义**，
snapshot 当前只保存图，不应为了“统一入口”硬加 `--from-snapshot`。

## 3. Snapshot fidelity

已有测试（2026-11-19 实跑 22 passed）：

```text
sim/tests/unit/test_p158_9_2_snapshot_surface.py
sim/tests/cli/test_trace_snapshot.py
```

锁定：

- edge/node 字段往返保真，唯一显式例外 `condition_ast`；
- live vs snapshot 的 dataflow `is_reachable` / `paths_count` / `all_conditions` 不分叉；
- `trace evidence --from-snapshot` 能查到 signal，但 **source_text 为空**（snapshot 不存 SV 源）；
- 无效 tag / 与 `--file`/`--filelist` 互斥有结构化错误。

结论：snapshot 是**图级快照**，不是源码/证据快照；source-dependent 命令保持 live-only。

## 4. Cache 默认

代码事实：

```text
UnifiedTracer.build_graph(use_cache=False)       # 库默认
_build_pruned_tracer(use_cache=True)             # 仅 prune fallback 路径
```

- 普通 `_build_tracer` 不暴露 `use_cache`，走库默认 false；
- `drivers` / `loads` / `trace evidence` 有 `--no-cache` 显式开关；
- 没有“全局默认开启 cache”的证据，也没有必要为了 serve 打开。

结论：保持现状；若未来给更多命令加 cache，必须同时提供 `--no-cache` 和
cache key/version 的契约测试。

## 5. Session 边界

```text
Session._BUILTIN_OPS == {"version"}
其他 op 由调用方注入 handler
```

现状：

- `Session` 是只读、无 CLI/环境依赖的库接缝；
- 没有 snapshot/cache/serve op；
- CLI `session` 是 hidden dev 命令，不是稳定 agent 入口。

结论：0.3.x 不把 Session 扩成 transport/server；agent 稳定入口仍是 CLI +
`capabilities --json`。

## 6. 建议 / 后续

- P182.5 关闭，不做实现；
- 若未来有真实需求，再单独立项：
  1. 只对**图-only**命令扩 snapshot；
  2. source-dependent 命令需要“snapshot + source bundle”新契约；
  3. cache 默认变更必须先有 `--no-cache` 对照与 key/version 测试；
  4. serve 需要独立的生命周期/并发/安全评估，不在 0.3.x。

## 7. 复现

```bash
python3 tools/eval_p1825_snapshot_surface.py
python3 -m pytest sim/tests/unit/test_p158_9_2_snapshot_surface.py \
  sim/tests/cli/test_trace_snapshot.py -q -p no:randomly
```
