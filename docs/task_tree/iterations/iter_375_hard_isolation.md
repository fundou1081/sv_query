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

## ⚠️ 阻塞

MiniMax-M3 headless 返回 HTTP 429：Token Plan 用量上限。  
因此 2 模型 × 12 题 × 3 seed 全矩阵没有完成；这只能算隔离机制 PoC。

## 🔜 下一步

P69.7.2：额度恢复后跑全矩阵；source 硬隔离 profile 已就绪。
