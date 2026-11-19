# AGENTS.md — sv_query L1 全局入口

> **产品方向**: [Agent RTL 查询 + 客观校验层](docs/architecture/product_direction_2026-10-31.md)。
> 本文件只做入口、路由和硬边界；细节用链接渐进披露，禁止把所有细节堆在这里。
> 修改前必须先读 [强制路由表](.claude/rules/modify-component-must-read.md)。

> **Agent 查询入口**: CLI + [`capabilities --json`](docs/agent/CAPABILITIES_GENERATED.md) 是唯一稳定入口；
> 查询协议见 [`.agents/skills/query-protocol/SKILL.md`](.agents/skills/query-protocol/SKILL.md)。
> 旧 [AGENT_FEATURE_MAP](docs/agent/AGENT_FEATURE_MAP.md) 是历史快照，不是命令真相源。

## 0. 架构鸟瞰

```text
RTL/filelist/snapshot
  -> pyslang v11 semantic AST          (src/sv_query/trace/core)
  -> SignalGraph / ModuleInstanceGraph (graph, verification, queries)
  -> CLI/JSON 或 Python Session        (src/cli, src/sv_query/session.py)
```

- 技术栈: Python 3.11+ / pyslang v11 / NetworkX / Typer / Rich。
- `src/sv_query/`: 查询引擎、图模型、编译、语义适配、cache/snapshot。
- `src/cli/`: agent 查询面、JSON envelopes、分层 registry、capabilities。
- `sim/tests/`: canonical 测试与真实 fixture；`docs/`: 契约、限制、计划证据。
- `tools/`: 门禁、扫描器、生成器；`agents/`: worker 协作记录，不是产品代码。

## 1. 真理源层级 (Source of Truth Hierarchy)

1. [产品方向](docs/architecture/product_direction_2026-10-31.md) — 做什么/不做什么。
2. [PLAN.md](PLAN.md) — 唯一计划源；`current item` 是当前工作。
3. [SEMANTIC_CONTRACTS](docs/dev/SEMANTIC_CONTRACTS.md) — 数据边/路径/verified 语义。
4. [CLAIMS](docs/dev/CLAIMS.md) — 对外声称与 gate 的对应关系。
5. [docs/INDEX.md](docs/INDEX.md) — 文档登记与 canonical 计数真相源。
6. [TESTING.md](TESTING.md) / [KNOWN_LIMITATIONS](docs/KNOWN_LIMITATIONS.md)。
7. [CURRENT_TODO.md](CURRENT_TODO.md) — 只记录此刻上下文，不另立计划。

冲突时按此顺序裁决；代码不是规范，**Existing files are not the reference**。

## 2. 强制路由 (修改前)

| 要改的东西 | 先读 |
|---|---|
| 任意 `src/` / `tools/` / `sim/tests/` | [modify-component-must-read](.claude/rules/modify-component-must-read.md) |
| Python 实现 | [general-code-style](.claude/rules/general-code-style.md) |
| 注释 / diff 清理 | [comment-style](.claude/rules/comment-style.md) |
| 测试 | [unit-test-admission](.claude/rules/unit-test-admission.md) |
| 新组件/新查询 | `.agents/skills/add-component/SKILL.md` |
| 查询错误/空结果 | `.agents/skills/debug-fault/SKILL.md` |
| 删代码/去重 | `.agents/skills/code-cleanup/SKILL.md` + `references/patterns.md` |

## 3. 铁律 (违反任意一条 = 停手并报告)

1. 禁 `--no-strict`；失败先诊断根因。
2. 禁 silent fallback；失败必须显式：异常/sentinel/结构化错误。
3. 禁 `except ...: pass`；禁止把失败伪装成正常。
4. filelist 一律 `--filelist`，禁止 `-f/--file` 传 filelist。
5. 失败归因顺序：fixture → 功能代码 → filelist → 环境 → 工具自身。
6. 不改用户 RTL/工程文件；写能力只进 `tools/` 且默认关闭。
7. `core` 只读 + JSON + 稳定 schema；agent 是消费者。
8. 同一语义只允许一份实现；发现两份就合并/删除。
9. 降级必须显式；实验能力进 `exp/`，不伪装稳定。
10. 缺陷登记必须写“什么输入 → 什么错误输出”。
11. 语义提取必须走 pyslang semantic AST；仅 UVM 宏允许源码 regex。
12. 项目适配不进 core 自动推断；放 `examples/project_adaptations/`。
13. 语义服从唯一契约；CLOCK/RESET 不是数据边；sample/truncated 不得写成 verified。

## 4. 任务流程

1. 在 `PLAN.md` 登记并置 `current item`；
2. 建 `docs/task_tree/tasks/` 任务文件；
3. 一次只做一个可观察迭代，写 `docs/task_tree/iterations/`；
4. 同步 `CURRENT_TODO` + `overview`；
5. 收尾更新 PLAN/INDEX/计数/CLAIMS（如有公开能力）。

大改动先说后做；重构必须拆成 **Prepare → Move → Postpare**，机械搬移与语义修改不得混在同一 diff。
两个补丁都失败时先 attack the premise，不要叠第三个补丁。

## 5. 核心命令

```bash
# 日常
python3 -m pytest sim/tests/ -m "not opensource" -q -p no:randomly
python3 run_cli.py capabilities --json
python3 run_cli.py stats --filelist <filelist> --json

# 提交前
bash tools/run_gates.sh
python3 tools/check_plan.py
python3 tools/check_docs.py --strict
git status --porcelain

# 真实多文件冒烟
python3 run_cli.py stats --filelist sim/tests/fixtures/scheduler_minimal/filelist.f --json
```

## 6. 汇报与停止

- 汇报格式：**现状 → 问题 → 建议 → 代价**；不谎报完成。
- 完成 = 代码 + 测试 + 文档 + 语义契约影响 + 反事实/独立 oracle。
- 公开 claim 必须有 `CLAIMS.md` 一行；没有 gate 标 `unverified`。
- 发现设计冲突/用户指令与代码事实冲突，先停下确认。

## 7. 渐进式治理层

| 层 | 位置 | 作用 |
|---|---|---|
| L1 | 本文件 | 入口、真理源、强制路由 |
| L2 | `.claude/rules/` | 被动红线，`paths:` 自动挂载 |
| L3 | `.agents/skills/`（`.claude/skills` 软链） | 7 段式任务技能 |
| L4 | `.agents/skills/*/references/` | 判例库按需展开 |

旧版流程细节仍以 [DISCIPLINE](docs/dev/DISCIPLINE.md)、[WORKFLOW](docs/dev/WORKFLOW.md)、[REVIEW_CHECKLIST](docs/dev/REVIEW_CHECKLIST.md) 为准。
