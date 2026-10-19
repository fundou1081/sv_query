# 开发流程 (Workflow)

> **本文是 `AGENTS.md` 的细则文件之一。** 入口/索引见 [AGENTS.md](../../AGENTS.md)。
> 硬性禁止项在 [DISCIPLINE.md](DISCIPLINE.md)；编码规范在 [CODING_STYLE.md](CODING_STYLE.md)。
> **最后修订**: 2026-10-19

---

## 0. 当前仓库约定

| 项 | 约定 |
|---|---|
| 开发分支 | **`main`**（2026-10-19 起；长期分支 `chore/*` 已合并删除） |
| 远端 | `backup`（HTTPS，主用）与 `ssh-origin`（SSH）指向同一 GitHub 仓库 |
| 提交 | `git commit -F <message-file>`（**不用**内联 `-m`，正文要写清根因/取舍/影响） |
| 代码 + 文档 | **同一个 commit**，不分开提交 |
| 合并 | 只在全量门禁 + 机械检查全绿后合并；能 fast-forward 就 fast-forward |

### 0.1 设施与唯一位置 (不得新建平行体系)

| # | 设施 | 唯一位置 | 作用 |
|---|---|---|---|
| 1 | **协作入口** | [AGENTS.md](../../AGENTS.md) | 流程与铁律，压缩后必重读 |
| 2 | **细则** | `docs/dev/` | 纪律 / 风格 / 流程 / 清单 |
| 3 | **当前 todolist** | [CURRENT_TODO.md](../../CURRENT_TODO.md) | **此刻**在做什么 — 唯一稳定追踪点 |
| 4 | **迭代记录** | [docs/task_tree/](../task_tree/) | 任务树 + 每次迭代一个文件 |
| 5 | **架构决策** | [docs/architecture/](../architecture/) + [ARCHITECTURE.md](../ARCHITECTURE.md) | 架构变更 / 决策记录 |
| 6 | **测试** | [TESTING.md](../../TESTING.md) + `sim/tests/` | 唯一测试手段与流程 |
| 7 | **文档索引** | [docs/INDEX.md](../INDEX.md) | 唯一文档入口 + 计数单一真相源 |

**辅助 (不是入口)**: [ARCHITECTURE_TODOLIST.md](../ARCHITECTURE_TODOLIST.md)（架构改造长期追踪）、
[TODO.md](../TODO.md)（版本级待办）、`memory/`（按日经验）、
[debugging_lessons/](../debugging_lessons/)（单次 debug 复盘）。

**禁止**新建 `records/` `logs/` `notes/` 等与上表重复的目录 —— 要加内容就加进已有位置。

---

## 1. 任务生命周期 (强制顺序)

### 1.1 开工前 (缺一步就不要动手)

1. **建任务文件**: `docs/task_tree/tasks/L<N>_<任务名>.md`
   - `L1` = 顶层任务, `L2` = 子任务, `L3` = 具体动作
   - 写清：背景、现状实测、目标、验收方式
2. **更新 `CURRENT_TODO.md`**: 设为"当前任务"，列出 sub-task，标 🟡 in_progress
3. **更新 `docs/task_tree/overview.md`**: 把任务挂到任务树
4. **写计划**: 明确 1~N 个 sub-task，每个都有**可验证输出**（命令 / 断言 / 数字）

### 1.2 迭代中

- **一个迭代 = 一个可观察的动作**（读代码 / 跑测试 / 修 bug / 验证结果）
- 每个迭代写一个 `docs/task_tree/iterations/iter_NNN_<简述>.md`，**边做边写**
- 每完成一个 sub-task 就勾选 `CURRENT_TODO.md`；遇阻塞立刻写明阻塞点
- 迭代号**只增不减**，不复用、不回填（当前最新 `iter_259`，下一个 `iter_260` 起顺延）

### 1.3 收尾

| 必须更新 | 内容 |
|---|---|
| `CURRENT_TODO.md` | 移到"最近完成"，清出当前任务位 |
| `docs/task_tree/overview.md` | 任务树状态 + 迭代汇总表新增一行 |
| 长期 todolist | `docs/ARCHITECTURE_TODOLIST.md` 或 `docs/TODO.md` 改状态 + 记录变更 |
| `TESTING.md` | 若新增/变更了测试流程或落盘位置 |
| `docs/architecture/` | 若涉及架构决策 |
| `docs/INDEX.md` | 若新增/改名/移动文档；若基线计数变化，更新"当前基线" |

**完成判定**: **代码 ✅ + 测试 ✅ + 文档 ✅** 三者齐备才算完成。
只完成代码就说"做完了" = 谎报进度。

---

## 2. 迭代记录规范

**必须**写在 `docs/task_tree/iterations/`，模板：

```markdown
# Iteration NNN: <标题>

**Metadata**:
- **Iteration #**: NNN
- **Task Tree Level**: L1 / L2 / L3
- **Parent Task**: <对应 tasks/ 下的文件名>
- **Created**: YYYY-MM-DD HH:MM GMT+8
- **Author**: 方豆 / <AI 助手名>
- **Outcome**: ✅ 成功 / ❌ 失败 / 🚧 未收敛 / ⚠️ 部分完成

## 🎯 本次目标            <附方豆原话指令>
## 📊 当前状态 / 预期结果   <开工时的实测状态>
## 🔬 实际结果            <真实发生了什么, 失败也如实写>
## 💡 关键发现 / 决策      <根因、踩的坑、为什么这么选>
```

### 记录纪律 (硬要求)

- **如实记录** —— 失败的尝试**必须写**，写清为什么失败
- **禁止事后美化** —— 不要把"试了 3 次才对"写成"一次就对"
- **禁止只写结论不写过程** —— 关键发现的推导路径比结论更值钱
- **必须记**: 关键发现 / 关键技术 / 决策及其理由
- 涉及自伤、回归、误判的，单独一段写清"我以为 → 实际是"

---

## 3. 文档卫生 (强制)

> 文档是项目**第二产品**。曾膨胀到 370 份、计数在十几处互相矛盾，才立的这条规矩。

1. **唯一文档入口 = `docs/INDEX.md`** —— 新增/改名/移动任何文档后必须登记；未登记 = 检查失败。
   根目录入口文档 (README / AGENTS / CURRENT_TODO / TESTING) 在 INDEX 登记即可，不重复建索引。
2. **过期报告 / 被取代的稿子 → 归档不删除** —— 移到 `docs/archive/<日期>-cleanup/`，
   并在该目录 `README.md` 写清归档原因。
3. **计数只有一个真相源** —— 全量测试/规模计数只写在 `docs/INDEX.md` 的"当前基线"一节，
   其他文档**引用**它，禁止写死 `N passed`。分套件计数可写，但必须是当期实测。
4. **历史快照豁免** —— `docs/task_tree/iterations/`、`CHANGELOG.md`、`memory/`、
   重构轮快照可保留当时计数（它们是时间点记录）。
5. **提交前必跑** `python3 tools/check_docs.py` —— 死链 / 归档越界 / 未登记 三项必须 0，
   计数漂移为警告（需人工确认）。
6. **提交前必跑** `python3 tools/check_except_pass.py` —— 见 [DISCIPLINE.md](DISCIPLINE.md) §3。

**教训 (iter_241)**: `docs/INDEX.md` 的 canonical 计数行连续 **4 个迭代没同步**，
原因正是"提交信息声称更新了、实际只改了另一行"。
**结论**: 计数类更新要**单独核验一遍 diff**，不能凭印象写进提交信息。

---

## 4. 测试流程

**唯一测试入口**: [TESTING.md](../../TESTING.md) —— 命令、marker、落盘隔离规则都在那里，不要散落。

三条必须遵守的补充：

1. **提交前跑全量门禁**，不要只跑改动相关的测试：
   ```bash
   python3 -m pytest sim/tests/ -m "not opensource" -q -p no:randomly
   ```
2. **涉及查询/图/CLI 的改动，额外跑真实多文件项目冒烟**（fixture 单文件会掩盖问题）：
   ```bash
   python3 run_cli.py <命令> --filelist sim/tests/fixtures/scheduler_minimal/filelist.f --json
   ```
   本项目已**三次**因只跑 fixture 而漏掉真实形态的 bug（hierarchy 树失真 / tools 路径守卫 /
   `-f` 与 `--filelist` 的差异）。
3. **写文件的测试必须隔离**：`SVQ_SNAPSHOT_DIR` / `SVQ_CACHE_DIR` 指向 `tmp_path`
   （subprocess 需传 `env=`），否则会污染真实目录。

---

## 5. 机械保障 (Mechanical Guards)

原则：**能用脚本判定的规则，就不要只写在文档里。**
本项目已有 4 个检查器，提交前全跑：

| 检查 | 作用 | 失败含义 |
|---|---|---|
| `tools/check_docs.py` | 死链 / 归档越界 / 未登记 | 文档卫生被破坏 |
| `tools/check_except_pass.py` | `except ...: pass` 计数 | 有静默吞异常 |
| `tools/check_cli_layers.py` | CLI 分层规则 R1~R8 | 层归属/反向依赖/隐式写文件等违规 |
| `tools/gen_cli_surface.py --check` | `docs/CLI_SURFACE.md` 与代码一致性 | 清单过期 |

**再加一条**: 真实项目冒烟脚本 / 目录树指纹这类"行为证明"，
优先写成测试而不是一次性脚本（例：只读性用目录 sha256 指纹证明）。

**新增规则的流程**: 先写进 [DISCIPLINE.md](DISCIPLINE.md) 或 [CODING_STYLE.md](CODING_STYLE.md)，
**同一次改动**里补检查器 + "检查器能检出违规"的自检测试。

---

## 6. 架构决策记录 (ADR)

架构发生变更时，在 `docs/architecture/` 单独写一份，必备字段：

| 字段 | 内容 |
|---|---|
| **时间** | YYYY-MM-DD HH:MM GMT+8 |
| **遇到的问题** | 什么触发了这次架构讨论（附实测证据） |
| **考虑的方案** | 至少 2 个，各自利弊 |
| **决策结果** | 选了哪个 |
| **利弊权衡** | 为什么接受它的缺点，放弃了什么 |

参考: `docs/architecture/case27_signal_graph_completeness_decision.md`。

---

## 7. 提交与合并

### 7.1 提交前

跑 [REVIEW_CHECKLIST.md](REVIEW_CHECKLIST.md) 的机械检查 + 自我审视清单。

### 7.2 提交信息

必须包含：

1. **方豆的原话指令**（一行，引用）
2. **根因**（不是"改了什么"，而是"为什么会错"）
3. **改法 + 被否决的方案**（为什么不是另一个）
4. **影响面与验证**（测试数字、机械检查结果、真实项目冒烟结论）
5. **登记的遗留项**（没修的东西写清在哪登记）

### 7.3 合并到 main

- 全量门禁 + 4 个检查器全绿
- 工作区干净（`git status` 0 改动）
- 优先 `git merge --ff-only`
- 合并后校验：`git rev-parse main backup/main` 一致
- 合并**之前**确认没有把该留的东西留在分支上（文档、测试、脚本）
