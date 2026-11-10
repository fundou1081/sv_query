# Iteration 452: P139 frontier worker nits

**状态**: ✅
**日期**: 2026-11-09

## 来源

Worker `svq-p139-review2` 独立验证：**APPROVE WITH NITS**。

## 修复

- 纯环 → `cycle_or_all_seen`；
- instance_boundary 的 instance 指向实例本身；
- `max_frontier` 全局预算；
- frontier 行按 node 去重；
- `path` 文档化；
- note 去掉 FIFO 字样；
- graph 异常显式 ValueError；
- `max_depth >= 1` 校验；
- params 增加 max_frontier。

## 验证

`test_frontier.py: 5 passed`；check 门禁全绿。
