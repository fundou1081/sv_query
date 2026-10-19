# AGENTS.md — sv_query 协作入口 (Process & Index)

> **维护人**: 方豆 + AI 助手 · **状态**: 强制执行 · **版本**: v2.0 (2026-10-19 重构为"流程入口 + 细则索引")
> **适用**: 所有在本仓库工作的 AI 助手 (QClaw / Claude Code / Copilot / DeepSeek Harness 等) 与人类开发者。

---

## 🎯 项目一句话

**sv_query** = SystemVerilog 静态分析工具，基于 pyslang + 自研 4 维分析：
**L1 module 抽取 / L2 端口连接 / L3 内部信号 / L4 可视化**。

目标：让验证工程师 (或其 agent) 直接问"这个信号谁驱动的"，而不是读代码。
**主消费者是 agent** → 查询面以只读、JSON、稳定 schema 为第一优先。

---

## 📌 这份文件是什么

**本文只写"该怎么协作 + 细则在哪"。具体条例不在这里展开。**

| 想知道什么 | 看哪里 |
|---|---|
| 硬性禁止项、产品不变量、违规处置 | [docs/dev/DISCIPLINE.md](docs/dev/DISCIPLINE.md) |
| 编码风格、设计决策逻辑、与方豆协作规则 | [docs/dev/CODING_STYLE.md](docs/dev/CODING_STYLE.md) |
| 任务生命周期、迭代记录、文档卫生、机械检查、提交/合并 | [docs/dev/WORKFLOW.md](docs/dev/WORKFLOW.md) |
| 提交前逐项检查清单 | [docs/dev/REVIEW_CHECKLIST.md](docs/dev/REVIEW_CHECKLIST.md) |
| 测试怎么跑、marker、落盘隔离 | [TESTING.md](TESTING.md) |
| 文档总索引与当前基线计数 | [docs/INDEX.md](docs/INDEX.md) |
| 架构分层与模块职责 | [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) |
| 当前在做什么 | [CURRENT_TODO.md](CURRENT_TODO.md) |
| 已知缺陷与能力边界 | [docs/KNOWN_LIMITATIONS.md](docs/KNOWN_LIMITATIONS.md) |

---

## 🔄 开工前必读顺序 (长对话压缩 / 新 session 恢复时强制执行)

1. **本文件** —— 确认协作方式与细则位置
2. [CURRENT_TODO.md](CURRENT_TODO.md) —— 此刻在做什么、仓库状态
3. [docs/dev/DISCIPLINE.md](docs/dev/DISCIPLINE.md) —— 硬规则 (压缩后必重读)
4. 最近 10 个 commit + [docs/task_tree/overview.md](docs/task_tree/overview.md) 的最近 3 行

**禁止**凭残留印象继续工作。上下文会被压缩，**只有文档留得住**。

---

## 🚫 铁律速查 (违反任一条 = 停下来报告方豆)

**硬性禁止** (详见 [DISCIPLINE.md](docs/dev/DISCIPLINE.md))：

| # | 规则 | 一句话 |
|---|---|---|
| 1 | 禁 `--no-strict` | 命令失败要诊断根因，不许开逃生口 |
| 2 | 禁 silent fallback | 失败必须显式：报错 / sentinel / 抛异常 |
| 3 | 禁 `except ...: pass` | 吞异常 = 让失败与正常不可区分 |
| 4 | 禁 `-f/--file` 传 filelist | filelist 一律 `--filelist`（误用会触发原生 SIGTRAP） |
| 5 | 失败按序归因 | fixture → 功能代码 → filelist → 环境 → (最后) 工具 bug |

**产品不变量** (改它 = 改产品定义，必须先问)：

| # | 不变量 |
|---|---|
| I1 | **不修改用户的 RTL / 工程文件** — 写能力只能放在 `tools/`，默认关闭 |
| I2 | `core` 层**只读 + JSON + 稳定 schema**（消费者是 agent） |
| I3 | **单一实现原则** — 同一语义只允许一份实现，发现两份就合并或删除 |
| I4 | 降级必须显式：实验能力进 `exp/`，在 `capabilities` 里降级，不伪装稳定 |
| I5 | 登记缺陷要写**可观察后果**（什么输入 → 什么错误输出），按输入形态枚举 |

---

## 🔧 工作流速查

完整流程见 [WORKFLOW.md](docs/dev/WORKFLOW.md)。

**开工**（缺一步不要动手）：
建 `docs/task_tree/tasks/L<N>_<任务>.md` → 更新 `CURRENT_TODO.md` → 挂到 `overview.md` → 写可验证的 sub-task

**迭代**：一个迭代 = 一个可观察动作；每个迭代写 `docs/task_tree/iterations/iter_NNN_*.md`（**边做边写**）

**收尾**：更新 `CURRENT_TODO.md`（移入"最近完成"）+ `overview.md` 汇总表 + 长期 todolist；
涉及新文档 → 登记 `docs/INDEX.md`；涉及计数 → 只改 `docs/INDEX.md` 的"当前基线"

**完成判定**：**代码 ✅ + 测试 ✅ + 文档 ✅**。只做完代码就说"完成了" = 谎报进度。

---

## 📋 提交前必跑

```bash
python3 -m pytest sim/tests/ -m "not opensource" -q -p no:randomly   # 全量门禁
python3 tools/check_docs.py                                          # 死链/归档/未登记
python3 tools/check_except_pass.py                                   # 禁 except:pass
python3 tools/check_cli_layers.py                                    # CLI 分层 R1~R8
python3 tools/gen_cli_surface.py --check                             # CLI 清单一致
```

逐项清单见 [REVIEW_CHECKLIST.md](docs/dev/REVIEW_CHECKLIST.md)。
涉及查询/图/CLI 语义的改动**必须**额外跑真实多文件项目冒烟（见 [WORKFLOW.md](docs/dev/WORKFLOW.md) §4）。

---

## 🗂️ 项目设施 (位置固定，不得新建平行体系)

| # | 设施 | 唯一位置 | 作用 |
|---|---|---|---|
| 1 | **协作入口** | `AGENTS.md` (本文件) | 流程 + 细则索引，压缩后必重读 |
| 2 | **细则** | `docs/dev/` | 纪律 / 风格 / 流程 / 清单 |
| 3 | **当前 todolist** | [CURRENT_TODO.md](CURRENT_TODO.md) | **此刻**在做什么 — 唯一稳定追踪点 |
| 4 | **迭代记录** | [docs/task_tree/](docs/task_tree/) | 任务树 + 每次迭代一个文件 |
| 5 | **架构决策** | [docs/architecture/](docs/architecture/) + [ARCHITECTURE.md](docs/ARCHITECTURE.md) | 架构变更 / 决策记录 |
| 6 | **测试** | [TESTING.md](TESTING.md) + `sim/tests/` | 唯一测试手段与流程 |
| 7 | **文档索引** | [docs/INDEX.md](docs/INDEX.md) | 唯一文档入口 + 计数单一真相源 |

**辅助 (不是入口)**：[docs/ARCHITECTURE_TODOLIST.md](docs/ARCHITECTURE_TODOLIST.md)（架构改造长期追踪）、
[docs/TODO.md](docs/TODO.md)（版本级待办）、`memory/`（按日经验）、
[docs/debugging_lessons/](docs/debugging_lessons/)（单次 debug 复盘）。

**禁止**新建 `records/` `logs/` `notes/` 等与上表重复的目录 —— 要加内容就加进已有位置。

---

## 📢 主动告知 (原则，细则见 CODING_STYLE §11)

发现这些情况**主动说**，不要默默决定或跳过：缺少测试 / 更好的架构 / 更好的方案 /
更简洁的实现 / 更高效的算法 / 登记过的"已知局限"实际更严重。

说明格式：**现状 → 问题 → 建议 → 代价**，然后**等方豆决定**。
大改动 (架构 / 重构 / 换算法) 必须**先说后做**；小而安全的改动可以直接做，但要在总结里列出来。

---

## 📝 版本

- **v2.0 (2026-10-19)** — 重构为"流程入口 + 细则索引"：正文拆到
  [docs/dev/DISCIPLINE.md](docs/dev/DISCIPLINE.md)、[CODING_STYLE.md](docs/dev/CODING_STYLE.md)、
  [WORKFLOW.md](docs/dev/WORKFLOW.md)、[REVIEW_CHECKLIST.md](docs/dev/REVIEW_CHECKLIST.md)；
  新增产品不变量 I1~I5（只读 / core 契约 / 单一实现 / 显式降级 / 可观察后果）；
  流程补：真实项目冒烟、机械保障优先、提交用 `-F`、合并前全量门禁。
  方豆指示："重新确立一份项目的开发纪律，写一份 AGENTS.md，流程类的放这里，
  具体要求用 link 放到其他文件。"
- v1.7 (2026-09-09 iter_229) — 新增核心纪律 4（`-f` 只接源码，filelist 用 `--filelist`）。
- v1.6 (2026-09-08 iter_190) — 纪律 2.5 补机械保障 `tools/check_except_pass.py`
  （"已全仓清零"的声明被实测证伪：src/ 仍有 52 处）。
- v1.5 (2026-09-08) — 新增文档卫生小节（INDEX 唯一入口 / 归档不删 / 计数单一真相源）。
- v1.4 — 新增"全面禁止 `except: pass`"。
- v1.3 — 新增"任务前后必须更新文档"，确立完成判定 = 代码+测试+文档。
- v1.2 — 新增项目设施表 + 迭代记录规范 + 可信开发纪律（先诊断再动手 / 冲突要停）。
- v1.1 — 新增代码决策逻辑 + 主动告知 + 自我审视清单。
- v1.0 (2026-08-27) — 初版：禁止 `--no-strict`、禁止 fallback。
