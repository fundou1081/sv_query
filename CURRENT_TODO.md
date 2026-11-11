# CURRENT_TODO — 当前正在做的事

> **计划源**: 代码修改计划以 [PLAN.md](PLAN.md) 为**全局唯一真相源**；本文件只记录"此刻"的上下文。
> **产品方向**: [product_direction_2026-10-31](docs/architecture/product_direction_2026-10-31.md) — agent RTL 查询 + 客观校验；动态值由外部波形工具提供。
> **交接状态**: [docs/dev/HANDOFF.md](docs/dev/HANDOFF.md) — 剩余工作、环境、worker 协议。
> **最后更新**: 2026-11-11 21:30 GMT+8 (P164 文档状态校准完成)

---

## 🎯 当前计划（以 [PLAN.md](PLAN.md) 为准）

- **当前 item**: **P158.11.2b generic long-query timeout** `<待做>`
  - 按 HANDOFF §12 的接手顺序：P158.11.2b → P158.9.2 → P158.12 → 17 skip 分类
  - 现状：`paths` 已有 budget/deadline；`dataflow._find_paths(cutoff=50)` 只有路径条数上限，
    `dataflow analyze` 也没有 `--timeout`（2026-11-11 实测）
  - 验收：超预算返回 `truncated` / `unknown_kind:"search_budget_exhausted"`，
    不得伪装 `found:false`；有 true-positive 测试；canonical 仍 0 failed

### 已完成（本轮 P164，文档状态校准）

- P164.1 计划树修正：current item 指向 P158.11.2b；P158.9 拆出 9.2；
  `---- ` 不可见项改为 `--`；`check_plan` 新增 P9（3 个以上短横线即报错）+ 字母后缀 id
- P164.2 CURRENT_TODO / HANDOFF / 会话日志：HEAD、相对命令、解释器、硬编码路径数（26）
- P164.3 契约/基线/限制文档：SEMANTIC_CONTRACTS §2.3/§11、INDEX 基线、README 计数、
  KNOWN_LIMITATIONS §4、ARCHITECTURE 过期声明、P159 §6.1/§6.2
- P164.4 `check_docs` 计数漂移：基准只取 INDEX「当前基线」章节且只认 `N passed`；
  文件名带日期 = 时点快照

### 长期挂起 / 已放弃（不再作为"下一步"）

| 项 | 状态 | 原因 |
|---|---|---|
| P62.2 交互式 debug | `<待做>`（**保持 gate**） | 不是核心 query/verify；保持 gate，不主动排期 |
| P69.7 硬隔离 12×2 fixed 全矩阵 | `<放弃>` | 环境成本高，产品问题未定 |
| P88 外部 VeriBug 验证 | `<放弃>` | 成本/环境；已用 OpenTitan 真实 block + independent intake 替代 |

---

## 📦 仓库状态

- **分支**: `main`；HEAD 以 `git log -1` 为准（2026-11-11 核对为 `56c10fa9`）
- **全量基线**: 见 [docs/INDEX.md 当前基线](docs/INDEX.md#-当前基线-单一真相源--计数只写在这里)（单一真相源，本文不写死计数）
- **命令面**: 45 命令 = core 40 + exp 5（audit / diagnose / trace overview / review render / architecture graph）
- **环境**: `python3` 必须是装了 typer/pyslang 的解释器（本机 `~/miniconda3/bin/python3`），
  否则 CLI 子进程测试会成片假失败
- **当前重点**: 文档状态已与代码对齐；下一步回到核心查询的有界性（P158.11.2b）

---

## ✅ 最近完成

| 项 | 内容 | 结果 |
|---|---|---|
| P164 | 文档状态校准（接手） | PLAN/CURRENT_TODO/HANDOFF/契约/基线/限制对齐；check_plan + check_docs 加固 |
| P162/P163 | 交接文档 + 会话记录 | 可交接、可追溯 |
| P160/P161 | opensource 分诊与修复 | 38 failed → 0 failed；17 个显式 skip |
| P158.1~11.2a | 语义契约波次 1~3 | 数据边/有界/确定性/corpus/写入/verified/snapshot/MIG/CI |
| P152/P153/P155/P156 | SPI 收口 | 9-task corpus；transitive fanin；reciprocity 误报 128→0 |

详见 [PLAN.md](PLAN.md)、[P158 remediation](docs/validation/P158_REMEDIATION_2026-11-11.md)、
[P161 remediation](docs/validation/P161_OPENSOURCE_REMEDIATION_2026-11-11.md)。

---

## 🔜 下一步（按顺序，未开工）

```text
1. P158.11.2b 通用长查询 timeout      <- 当前 item
2. P158.9.2   snapshot surface 矩阵
3. P158.12    P2 清理（26 个硬编码路径 / no:randomly / impact 定位 / 空 expression self-loop）
4. 17 个 opensource skip 的最终处置（归档 retired exp / 补 fixture / 保留显式 skip）
```

未决讨论项（等方豆拍板）：`trace impact` 是否降 exp；真实项目依赖闭包是否固化进 repo。
