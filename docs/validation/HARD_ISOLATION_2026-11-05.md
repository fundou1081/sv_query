# 硬隔离 PoC：sandbox-exec + headless DSH

**日期**: 2026-11-05
**PLAN**: P69.7（部分）
**目标**: 让 source-only agent 在 OS 层无法读取 sv_query 仓库/旧工作区，
也无法执行 `sv_query`，而不是只靠 prompt 约束。

## 1. 机制

`tools/benchmark/hard_isolated/{source,t2}.sb`：

- `source.sb`：`allow default` + deny repo / `/tmp/lr_pilot` + deny exec `sv_query`；
- `t2.sb`：deny `/tmp/lr_pilot`，但允许 repo（editable install 的 `src/cli` 依赖）；
- 外部 `sandbox-exec` 负责边界；设置 `DSH_PERMISSION_MODE=danger-full-access`
  避免 DSH 内部 bash sandbox 与本机后端冲突。

已验证：

```text
source profile 读 repo README → Operation not permitted
source profile 执行 sv_query   → denied
```

## 2. 单题 PoC（两个模型）

工作区：`/tmp/lr_hard_ws`（只有 AXI/SERV/Pico source copy）。
任务：AXI `m_axi_araddr` direct drivers/loads。

| 臂 | drivers | loads | 结果 |
|---|---|---|---|
| MiniMax source hard | `...m_axi_araddr_reg` | `axi_adapter.m_axi_araddr` | ✅ |
| MiniMax svq hard | `...m_axi_araddr_reg` | `axi_adapter.m_axi_araddr` | ✅ |
| DeepSeek source hard | `...m_axi_araddr_reg` | `axi_adapter.m_axi_araddr` | ✅ |
| DeepSeek svq hard | `...m_axi_araddr_reg` | `axi_adapter.m_axi_araddr` | ✅ |

source 输出没有引用 sv_query 源码；T2 正常调用 CLI。

## 3. 阻塞

- MiniMax-M3 额度已恢复；source/T2 单题都能正常调用并通过。
- 但 2 模型 × 12 题 × 3 seed 的硬隔离矩阵仍未跑。
- MiniMax source 输出声称用过 `/tmp/lr_pilot` artifact，而 source profile 已 deny 该路径；
  这可能是模型臆造，也可能是隔离泄漏，**需要审计**。不能据此声称 source 完全干净。
- 单题 PoC 只能证明隔离机制可用，不能证明准确率/成本。

## 4. 复现

见 [tools/benchmark/hard_isolated/README.md](../../tools/benchmark/hard_isolated/README.md)。

## 5. 结论

- 硬隔离已从“prompt 约束”推进到 OS 层 deny（source 臂）；
- 剩余问题是 **模型额度 + 12×3 运行成本**，不是 sandbox 机制本身；
- 在额度恢复前，不做全矩阵结论。
