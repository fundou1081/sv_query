# P154 snapshot-executable frontier probes

**日期**: 2026-11-10
**状态**: ✅

## 1. 问题

P152 N-3：

```text
frontier next_probes = connections/instances/ports <node>
但这些命令不支持 --from-snapshot
```

agent 在 snapshot 模式下跟着 probe 会撞墙。

## 2. 实现

新增 snapshot 支持：

```text
instances --from-snapshot
connections --from-snapshot
ports --from-snapshot
```

frontier 在 snapshot 模式生成 probe 时追加：

```text
--from-snapshot <tag>
```

示例：

```text
connections spi_host.u_window --from-snapshot opentitan_spi
```

## 3. 快照实例兼容

snapshot tracer 的 `get_instances()` 从 MIG 读取（P151 持久化），
不再依赖 semantic adapter。

## 4. 测试

```text
test_frontier_snapshot_probes.py
```

创建临时 snapshot → frontier → 对每个 next_probe 直接执行，
全部 rc=0 / ok=true。

## 5. 边界

- 旧 snapshot 无 MIG 时，connections 仍显式 unknown/失败；
- probe 只保证同一个 snapshot 上下文可执行，不保证语义上一定有结果。
