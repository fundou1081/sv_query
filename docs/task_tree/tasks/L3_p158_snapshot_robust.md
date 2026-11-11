# Task: P158.7 snapshot 构造与损坏输入

**状态**: ✅ 完成
**日期**: 2026-11-11

## 结果

- `UnifiedTracer.load_snapshot()` 成为唯一 snapshot 构造入口（graph + MIG + tracers + path resolver）；
- `_load_tracer_from_snapshot` 不再手工设 4 个私有字段；
- `ModuleInstanceGraph.to_dict/from_dict` 持久化 `module_ports`；
- `SnapshotManager.load/show` 对损坏 JSON/根对象显式错误，不裸 traceback；
- `snapshot list` 使用文件名作为 tag，损坏文件作为可见 error entry；
- body tag 不一致显式 `tag_mismatch`；
- 3 个 regression（损坏文件、tag 权威、MIG roundtrip/tracer）。

## 边界

snapshot 仍不存 class/covergroup semantic state；`load_snapshot` 显式置 None。
