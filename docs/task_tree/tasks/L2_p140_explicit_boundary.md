# Task: P140 explicit-boundary guided trace

**状态**: ✅ 完成
**日期**: 2026-11-09

## 交付

- `examples/project_adaptations/opentitan_fifo/trace_with_map.py`；
- I2C S1 真实回放：`nakok.q -> fmt_flag_nak_ok`；
- 空 map / 缺 evidence 负例；
- 2 个回归测试。

## 边界

core 不自动识别 FIFO；runner 只拼接显式 boundary。
