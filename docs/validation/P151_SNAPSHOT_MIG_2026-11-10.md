# P151 snapshot MIG persistence

**日期**: 2026-11-10
**状态**: ✅

## 1. 问题

P149 支持 `verify consistency --from-snapshot`，但 snapshot 只存 SignalGraph：
`connection` check 因缺 MIG 只能 unknown。

## 2. 实现

- `ModuleInstanceGraph.to_dict()` / `from_dict()`；
- `snapshot save` 写入 `module_graph`（instances + ports）；
- `_load_tracer_from_snapshot` 重建 MIG，并挂到 tracer；
- `PathResolver` / `SignalTracer` 同步带 MIG；
- 旧 snapshot 没有 `module_graph` → `connection` 仍显式 unknown，不伪造 pass。

## 3. 实测

临时 snapshot（arch_pair）：

```text
verify consistency --from-snapshot p151 --checks connection,bit
verified = true
unknown_checks = []
bit_mapping: pass
connection: pass, checked=4
```

## 4. 测试

`test_verify_consistency_snapshot.py` 更新：

```text
new snapshot -> connection pass + checked > 0
legacy snapshot without module_graph -> connection unknown（逻辑保留）
```

## 5. 边界

- 新 snapshot 包含 MIG，文件更大；
- MIG 只存 instance/port 映射，不存语义/AST；
- 旧 snapshot 不回填，不静默 fallback。
