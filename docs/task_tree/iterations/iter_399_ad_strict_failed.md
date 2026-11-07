# Iteration 399: 严格 A/D 尝试（P95）

**状态**: ⏭️ 放弃
**日期**: 2026-11-07

## 尝试

- T2 deny repo；
- query-only workspace（无 source/filelist）；
- prompt 强制 `--from-snapshot`；
- session telemetry 审计。

## 结果

- strict smoke 434s，exact 但 protocol 失败；
- query-only smoke 9.5min 未结束，手动终止；
- agent 搜索 repo/site-packages、读 snapshot JSON、尝试 pip/git。

## 结论

文件系统收紧不能强制工具调用；需要 harness tool allowlist。未完成 24-cell 严格对比。
