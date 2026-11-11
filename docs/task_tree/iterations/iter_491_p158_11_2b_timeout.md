# iter_491 — P158.11.2b 通用长查询 timeout（dataflow 有界化）

**日期**: 2026-11-11
**任务**: [L3_p158_long_query_timeout](../tasks/L3_p158_long_query_timeout.md)
**触发**: 方豆「先解决 p158.11.2b 之后我们再来讨论 review 的内容」（P164 提交后开工）

---

## 1. 动作

核心 `src/**` 改动 4 个文件 + 新增 1 个模块；测试新增 1 个文件 + 1 个 fixture。

| # | 文件 | 改动 |
|---|---|---|
| 1 | `src/trace/core/graph/search_budget.py` (新) | `SearchBudget` 从 MIG 的 `_SearchBudget` 抽出，成为预算记账**唯一实现**；MIG 保留 `_SearchBudget = SearchBudget` 别名 |
| 2 | `src/trace/core/graph/dataflow.py` | ① `DataFlowResult` 新增 `truncated/truncation_reason/expansions/search_status`；② `_find_paths` 内 4 处 `list(nx.all_simple_paths(...))` 全部替换为 `_bounded_simple_paths`（栈式 DFS，遍历序与 networkx 一致）；③ `analyze(max_paths, max_expansions, timeout_s)`：预算耗尽 → `is_reachable=None` + `truncated:true`；`max_paths` 收满 → `truncation_reason:"max_paths_reached"`（不再静默 slice） |
| 3 | `src/cli/core/semantic/dataflow.py` | `dataflow analyze` 新增 `--max-expansions`（默认 200000）/ `--timeout`（秒）；JSON 输出带截断字段；耗尽时 `ok:false + machine.unknown_kind:"search_budget_exhausted"` |
| 4 | `src/cli/_registry.py` + `docs/architecture/json_contract_2026-10-31.md` | dataflow result_fields / 契约文档同步新字段 |
| 5 | `sim/tests/fixtures/dataflow_budget/diamond.sv` (新) | 8 级菱形：s0→y 共 256 条简单数据路径，可稳定触发各截断分支 |
| 6 | `sim/tests/unit/test_p158_11_dataflow_budget.py` (新) | true-positive：max_paths 截断可见 / expansions 耗尽 → unknown / timeout=0 → deadline；反例：耗绝不返回 `found:false` |

复杂度：`_bounded_simple_paths` 初版 CC=12 超 check_crap 阈值 10，拆出
`_next_unvisited_edge` / `_expandable` 后通过（每考察一条边记 1 次 expansion，
计量口径比初版更诚实）。

## 2. 设计要点

- **不写第二份 budget 逻辑**：`SearchBudget` 同时被 MIG `PathResolver` 与
  `DataFlowGraph` 引用；`verify` 等将来复用同一实现。
- **为什么不用 `nx.all_simple_paths`**：它先遍历整棵搜索树才产出，
  `list(...)` 更是先物化全部路径，预算内无法中止。
- **遍历序保持不变**：与 networkx `_all_simple_edge_paths` 同构（栈 + 当前路径
  字典按插入序扩展），golden 测试顺序不受影响（实测 256 条路径顺序逐一相等）。

## 3. 证据（命令与结果）

```text
pytest sim/tests/unit/test_p158_11_dataflow_budget.py
  + test_p158_data_edge_contract.py
  + integration/test_dataflow_golden.py
  + regression/test_dataflow_endpoint.py
  + unit/test_dataflow_error_hint.py
  → 59 passed / 0 failed（PATH=~/miniconda3/bin, --basetemp=/tmp/p158x）

cli/test_json_contract.py + unit/test_trace_schemas.py → 52 passed

unit 全量（`-m "not opensource"` 子集内, `--basetemp=/tmp/p158run`）→
  **860 passed / 2 skipped（显式原因: pilot .v 不可用）/ 0 failed**（11min 独立复核）

门禁: check_docs(--strict)/except_pass/semantic_regex/cli_layers/
      gen_cli_surface --check/check_plan(577 项)/check_crap 全部 exit 0

手工复现（diamond fixture）:
  max_paths=10    → is_reachable:true, paths_count:10, truncated:true,
                    truncation_reason:"max_paths_reached"
  max_expansions=5 → is_reachable:null, truncated:true,
                    truncation_reason:"max_expansions_reached" (unknown)
  timeout_s=0.0   → truncation_reason:"deadline_reached" (unknown)
  无预算           → 256 条路径全量枚举 complete（与 nx 同序）
```

## 4. 边界与诚实声明

- **canonical 全量（unit+cli+integration+regression）未在本机独立复核**
  （历史原因：全量 28min+ 且沙箱下 basetemp 冲突）；本轮已复核
  unit 全量（860 passed）+ dataflow/golden/endpoint/契约/schema 相关子集（59+52 passed）。
- `verify` / `subgraph` / `impact` 等命令目前**没有**无界枚举路径，
  故未加预算参数；新增长查询必须复用 `SearchBudget`（契约 §3 已写明）。
- 17 个 opensource skip 与 `trace impact` 定位问题（P158.12 / 未决讨论项）未动。

## 5. 影响的契约

- [SEMANTIC_CONTRACTS §3](../../dev/SEMANTIC_CONTRACTS.md)：dataflow 有界化的验收证据补齐；
  §11 状态表「长查询有界」→ ✅ P158.11。
- `json_contract_2026-10-31`：dataflow result 字段变更（新增截断字段，向后兼容：
  旧字段全部保留）。
