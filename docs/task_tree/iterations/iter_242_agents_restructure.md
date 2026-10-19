# Iteration 242: `AGENTS.md` 重构为流程入口 + 开发纪律 v2.0

**Metadata**:
- **Iteration #**: 242
- **Task Tree Level**: L1
- **Parent Task**: `docs/task_tree/tasks/L1_dev_discipline_v2.md`
- **Created**: 2026-10-19 GMT+8
- **Author**: 方豆 / AI 助手 (方豆: "重新确立一份项目的开发纪律，并且写一份 Agents.md，这个源文件记录流程类的，具体要求用 link 的方式存放到其他文件。比如项目开发纪律，coding style 等等。")
- **Outcome**: ✅ 成功 (522 行单文件 → 149 行入口 + 4 份职责单一的细则; 新增产品不变量与 6 条可执行条款)

## 🎯 本次目标

把 `AGENTS.md` 从"什么都有"（522 行）改成**流程入口 + 链接索引**，
细则（开发纪律 / coding style / 工作流 / 检查清单）落到 `docs/dev/`。

同时**重新确立**纪律本身 —— 不是 Ctrl+C 搬家，而是把近半年踩过的坑变成可执行条款。

## 📊 开工时的状态

- `AGENTS.md` 522 行：硬规则细则占 ~45%，流程只占 ~30%，版本日志 ~25%
- `docs/` 下已有 4 个分类目录（architecture / archive / debugging_lessons / refactoring / task_tree），
  **没有**"开发规范"这一类
- 文档卫生检查 `tools/check_docs.py` 强制：新文档必须登记 INDEX、链接不得死链

## 🔬 实际结果

### 拆分结构

| 文件 | 职责 | 行数 |
|---|---|---|
| `AGENTS.md` | 项目一句话 / 必读顺序 / 铁律速查 / 工作流速查 / 设施表 / 提交前命令 / 版本 | 149 |
| `docs/dev/DISCIPLINE.md` | 产品不变量 I1~I5 + 5 条硬规则 + 归因顺序 + 例外 + 违规处置 + 每条规则的历史由来 | 175 |
| `docs/dev/CODING_STYLE.md` | 先探索后决策 / 单一实现 / 修根因 / 函数职责 / 结构化数据 / 注释 / 日志 / 与方豆协作 | 173 |
| `docs/dev/WORKFLOW.md` | 任务生命周期 / 迭代模板 / 文档卫生 / 测试与冒烟 / 机械保障 / ADR / 提交合并 | 187 |
| `docs/dev/REVIEW_CHECKLIST.md` | 机械检查命令 + 四组自检 + 反模式表 + 完成定义 | 100 |

### 真正新增的内容（重新确立，而非搬家）

| 新增 | 来自哪次教训 |
|---|---|
| **I1 不修改用户 RTL / 工程文件** | 本轮确立的产品约束（写能力只进 `tools/`，默认关闭） |
| **I2 core 只读 + JSON + 稳定 schema** | 既有的 CLI 分层决策，这次上升为不变量 |
| **I3 单一实现原则** | iter_240/241：`loads` 两份遍历分叉，API 静默返回空 |
| **I4 降级必须显式** | `exp/` 命名空间决策 |
| **I5 登记缺陷写可观察后果 + 按输入形态枚举** | iter_241：登记写"无跨模块支持"，实际影响面大得多 |
| **机械保障优先于文档声明** | `except: pass` 曾"声称清零"、实测 52 处 |
| **计数更新要核验 diff** | iter_240 提交信息声称更新了 INDEX 计数，实际没改，漂移 4 个迭代 |
| **真实项目冒烟** | 三次 fixture 全绿却漏掉真实 filelist 形态 bug |
| **禁止过期注释** | iter_241 清掉引用已删除类 `TraceResult` 的 docstring |
| **反模式 → 后果表** | 把反复犯的错做成对照表 |

### 交叉引用同步

拆完之后，其他文档里"见 AGENTS.md 某某条"会变成两跳。同步改成直连细则：

- `EXTRACTION_FAILURES.md` 4 处 → `dev/DISCIPLINE.md`
- `KNOWN_LIMITATIONS.md`（`-f` 纪律）→ `dev/DISCIPLINE.md §4`
- `ARCHITECTURE_TODOLIST.md`（50 行阈值）→ `dev/CODING_STYLE.md §5`
- `USER_GUIDE.md` 修正一处错记："`AGENTS.md` - 已知限制" → 协作入口
- `docs/INDEX.md` 文档卫生小节 → `dev/WORKFLOW.md §3`

**刻意保持不变**: 硬规则编号 1~5 原样保留 —— 全仓多处文档写"核心纪律 #2 / #4"，
编号不变则这些引用仍然成立，不需要全仓改写。

## 💡 关键发现 / 决策

1. **"入口 + 索引"的价值在于读者的注意力预算。** 522 行里 agent 真正每次都需要的是
   "现在该做什么 + 红线是什么"，其余是查得到的。把细则移出去后，入口 149 行，
   任何一次恢复上下文只需读这一屏 + CURRENT_TODO。

2. **拆分是重新审视纪律的机会。** 搬家过程中发现原文档有三处"只有声明没有后果"
   （"修 bug 要修根因"没给判据、"缺测试要主动说"没给优先级、"记录纪律"没给模板），
   这次都补成了可执行条款。

3. **产品不变量以前散落在各决策记录里。** I1（不改 RTL）、I2（core 契约）、I4（显式降级）
   分别写在 `EXP_NAMESPACE.md`、`CLI_SURFACE.md`、`ARCHITECTURE.md` 和历次对话里，
   **没人一进来就能看到全部红线**。这次集中成 5 条，并且每条只占一行 + 一个链接。

## 🔗 相关

- 任务: [L1_dev_discipline_v2.md](../tasks/L1_dev_discipline_v2.md)
- 入口: [AGENTS.md](../../../AGENTS.md)
- 索引: [docs/INDEX.md](../../INDEX.md)
