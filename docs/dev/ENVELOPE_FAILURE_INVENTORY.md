# Envelope Failure Inventory — P182.1d phase 1 (read-only)

> **状态**: phase 1 完成（只读盘点）；**不是 gate**，不裁决 rc/ok 对错，不接 `run_gates.sh`。
> P182.1f 已在其上建立严格失败契约 gate：见 [ENVELOPE_FAILURE_CONTRACT](ENVELOPE_FAILURE_CONTRACT.md)。
> **来源**: `python3 tools/check_envelope_contract.py --failure-inventory --json`
> **Baseline**: 4e93f1af
> **日期**: 2026-11-18

## 1. 范围

对 P182.1c manifest 中的 **26 个 core standard 命令**各执行一条显式最小失败输入，
记录真实 CLI 的：

- `rc`
- 顶层 `ok`
- 顶层 `error_code`
- `errors` 是否存在 / 条数
- `result` 是否存在
- 描述性分类（非通过/失败判定）

`argv` 中的 fixture 均为仓库既有文件；失败本身就是“文件不存在”时，`fixture` 列为空，
不伪造可用输入。所有命令都找到了合法失败输入，因此本轮 **NO_FAILURE_INPUT = 0**；
工具仍支持该状态（附原因，且不执行命令）。

## 2. 汇总（当前树，2026-11-18）

```text
entries: 26/26 observed=26 no_failure_input=0
classification:
  operational_error (rc != 0)          22
  business_ok_false (rc=0, ok=false)   4
  usage_error                           0
  no_json_output                        0
  execution_error                       0
presence:
  顶层 error_code                        2
  errors 键                             20
  result 键                              5
```

- **operational rc1 = 22**：进程以非 0 退出；22 条全部有 JSON 信封（其中 16 条有 `errors` 键、6 条只有顶层 `error` 字段）。
- **business rc0/ok=false = 4**：`drivers` / `loads` / `trace evidence` /
  `trace profile` 的未知 signal。按任务要求**只记录，不修改**。
- 顶层 `error_code` 只有 `controlflow list-conditioned` 和 `stats` 两条
  （均为 `E_FILE_NOT_FOUND`）；其余失败信封没有顶层 `error_code`。
- `errors` 20 条全是 list：13 条 `list[str]`、7 条 `list[dict]`；另 6 条完全没有该键。
- `result` 只在 5 条失败路径上存在：4 条 business `ok=false` 的 trace 命令 +
  `scope`（`result: null`）。

这些计数是观测值，不是“应该如此”的契约。

## 3. 逐命令观测

| 命令 | 失败 argv | rc | ok | error_code | errors | result | 分类 |
|---|---|---|---|---|---|---|---|
| `drivers` | `drivers NoSuchSignal --filelist sim/tests/fixtures/scheduler_minimal/filelist.f --json` | 0 | false | — | `1` | yes | business_ok_false |
| `loads` | `loads NoSuchSignal --filelist sim/tests/fixtures/scheduler_minimal/filelist.f --json` | 0 | false | — | `1` | yes | business_ok_false |
| `trace evidence` | `trace evidence NoSuchSignal -f sim/tests/integration/dataflow_fixtures/sync_fifo.sv --json` | 0 | false | — | `1` | yes | business_ok_false |
| `trace profile` | `trace profile NoSuchSignal -f sim/tests/integration/dataflow_fixtures/sync_fifo.sv --json` | 0 | false | — | `1` | yes | business_ok_false |
| `trace lookup` | `trace lookup --path sync_fifo.data_out -f does_not_exist_p182_1d.sv --json` | 1 | false | — | `1` | no | operational_error |
| `trace manifest` | `trace manifest --path sync_fifo.data_out -f does_not_exist_p182_1d.sv --json` | 1 | false | — | `1` | no | operational_error |
| `trace constraints` | `trace constraints NoSuchItem -f sim/tests/fixtures/mixed_corpus/env_nested_constraint.sv --json` | 1 | false | — | `1` | no | operational_error |
| `trace constraint-neighborhood` | `trace constraint-neighborhood NoSuchItem -f sim/tests/fixtures/constraint_neighborhood.sv --json` | 1 | false | — | `1` | no | operational_error |
| `trace tb-join` | `trace tb-join tb_item.rcont -f sim/tests/fixtures/tb_join_tb.sv --from-snapshot no_such_snapshot_p182_1d --json` | 1 | false | — | absent | no | operational_error |
| `trace frontier` | `trace frontier top.nope --direction fanout -f sim/tests/fixtures/arch_pair.sv --json` | 1 | false | — | absent | no | operational_error |
| `trace constraint-chain` | `trace constraint-chain rnd_item.nope rnd_item.d -f sim/tests/fixtures/constraint_neighborhood.sv --json` | 1 | false | — | `1` | no | operational_error |
| `trace covergroups` | `trace covergroups -f does_not_exist_p182_1d.sv --json` | 1 | false | — | `1` | no | operational_error |
| `trace coverpoints` | `trace coverpoints top.e.nope -f sim/tests/fixtures/mixed_corpus/env_nested_constraint.sv --json` | 1 | false | — | `1` | no | operational_error |
| `trace covergroup` | `trace covergroup no_such_cg --instance top.e -f sim/tests/fixtures/mixed_corpus/env_nested_constraint.sv --json` | 1 | false | — | `1` | no | operational_error |
| `controlflow analyze` | `controlflow analyze NoSuchSignal --filelist sim/tests/fixtures/scheduler_minimal/filelist.f --json` | 1 | false | — | `1` | no | operational_error |
| `controlflow list-conditioned` | `controlflow list-conditioned --filelist does_not_exist_p182_1d.f --json` | 1 | false | `E_FILE_NOT_FOUND` | absent | no | operational_error |
| `dataflow analyze` | `dataflow analyze NoSuchSignal sync_fifo.data_out -f sim/tests/integration/dataflow_fixtures/sync_fifo.sv --json` | 1 | false | — | `1` | no | operational_error |
| `verify consistency` | `verify consistency -f does_not_exist_p182_1d.sv --json` | 1 | false | — | `1` | no | operational_error |
| `verify claim` | `verify claim -f sim/tests/fixtures/json_contract/struct.sv --claim {bad json --json` | 1 | false | — | `1` | no | operational_error |
| `verify structural` | `verify structural -f does_not_exist_p182_1d.sv --json` | 1 | false | — | `1` | no | operational_error |
| `scope` | `scope top.nope -f sim/tests/fixtures/json_contract/struct.sv --json` | 1 | false | — | `1` | yes | operational_error |
| `stats` | `stats --file does_not_exist_p182_1d.sv --json` | 1 | false | `E_FILE_NOT_FOUND` | absent | no | operational_error |
| `graph nodes` | `graph nodes --filelist does_not_exist_p182_1d.f --json` | 1 | false | — | absent | no | operational_error |
| `graph edges` | `graph edges --filelist does_not_exist_p182_1d.f --json` | 1 | false | — | absent | no | operational_error |
| `filelist prune` | `filelist prune --filelist sim/tests/fixtures/minimal_3module/filelist.f --top top_minimal --output p182_1d_bad_output.txt --json` | 1 | false | — | `1` | no | operational_error |
| `graph subgraph` | `graph subgraph sync_fifo.nope -f sim/tests/integration/dataflow_fixtures/sync_fifo.sv --depth 1 --json` | 1 | false | — | `1` | no | operational_error |

## 4. 失败输入的选择说明

- **语义失败优先**：未知 signal / scope / covergroup / claim JSON 等，使用仓库既有
  fixture，因此能区分“输入语义错误”与“文件不存在”。
- **缺失文件**：命令没有更小且稳定的语义失败入口时使用（`trace lookup`、
  `trace manifest`、`trace covergroups`、`verify consistency`、
  `verify structural`、`stats`、`graph nodes`、`graph edges`、
  `controlflow list-conditioned`）。`trace lookup/manifest` 的未知 path 实际是
  `rc=0, ok=true, found=false`，不算失败输入，故改用缺失源文件。
- **`trace tb-join`**：使用合法字段 + 不存在的 snapshot tag；工具在临时
  `SVQ_SNAPSHOT_DIR` 内运行，不接触用户快照。
- **`filelist prune`**：使用真实 filelist + 非法输出后缀 `.txt`；默认 dry-run，
  验证在写文件前失败，不落盘。
- 未编造 fixture；未生成一次性 RTL 输入。

## 5. 复现

```bash
# 文本表 + 汇总；exit 恒为 0（只读观测，不 gate）
python3 tools/check_envelope_contract.py --failure-inventory

# 机器可读（26 条 rows，每命令一条）
python3 tools/check_envelope_contract.py --failure-inventory --json

# 定向测试
python3 -m pytest sim/tests/unit/test_p182_1d_failure_inventory.py -q -p no:randomly
```

`--failure-inventory` 永远返回 0；manifest 自身问题或观测到的任何 rc/ok 不一致只打印，
不改变退出码，也不做 PASS/FAIL 判定。

## 6. 不能从这个盘点得出的结论

- 不能据此判定失败信封“正确”或“错误”；它只记录现状。
- 不能把 `rc=0/ok=false`（drivers/loads/evidence/profile）当成已修复或已裁决。
- 不能据此推断 direct / exp / truncated 命令的失败行为。
- 不能用它替代成功路径矩阵（`--matrix-core`）或 canary（`--canary`）。
- 不能把它接入 `run_gates.sh`：本模式不是 gate。

下一步（P182.1d phase 2 / P182.1e）：由主会话裁决失败信封是否需要统一
`error_code` / `errors` / rc 语义；本阶段未改 `src/`、CLI、registry。
