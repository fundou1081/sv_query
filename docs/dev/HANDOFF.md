# 交接文档 (HANDOFF)

**交接时间**: 2026-11-11 20:30 (Asia/Shanghai)（2026-11-11 21:10 校对状态类文档）
**仓库**: `/Users/fundou/my_dv_proj/sv_query`
**HEAD**: 以 `git log -1` 为准（本文最后核对：`56c10fa9`）
**状态**: canonical 与 opensource 均为 0 failed；P158 还剩部分收尾

> 给接手 agent：先读完本文件，再按 [AGENTS.md](../../AGENTS.md) §0 的顺序恢复上下文。
> 本文件是交接状态，不是计划树唯一真相源；PLAN.md 仍是唯一计划源。

---

## 1. 一句话状态

```text
sv_query 是 agent 的 RTL 查询 + 客观校验层；
核心语义契约、数据边、确定性、snapshot MIG、真实 corpus 已经落地；
当前不是“完成品”，剩余工作集中在：
P158.9 snapshot surface 矩阵、P158.12 P2 清理（11.2b 长查询 timeout 已完成）。
```

当前测试：

```text
canonical:   2678 passed / 0 skipped / 131 deselected / 0 failed
opensource:  114 passed / 17 skipped / 0 failed
```

opensource 的 17 个 skip 都有显式原因，见 §7。

---

## 2. 必须先读

按顺序：

1. [AGENTS.md](../../AGENTS.md) — 铁律、完成判定、开工/收尾
2. [产品方向](../architecture/product_direction_2026-10-31.md) — 做什么/不做什么
3. [PLAN.md](../../PLAN.md) — 唯一计划树 + `current item`
4. [CURRENT_TODO.md](../../CURRENT_TODO.md)
5. [DISCIPLINE.md](DISCIPLINE.md)
6. [SEMANTIC_CONTRACTS.md](SEMANTIC_CONTRACTS.md) — **本项目的核心**
7. [CLAIMS.md](CLAIMS.md) — 公开 claim 的状态
8. [TESTING.md](../../TESTING.md)
9. [P160 triage](../validation/P160_OPENSOURCE_TRIAGE_2026-11-11.md) 与
   [P161 remediation](../validation/P161_OPENSOURCE_REMEDIATION_2026-11-11.md)
10. [本轮对话/工作记录](../sessions/2026-11-11_sv_query_session_log.md)（事实重建，非逐字）

如果只读一份历史复盘：

- [2026-11-11_pitfalls.md](../lessons/2026-11-11_pitfalls.md)
  — 22 个坑、10 条正面经验、20 条反模式、10 个重来决策

---

## 3. 已完成（不要重复做）

| 任务 | 结果 |
|---|---|
| P158.1 | 数据边唯一策略：`DRIVER/CONNECTION`；CLOCK/RESET/BIT_SELECT 不是数据路径 |
| P158.2 | paths work budget + deadline + 显式 `truncated` |
| P158.3 | 构建确定性；根因是 `id(pyslang wrapper)` 被 GC 地址复用；已用强引用保活 |
| P158.4 | SPI corpus runner；9 tasks |
| P158.5 | `filelist prune` 默认 dry-run、`--apply`、`.f/.fl`、`--force` + `.bak` |
| P158.6 | `verify consistency` 的 `verified` 纳入 `coverage_complete`；sample/truncated 不再 verified |
| P158.7 | snapshot 统一 `load_snapshot()`；损坏 snapshot 显式错误；MIG `module_ports` 持久化 |
| P158.8 | bit/reciprocity true-positive + legacy snapshot 回归 |
| P158.9.1 | capabilities `core_groups` 修正；核心命令 json_contract 覆盖 |
| P158.10 | `tools/run_gates.sh`；CI 与本地同一条 gate；增量 ruff |
| P158.11.1 | `dataflow analyze --from-snapshot`；frontier `--max-visits` |
| P158.11.2a | snapshot size guard `SVQ_SNAPSHOT_MAX_MB` + size metadata |
| P159 | 全量踩坑历史 |
| P160/P161 | opensource 38 failed -> 0 failed；17 显式 skip |

关键提交：

```text
20ed39d6 — fix(P158.11.2a): snapshot size guard and metadata
38a68621 — fix(P161): remediate opensource test failures
b6899917 — test(P160): triage opensource failures
2106bac2 — feat(P158.11.1): dataflow from snapshot and frontier visit cap
d1325aaf — docs(P159): record full pitfalls and lessons history
```

---

## 4. 当前架构/所有权边界

| 文件/模块 | 责任 | 注意 |
|---|---|---|
| `src/trace/core/graph/contracts.py` | **唯一** edge 分类 | 不允许在命令里另写 edge 集合 |
| `src/trace/core/module_instance_graph.py` | PathResolver / MIG | 路径有界；不要恢复全 edge 遍历 |
| `src/trace/core/graph/dataflow.py` | dataflow 段/路径 | 必须只走数据边；BIT_SELECT 只做端点位展开 |
| `src/trace/core/snapshot_manager.py` | snapshot CRUD/大小/损坏 | 文件名是 tag 权威；损坏文件可见 |
| `src/trace/unified_tracer.py` | `load_snapshot` 唯一构造入口 | 不要再手工设 4 个私有字段 |
| `src/cli/_registry.py` | capabilities/registry/contract | 40 core 命令的 group/contract |
| `tools/agent/run_spi_corpus.py` | 真实 corpus runner | 9 tasks；不要改成“只打印” |
| `tools/run_gates.sh` / `tools/run_lint.sh` | CI/本地 gate | 不要绕过 |
| `.github/workflows/tests.yml` | CI | opensource 可见但不阻塞 |

**不要修改** `src/trace/core` 去做 OpenTitan 特定 FIFO/接口推断；
项目适配只能在 `examples/project_adaptations/` 或外部显式调用。

---

## 5. 剩余工作

### 5.1 P158.11.2b：通用长查询 timeout（✅ 已完成，2026-11-11）

落地（commit 见 git log `feat(P158.11.2b)`）：

- `src/trace/core/graph/search_budget.py::SearchBudget`：预算记账唯一实现
  （从 MIG 的 `_SearchBudget` 抽出共享，旧名保留别名）；
- `dataflow._find_paths` 全部 `list(nx.all_simple_paths(...))` 替换为同遍历序的有界 DFS
  `_bounded_simple_paths`（每考察一条出边记 1 次 expansion）；
- `DataFlowResult` 新增 `truncated / truncation_reason / expansions / search_status`；
  耗尽时 `is_reachable=None`（unknown），不再伪装 `found:false`；
- CLI `dataflow analyze` 新增 `--max-expansions`（默认 200000）/ `--timeout`（秒），
  JSON 输出同步截断字段；json_contract / capabilities result_fields 已同步；
- 机械 gate：`sim/tests/unit/test_p158_11_dataflow_budget.py`（diamond fixture，
  max_paths 截断 / expansions 耗尽 / timeout=0 → unknown）。

边界：`verify` / `subgraph` 等其余命令若将来出现无界枚举，同样走 `SearchBudget`。

### 5.2 P158.9.2：snapshot surface 矩阵（9.1 已完成）

问题：`--from-snapshot` 半状态（有的命令支持，有的不支持）。

需要：

- 一张唯一矩阵：命令 → graph-only / graph+MIG / 需要 semantic adapter；
- `capabilities` / `--help` / `json_contract` 同源；
- 不支持的命令显式失败/unknown，不静默 fallback。

### 5.3 P158.12：P2 清理

建议按这个顺序：

1. **26 个测试文件**硬编码 `/Users/fundou/...` → 仓库相对路径
   （2026-11-11 实测 `grep -rl "/Users/fundou" sim/tests --include=*.py | wc -l` = 26；
   旧文档写 20/23 都不准）；
2. `-p no:randomly` no-op：移除 flag 或真正安装插件（实测 `pytest_randomly` 未安装）；
3. `trace impact` heuristic 在 core：移 `exp` 或把 `kind` 改成 heuristic 并补 claim；
4. 408 条空 expression 的 self-loop：**先补复现命令/基线文件**再调查（当前文档没有入口，接手无法验证）；
5. `false_confident` 指标在 task exception 时漏计；
6. 文档/help/skills 漂移。

### 5.4 17 个 opensource skip 分类

不要直接删除；逐项判断：

```text
benchmark timeout (3)      -> 能否加预算/标记 slow
long-range pilot (2)       -> 环境永久缺失还是应提供 fixture
TLUL (2)                   -> 依赖闭包缺失
CVA6/prim_fifo (2)         -> 依赖闭包缺失
naplespu retired exp (8)   -> 已退休；可归档，不恢复旧命令
```

---

## 6. 工作流（接手 agent 必读）

### 6.1 恢复上下文

```bash
cd /Users/fundou/my_dv_proj/sv_query
git status --porcelain
git log --oneline -5
sed -n '20,24p' PLAN.md
grep -n "^current item" PLAN.md        # 比行号稳定，推荐
python3 tools/check_plan.py
```

先核对 `PLAN.md` 的 `current item` 是否与代码/测试一致；
不一致先修正计划树，不要凭印象继续。

### 6.2 开工

- 先在 `PLAN.md` 登记（新工作挂到对应 `P*`；不要另立计划列表）；
- 建 `docs/task_tree/tasks/L<N>_<任务>.md`；
- 更新 `CURRENT_TODO.md` / `overview.md`；
- 写清验收命令和反例。

### 6.3 提交前

```bash
bash tools/run_gates.sh
```

它会跑：

```text
canonical pytest
check_docs
check_except_pass
check_semantic_regex
check_cli_layers
gen_cli_surface --check
check_crap
check_plan
```

opensource 是独立套件：

```bash
python3 -m pytest sim/tests/ -m "opensource" -q -p no:randomly
```

当前期望：

```text
canonical:   2678 passed / 0 failed
opensource:  114 passed / 0 failed / 17 explicit skips
```

**解释器必须先对齐**（2026-11-11 实测坑）：`run_gates.sh` 与测试内部都调用 `python3`。
若 PATH 里的 `python3` 不是装了 typer/pyslang 的那个（本机默认可能是 3.13.x），
CLI 子进程测试会成片报 `ModuleNotFoundError: No module named 'typer'`——这是环境假失败，
不是产品回归。本机正确用法：

```bash
export PATH="$HOME/miniconda3/bin:$PATH"   # 3.11.4 + pyslang 11.0.0
bash tools/run_gates.sh
```

计数若变化，只更新 `docs/INDEX.md` 的“当前基线”；不要在其他地方写死。

---

## 7. 17 个 opensource skip 的现状

```text
3 × test_benchmark_pr5        wrapper benchmark 300s timeout
2 × test_run_long_range_runner pilot axi/serv 无 .v
2 × dataflow_controlflow      TLUL fixture/dependency incomplete
2 × dataflow_latency         CVA6 / prim_fifo dependency incomplete
8 × test_naplespu_filelist    retired exp commands, explicit skip
```

规则：

- 环境缺失是显式环境 skip，不是产品通过；
- retired exp 测试不能靠“移出统计”变绿；当前是显式 skip，理由可审计；
- 不要把新的 fail 改成 skip 来变绿。

---

## 8. 外部环境 / 复现

### SPI snapshot

```bash
export SVQ_SNAPSHOT_DIR=/tmp/opentitan_svq_spi/snapshots
# snapshot tag: opentitan_spi
# filelist: /tmp/opentitan_svq_spi/opentitan_spi.clean.f
```

重建：

```bash
cd /Users/fundou/.dsh/opencode-workers-lite/opentitan-pilot/workspace
SVQ_SNAPSHOT_DIR=/tmp/opentitan_svq_spi/snapshots \
python3 /Users/fundou/my_dv_proj/sv_query/tools/agent/setup_snapshot.py \
  --path . --tag opentitan_spi \
  --filelist /tmp/opentitan_svq_spi/opentitan_spi.clean.f \
  --snapshot-dir /tmp/opentitan_svq_spi/snapshots \
  --source-root . --json
```

### SPI corpus

```bash
cd /Users/fundou/my_dv_proj/sv_query
SVQ_SNAPSHOT_DIR=/tmp/opentitan_svq_spi/snapshots \
python3 tools/agent/run_spi_corpus.py --json
# expect 9/9
```

### 机器依赖

- Python 3.11 / 3.12；**本机实测可用解释器**：`~/miniconda3/bin/python3`（3.11.4）
- pyslang（GitHub source）；本机 `pyslang 11.0.0`
- `crapper`（复杂度门禁；没有会 exit 3，不是 pass）
- macOS（部分外部路径是机器绑定的）
- 注意：本机 PATH 默认 `python3` 可能是 3.13.x（无 typer/pyslang），见 §6.3 解释器说明

---

## 9. Worker / 并行 agent 协议

如果要开 worker：

1. worker 必须从当前 HEAD 建独立 worktree；
2. 任务 prompt 必须包含：
   - 读 `SEMANTIC_CONTRACTS` / `DISCIPLINE §0.1` / `CLAIMS`
   - 不允许改 PLAN/docs/CLAIMS（除非主会话明确）
   - 必须提交 commit hash
   - 必须给复现命令 + 反例
3. worker 的 `APPROVE` 不是证据；主会话至少复现 P0；
4. worker 配额 429 / 中断时，主会话从 worktree 取 diff，重新验证后合并；
5. 不要让两个 worker 同时改同一文件（尤其 `dataflow.py` / `module_instance_graph.py`）。

本仓库真实教训：P160 worker 遇到 429，主会话接管；P158.3 worker 的源码位置 key 方案导致 18 个 generate 测试失败，被回退后采用强引用方案。

---

## 10. 完成 / 交回 checklist

交回前：

- [ ] `bash tools/run_gates.sh` 0 退出码
- [ ] canonical 0 failed；opensource 0 failed 或每个 skip 有 reason
- [ ] 新增/变更行为有 true-positive 测试和反例
- [ ] 没有自动 bless golden / 没有 fail->skip
- [ ] `PLAN.md` / `CURRENT_TODO` / `overview` / `docs/INDEX` 同步
- [ ] `CLAIMS.md` 中相关 claim 状态更新
- [ ] 列出未修问题、环境限制、外部 fixture 依赖
- [ ] 最终报告写清：改了什么、证据、风险、下一步

---

## 11. 不要做

- 不要为了绿灯删除/跳过测试；
- 不要用一次 fresh parse 证明 determinism；
- 不要在命令里另写一份 edge 策略；
- 不要把 CLOCK/RESET 当数据路径；
- 不要在 sample/truncated 上返回 `verified:true`；
- 不要在 core 里做 OpenTitan 特定推断；
- 不要静默覆盖用户文件；
- 不要把 worker APPROVE 当真实项目通过；
- “所有查询都有界”仍需谨慎表述：paths/frontier/dataflow 有 gate；
  新增长查询必须复用 `SearchBudget`（见 SEMANTIC_CONTRACTS §3）。

---

## 12. 建议接手顺序

```text
0. 文档状态校准（P164，2026-11-11 已完成：PLAN/CURRENT_TODO/契约/基线/HANDOFF 对齐）
1. P158.11.2b generic timeout（2026-11-11 已完成）
2. P158.9 snapshot surface 矩阵（9.2）
3. P158.12 P2 清理
4. 17 个 skip 分类
```

如果只接一个任务，选 **P158.9.2 snapshot surface 矩阵**：
`--from-snapshot` 覆盖不一致是当前最影响 agent 可用性的缺口。
