# Task: P166 opensource golden calibration

**状态**: ✅ 完成
**日期**: 2026-11-12

## 触发

2026-11-12 接手复核发现 HANDOFF 声称的 opensource
`114 passed / 17 skipped / 0 failed` 已过期：实际 3 failed。

## 根因

- R-026 清除恒自环边后，stats DRIVER/edge 计数变化；
- P158.11.2b 给 dataflow 增加 `expansions/truncated/search_status` 字段；
- 旧 golden 未重捕，且 `elapsed_s` 被错误冻结进 golden（时钟波动）。

## 处理

- `_normalize` 显式移除 `elapsed_s`（非语义 golden）；
- 重捕 stats/dataflow 的 4 个 golden（strict_uart/prim_arbiter）；
- 保持无 auto-bless：缺失 golden 仍直接失败；
- 重新验证 opensource。
