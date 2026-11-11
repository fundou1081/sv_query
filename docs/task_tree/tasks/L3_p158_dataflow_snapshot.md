# Task: P158.11.1 dataflow snapshot + frontier cap

**状态**: ✅ 完成
**日期**: 2026-11-11

## 结果

- `dataflow analyze --from-snapshot <tag>`：复用 `_load_tracer_from_snapshot`，不再重新 parse；
- `--from-snapshot` 与 `--file/--filelist` 互斥，`--evidence` 显式不支持 snapshot；
- frontier `--max-visits` 可配置，`summary.truncated` 可见；
- 回归：snapshot dataflow、互斥、frontier max_visits。
