# CURRENT_TODO — 当前正在做的事

> **计划源**: 代码修改计划以 [PLAN.md](PLAN.md) 为**全局唯一真相源**；本文件只记录"此刻"的上下文。
> **产品方向**: [product_direction_2026-10-31](docs/architecture/product_direction_2026-10-31.md) — agent RTL 查询 + 客观校验；动态值由外部波形工具提供。
> **交接状态**: [docs/dev/HANDOFF.md](docs/dev/HANDOFF.md) — 剩余工作、环境、worker 协议。
> **最后更新**: 2026-11-11 23:55 GMT+8 (P158.9.2 完成)

---

## 🎯 当前计划（以 [PLAN.md](PLAN.md) 为准）

- **当前 item**: **P158.12 P2 清理** `<待做>`
  - 剩余：26 个测试文件硬编码 `/Users/fundou` 路径、`-p no:randomly` no-op、
    空 expression self-loop；12.1（trace impact 降 exp）已完成
  - 按 HANDOFF §12 顺序：~~P158.11.2b~~ → ~~P158.9.2~~ → P158.12 → 17 skip 分类

### 已完成（本轮 P158.9.2，iter_493）

- `to_dict/from_dict` 补齐：condition_chain / source(SignalSource) /
  function_return / is_function_call / node+edge extra（JSON-safe 过滤）
- 显式不保证：condition_ast（运行期 AST）、class/covergroup 状态（恒 None）
- `docs/dev/SNAPSHOT_SURFACE.md`：字段级 + 命令级快照能力面矩阵（单一权威）
- 机械 gate：`test_p158_9_2_snapshot_surface.py` 10 项（往返保真 / 旧格式兼容 /
  CLI live-vs-snapshot parity）
- 实测证据：condition_chain 丢 32/32 → 0；source 丢 44/44 → 0；
  effective_condition 重算 72/72；快照体积 +33%（64MB 上限不变）

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
- **命令面**: 45 命令 = core 39 + exp 6（audit / diagnose / trace overview / review render / architecture graph /
  trace impact——**2026-11-11 降级**：未标定启发式不得伪装稳定，见 KNOWN_LIMITATIONS §3.4）
- **环境**: `python3` 必须是装了 typer/pyslang 的解释器（本机 `~/miniconda3/bin/python3`），
  否则 CLI 子进程测试会成片假失败
- **当前重点**: P158.9.2 已完成（快照往返保真 + SNAPSHOT_SURFACE.md 矩阵）；下一步 P158.12 P2 清理

---

## ✅ 最近完成

| 项 | 内容 | 结果 |
|---|---|---|
| P158.11.2b | 通用长查询 timeout（iter_491） | SearchBudget 唯一实现；dataflow 有界 DFS + CLI 预算参数 + truncated 契约 |
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
1. P158.12    P2 清理（26 个硬编码路径 / no:randomly / 空 expression self-loop）<- 当前 item
2. 17 个 opensource skip 的最终处置（归档 retired exp / 补 fixture / 保留显式 skip）
3. P165.1     signal.py 全图扫描 pred/succ 化（O(V×E)→O(度)，小改动）
4. P165.3/4   外部故障集 + filelist 闭包自动化（开源前）
5. P165.2     packaging 重命名（随开源破坏性窗口）
```

未决讨论项（等方豆拍板）：真实项目依赖闭包是否固化进 repo。
已拍板（2026-11-11）：`trace impact` 降 exp（已落地，P158.12.1）；方案 B 拒绝、方案 C 暂缓（见 PLAN P165）。
