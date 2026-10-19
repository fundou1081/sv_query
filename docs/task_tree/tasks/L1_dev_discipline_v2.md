# L1: 开发纪律 v2.0 + AGENTS.md 重构为流程入口

**状态**: ✅ 完成 (2026-10-19, iter_242)
**发起**: 方豆 — "重新确立一份项目的开发纪律，并且写一份 Agents.md，这个源文件记录流程类的，
具体要求用 link 的方式存放到其他文件。比如项目开发纪律，coding style 等等。"
**产出**: [AGENTS.md](../../../AGENTS.md) + [docs/dev/](../../dev/)

---

## 背景

`AGENTS.md` 从 2026-08-27 起持续追加，到重构前 **522 行**，混合了三类内容：

| 内容类型 | 占比 | 问题 |
|---|---|---|
| 流程（开工/迭代/收尾、记录在哪） | ~30% | 和纪律细则混在一起，找起来要滚动 |
| 硬规则细则（为什么禁 --no-strict、SIGTRAP 原理…） | ~45% | 篇幅压过流程，agent 读完后容易只记住规则忘了流程 |
| 历史与版本 | ~25% | 版本日志 30 行 |

**根本问题**: 这是一个"什么都有"的文档，而方豆要的是
**流程入口 + 链接索引** —— 需要时再展开，不需要时不占读者注意力。

## 目标

1. `AGENTS.md` 只保留：项目定位、必读顺序、铁律速查（一行一条）、工作流、设施表、提交前命令、版本
2. 细则拆到 `docs/dev/`，每份**单一职责**
3. 顺手"重新确立"纪律内容：把近半年踩过的坑变成可执行的条款
4. 所有 link 可达（`tools/check_docs.py` 死链 = 0），新文档登记进 `docs/INDEX.md`

## 拆分方案

| 文件 | 职责 | 行数 |
|---|---|---|
| [AGENTS.md](../../../AGENTS.md) | 流程 + 索引（本文档你正在看的入口） | 149 |
| [dev/DISCIPLINE.md](../../dev/DISCIPLINE.md) | 产品不变量 I1~I5 + 5 条硬规则 + 归因顺序 + 例外 + 违规处置 + 历史由来 | 175 |
| [dev/CODING_STYLE.md](../../dev/CODING_STYLE.md) | 先探索后决策 / 单一实现 / 修根因 / 函数职责 / 结构化数据 / 注释 / 协作规则 | 173 |
| [dev/WORKFLOW.md](../../dev/WORKFLOW.md) | 任务生命周期 / 迭代记录 / 文档卫生 / 测试与冒烟 / 机械检查 / ADR / 提交合并 | 187 |
| [dev/REVIEW_CHECKLIST.md](../../dev/REVIEW_CHECKLIST.md) | 机械检查命令 + 四组自检 + 反模式表 + 完成定义 | 100 |

## "重新确立"具体加了什么（不是简单搬家）

| 新增 | 来源教训 |
|---|---|
| **产品不变量 I1：不修改用户 RTL** | 本轮工作确立的产品约束（写能力只进 `tools/`） |
| **不变量 I3：单一实现原则** | iter_240/241：`loads` 两份遍历分叉出 `"None.sig"` 假 id |
| **不变量 I5：登记缺陷写可观察后果** | iter_241：登记写"无跨模块支持"，实际是"任何不给 module 的调用都静默空" |
| **WORKFLOW §5 机械保障优先** | 规则写进文档没检查器 → 会回归（`except: pass` 曾声称清零，实测 52 处） |
| **WORKFLOW §3 教训：计数要核验 diff** | iter_240 提交信息声称更新了 INDEX 计数，实际没改，漂移 4 个迭代 |
| **WORKFLOW §4 真实项目冒烟** | 三次"fixture 全绿掩盖真实 bug" |
| **CODING_STYLE §8 禁止过期注释** | iter_241 顺带清掉引用已删除类 `TraceResult` 的 docstring |
| **REVIEW_CHECKLIST §6 反模式表** | 把反复犯的错做成对照表，比清单更好用 |

## 验证

- `python3 tools/check_docs.py`：死链 0 / 归档越界 0 / 未登记 0 / 计数漂移 0
- 交叉引用同步更新（避免"链接指向入口、入口再跳一次"）：
  `EXTRACTION_FAILURES.md`（4 处 → DISCIPLINE）、`KNOWN_LIMITATIONS.md`（→ DISCIPLINE §4）、
  `ARCHITECTURE_TODOLIST.md`（→ CODING_STYLE §5）、`USER_GUIDE.md`（修正"AGENTS.md = 已知限制"的错记）、
  `INDEX.md`（文档卫生 → WORKFLOW §3）
- 纯文档改动，未触碰 `src/` 与 `sim/`；全量门禁沿用 iter_241 的结果（同一份代码）

## 遗留

- 规则编号（1~5）保持不变 → 其他文档里"核心纪律 #2 / #4"的引用仍然成立，无需全仓改写
- `memory/` 与 `docs/task_tree/iterations/` 里的历史引用是时间点快照，按文档卫生规则**不回改**
