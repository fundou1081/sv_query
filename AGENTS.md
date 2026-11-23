# AGENTS.md — sv_query contributor / agent entry

> **开发位置**: 本仓库 `fundou1081/sv_query`（public）是**唯一开发主线**。
> 私有仓库 `fundou1081/sv_query_private` 只保存旧历史/开发资产，是**冻结归档，只读**；
> 不要在那里继续开发产品代码。详见 [REPOSITORY_LAYOUT](docs/dev/REPOSITORY_LAYOUT.md)。

> **产品方向**: [Agent RTL 查询 + 客观校验层](docs/architecture/product_direction_2026-10-31.md)。
> 本文件只做入口、路由和硬边界；细节用链接渐进披露。

> **Agent 查询入口**: CLI + [`capabilities --json`](docs/agent/CAPABILITIES_GENERATED.md)；
> 查询协议见 [`.agents/skills/query-protocol/SKILL.md`](.agents/skills/query-protocol/SKILL.md)。

## 0. 架构鸟瞰

```text
RTL/filelist/snapshot
  -> pyslang v11 semantic AST          (src/sv_query/trace/core)
  -> SignalGraph / ModuleInstanceGraph (graph, verification, queries)
  -> CLI/JSON or Python Session        (src/sv_query/cli, src/sv_query/session.py)
```

- Python 3.11+ / pyslang v11 / NetworkX / Typer / Rich。
- `src/sv_query/`: 查询引擎、图模型、编译、语义适配、cache/snapshot。
- `src/sv_query/cli/`: agent 查询面、JSON envelopes、分层 registry、capabilities。
- `sim/tests/`: canonical 测试与 fixture；`docs/`: 契约、限制、验证报告。
- `tools/`: 门禁、扫描器、生成器。

## 1. 真理源层级

1. [产品方向](docs/architecture/product_direction_2026-10-31.md)
2. [PLAN.md](PLAN.md) — 唯一计划源
3. [SEMANTIC_CONTRACTS](docs/dev/SEMANTIC_CONTRACTS.md)
4. [CLAIMS](docs/dev/CLAIMS.md)
5. [docs/INDEX.md](docs/INDEX.md)
6. [TESTING.md](TESTING.md) / [KNOWN_LIMITATIONS](docs/KNOWN_LIMITATIONS.md)
7. [CURRENT_TODO.md](CURRENT_TODO.md)

## 2. 修改前阅读

| 要改的东西 | 先读 |
|---|---|
| Python 实现 | [CODING_STYLE](docs/dev/CODING_STYLE.md) |
| 语义/路径/证据 | [SEMANTIC_CONTRACTS](docs/dev/SEMANTIC_CONTRACTS.md) |
| 测试 | [TESTING.md](TESTING.md) |
| 命令面 | [COMMAND_SURFACE_RATCHET](docs/dev/COMMAND_SURFACE_RATCHET.md) |
| bit-select hints | [BIT_SELECT_HINTS](docs/dev/BIT_SELECT_HINTS.md) |
| 用户查询 | [USER_GUIDE](docs/USER_GUIDE.md) / [query-protocol](.agents/skills/query-protocol/SKILL.md) |

## 3. 铁律

1. 禁 `--no-strict`；失败先诊断根因。
2. 禁 silent fallback；失败必须显式：异常/sentinel/结构化错误。
3. 禁 `except ...: pass`。
4. filelist 一律 `--filelist`，禁止 `-f/--file` 传 filelist。
5. 失败归因顺序：fixture → 功能代码 → filelist → 环境 → 工具自身。
6. 不改用户 RTL/工程文件；写能力只进 `tools/` 且默认关闭。
7. `core` 只读 + JSON + 稳定 schema。
8. 同一语义只允许一份实现。
9. 降级必须显式；实验能力进 `exp/`。
10. 缺陷登记写“什么输入 → 什么错误输出”。
11. 语义提取走 pyslang semantic AST；仅 UVM 宏允许源码 regex。
12. 项目适配放 `examples/project_adaptations/`。
13. CLOCK/RESET 不是数据边；sample/truncated 不得写成 verified。

## 4. 工作流程

1. 更新 `PLAN.md`；
2. 做窄的可观察改动；
3. 补测试与文档；
4. 跑：
   ```bash
   bash tools/run_gates.sh
   python3 tools/check_plan.py
   python3 tools/check_docs.py --strict
   ```
5. P0/P1 或语义/缓存/session/verification 改动，必须由**独立 worker 只读审查**
   （[CODE_REVIEW_PROTOCOL](docs/dev/CODE_REVIEW_PROTOCOL.md)）。审查发现 P0/P1
   必须重改并复审；未关闭不得提交发布。

## 5. 核心命令

```bash
python3 -m pytest sim/tests/ -m "not opensource" -q -p no:randomly
python3 run_cli.py capabilities --json
python3 run_cli.py stats --filelist <filelist> --json
```

## 6. 汇报

**现状 → 问题 → 建议 → 代价**；不谎报完成。公开 claim 必须有 `CLAIMS.md` 一行。
