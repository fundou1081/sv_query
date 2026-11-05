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

## 2. 隔离审计（2026-11-05）

首次“硬隔离”有一个真实泄漏：

- profile 只 deny `/tmp/lr_pilot`；
- macOS `/tmp` 是 `/private/tmp` 的 symlink；
- `sandbox-exec` 按 canonical path 匹配，`/tmp/lr_pilot` 规则没有覆盖 `/private/tmp/lr_pilot`。

探针：

```text
cat /private/tmp/lr_pilot/axi.f  → 允许（修复前）
cat /private/tmp/lr_pilot/axi.f  → Operation not permitted（修复后）
```

所以 MiniMax source 之前声称“用了 /tmp/lr_pilot artifact”**不是臆造**，而是泄漏。  
修复：`source.sb` / `t2.sb` 同时 deny canonical `/private/tmp/lr_pilot`。

另一个问题：hard workspace 的 `axi.f` 仍指向 `/tmp/lr_pilot/axi`，T2 被迫在 workspace
里重写 filelist。新增 `rewrite_filelists.py`，生成指向 `/private/tmp/lr_hard_ws` 的
filelist；source/T2 都能直接使用。

## 3. 单题 PoC（修复后，两个模型）

工作区：`/tmp/lr_hard_ws`（只有 AXI/SERV/Pico source copy）。
任务：AXI `m_axi_araddr` direct drivers/loads。

| 臂 | drivers | loads | 结果 |
|---|---|---|---|
| MiniMax source hard | `...m_axi_araddr_reg` | `axi_adapter.m_axi_araddr` | ✅ |
| MiniMax svq hard | `...m_axi_araddr_reg` | `axi_adapter.m_axi_araddr` | ✅ |
| DeepSeek source hard | `...m_axi_araddr_reg` | `axi_adapter.m_axi_araddr` | ✅ |
| DeepSeek svq hard | `...m_axi_araddr_reg` | `axi_adapter.m_axi_araddr` | ✅ |

source 输出没有引用 sv_query 源码；T2 正常调用 CLI。

## 4. 稳定性评估

### 硬隔离

- 修复后 4 个 cell（两模型 × source/T2）在同一个 AXI 任务上全部正确；
- 没有重复 seed，因此**不能评估硬隔离方差**；
- 单题 PoC 只证明隔离机制可用。

### 软隔离（已有 12 题 × 2 seed）

- T2：两 seed 都 12/12，稳定；
- source：MiniMax 7→6，DeepSeek 6→10，方差明显；
- 这支持“T2 稳定”，不支持“source 一定差/模型排名”。

### 仍不能声称

- 硬隔离 12×3 准确率/成本；
- source 完全干净的准确率；
- 模型能力排名。

## 5. 复现

见 [tools/benchmark/hard_isolated/README.md](../../tools/benchmark/hard_isolated/README.md)。

## 6. 结论

- 硬隔离已从“prompt 约束”推进到 OS 层 deny（source 臂）；
- 剩余问题是 **模型额度 + 12×3 运行成本**，不是 sandbox 机制本身；
- 在额度恢复前，不做全矩阵结论。
