# Task: P165.1 signal/structural full-graph scans

**状态**: ✅ 完成
**日期**: 2026-11-12

## 结果

- `signal.py` 的 12 处 `graph.edges()` 全图扫描改为 `predecessors/successors`；
- 新增 `_incoming_pairs` / `_outgoing_pairs`，本地邻居 O(度)；
- `structural.py` 的 `_port_map` 从 per-instance O(I×E) 改为一次 `_port_index` O(V+E)；
- 新增静态回归 `test_signal_no_full_graph_scan.py`；
- canonical 2724 passed / 0 failed / 123 deselected。
