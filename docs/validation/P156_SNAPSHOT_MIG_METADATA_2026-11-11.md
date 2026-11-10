# P156 snapshot MIG metadata

**日期**: 2026-11-11
**状态**: ✅

## 1. 问题

P151 已让新 snapshot 持久化 MIG，但 `snapshot list` 只显示
node/edge count；agent 无法在查询前判断：

```text
这个 snapshot 有没有 module_graph？
connection/instances 能不能用？
```

旧 snapshot 与 new snapshot 混在一起时尤其危险。

## 2. 修复

`SnapshotManager.show()` 增加：

```json
{
  "module_graph_present": true,
  "module_graph_instances": 214,
  "module_graph_ports": 1734
}
```

`snapshot list <tag>` 可直接预检。

## 3. 兼容性

- 新 snapshot：MIG 可用；
- 旧 snapshot：`module_graph_present=false`，相关命令显式 unknown/失败；
- 不自动重建、不静默 fallback。

## 4. 测试

`test_verify_consistency_snapshot.py` 已断言新 snapshot 的
`module_graph_present=true` 且 instances > 0。
