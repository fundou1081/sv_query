# P165.3.3 mutation coverage expansion

**日期**: 2026-11-13
**状态**: ✅ 完成（pilot 扩展）
**前置**: P165.3.2 4-task pilot

## 1. 扩展

从 4 个 mutation 扩到 10 个，覆盖：

```text
drivers
loads
paths
controlflow conditions
dataflow / CDC bypass
bit-select
```

任务定义：

```text
tools/agent/task_corpora/mutation_faults_pilot.json
```

runner：

```text
tools/agent/mutation_faults.py
```

新增 facts 抽象：

```text
drivers/loads -> item set
paths         -> path item set + found
controlflow   -> condition expression set
dataflow      -> intermediate_signals + clock_domain/primary_is_async/is_reachable
```

## 2. 结果

```text
10 passed / 0 failed / 0 invalid
```

| task | mutation | 验证事实 |
|---|---|---|
| `simple_driver_swap` | `data=din` → `data=en` | driver 集合 |
| `simple_driver_removed` | `data=din` → `data=0` | load 集合 |
| `sync_second_flop_swap` | `sync1<=sync0` → `sync1<=async_i` | driver 集合 |
| `pico_dbg_mem_valid_swap` | `dbg_mem_valid=mem_valid` → `mem_ready` | driver 集合 |
| `simple_path_removed` | 换源 | `paths.found: true → false` |
| `simple_path_added` | 换源 | `paths.found: false → true` |
| `simple_condition_invert` | `if (en)` → `if (!en)` | controlflow 条件集合 |
| `mux_condition_invert` | `if (sel_a)` → `if (!sel_a)` | controlflow 条件集合 |
| `cdc_bypass_first_stage` | 绕过第一级同步 | dataflow intermediates + `primary_is_async` |
| `bit_select_swap` | `sum[7:0]` → `sum[15:8]` | driver 位节点 |

## 3. 独立 oracle

每个 mutant 都由 Verilator `--lint-only -Wno-fatal` 验证可 elaborate。
`pico` 任务使用本机外部 `picorv32.v`；缺失时显式 prepare error。

## 4. 这证明什么 / 没证明什么

证明：

- mutation diff 是 ground truth，不是从 sv_query 反推；
- runner 能区分 driver/load/path/condition/dataflow 事实；
- path / condition / CDC 三层都有可执行 mutation；
- 每个任务有 before/after 双侧断言，baseline 不满足则 invalid_baseline。

没证明：

- 不是真实历史 bug benchmark；
- 10 个任务仍不是统计显著；
- mutation 只覆盖局部结构事实，不代表完整 agent 效果。

## 5. 测试

```text
sim/tests/unit/test_mutation_faults.py
  4 passed (driver + path + condition + CDC)
```

完整 pilot：

```bash
python3 tools/agent/mutation_faults.py \
  --tasks tools/agent/task_corpora/mutation_faults_pilot.json --json
```
