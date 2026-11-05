# Iteration 375: sandbox-exec 硬隔离 PoC（PLAN P69.7.1）

**Metadata**:
- **Iteration #**: 375
- **Task Tree Level**: L2（PLAN `P69.7`）
- **Created**: 2026-11-05 GMT+8
- **Author**: 方豆 / AI 助手
- **Outcome**: ⚠️ PoC 完成；全矩阵被 MiniMax 429 阻塞

## 🎯 动作

- 新增 `tools/benchmark/hard_isolated/{source,t2}.sb`；
- 使用 macOS `sandbox-exec` 包裹 `dsh --profile headless`；
- source profile：
  - deny read sv_query repo；
  - deny read `/tmp/lr_pilot`；
  - deny exec `sv_query`；
- T2 profile：deny `/tmp/lr_pilot`，允许 repo（editable install 依赖）；
- 设置 `DSH_PERMISSION_MODE=danger-full-access` 让外部 sandbox 成为边界。

## ✅ 验证

```text
source 读 repo → Operation not permitted
source 执行 sv_query → denied
```

DeepSeek-Flash 单题 AXI fanin：

| 臂 | 结果 |
|---|---|
| source hard | drivers/loads correct |
| svq hard | drivers/loads correct |

## ⚠️ 额度恢复后的重试

- MiniMax-M3 quota 恢复；source/T2 单题通过；
- 仍只完成单题 PoC，12×3 全矩阵未跑；
- MiniMax source 输出声称读过 `/tmp/lr_pilot` artifact，但 sandbox 已 deny，
  需审计是否臆造/泄漏。

## 🔜 下一步

P69.7：跑全矩阵；先审计 source 的 artifact 声明。
