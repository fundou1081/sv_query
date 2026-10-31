# L2 — P31 低完成度能力降级 exp

**Created**: 2026-10-31 GMT+8
**方豆**: "audit diagnose view 这几个，好像功能完成度低，移动到实验档位，默认不提供吧。"

## 范围

- `audit` / `diagnose`：core → exp，默认不推荐、不出现在 capabilities 默认输出
- `view` 全部命令（visualize*/arch*/design*/trace overview）：view → exp
- CLI 默认 `--help` 隐藏这些入口；老路径仍可显式调用（兼容）
- `capabilities --include-exp` 才列出

## 验收

- 默认 capabilities 只剩 core（23 命令）
- `--include-exp` 可见 exp 命令
- `svq --help` 不显示 audit/diagnose/visualize/arch/design/overview
- 现有测试仍可调用老路径；全量门禁 0 failed

## 完成记录（2026-10-31）

- P31.1/P31.2 ✅ iter_327：audit/diagnose/view 降级 exp；默认 help/capabilities 不提供
- 全量 2635 passed（含 P32）
