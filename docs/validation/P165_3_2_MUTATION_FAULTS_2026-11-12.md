# P165.3.2 mutation fault set (independent oracle)

**日期**: 2026-11-12
**状态**: ✅ pilot 完成
**前置**: P165.3.1 Verilator oracle

## 1. 方法

不依赖 OpenTitan 历史，也不自撰 expected：

```text
mutation diff = ground truth
Verilator       = 独立 compile/elaboration oracle
sv_query        = 被验证的查询实现
```

流程：

1. 复制 RTL 到临时目录（不改原文件）；
2. 精确字符串替换一个驱动/连接；
3. Verilator `--lint-only -Wno-fatal` 证明 mutant 可 elaborate；
4. 对 baseline 和 mutant 跑同一个 sv_query 查询；
5. 用 mutation 前后事实（driver/load 集合）判定：
   - baseline 必须满足 before；
   - mutant 必须满足 after；
   - 否则 `failed`；mutant 不编译则 `invalid_mutant`。

## 2. 工具

```text
tools/agent/mutation_faults.py
tools/agent/task_corpora/mutation_faults_pilot.json
```

运行：

```bash
python3 tools/agent/mutation_faults.py \
  --tasks tools/agent/task_corpora/mutation_faults_pilot.json --json
```

## 3. Pilot 结果

```text
4 passed / 0 failed / 0 invalid
```

| task | mutation | before | after |
|---|---|---|---|
| `simple_driver_swap` | `data=din` → `data=en` | driver `top.din` | driver `top.en` |
| `simple_driver_removed` | `data=din` → `data=0` | `top.din` load `top.data` | no `top.data` load |
| `sync_second_flop_swap` | `sync1<=sync0` → `sync1<=async_i` | driver contains `sync0` | no `sync0` |
| `pico_dbg_mem_valid_swap` | `dbg_mem_valid=mem_valid` → `mem_ready` | contains `mem_valid` | contains `mem_ready`, no `mem_valid` |

pico 任务使用本机 `~/my_dv_proj/openrtl/picorv32/picorv32.v`；缺失时 runner
会报 `prepare` 错误，不会被当作 pass。

## 4. 这证明了什么 / 没证明什么

证明：

- 对 4 个可编译 mutant，查询事实确实跟随 mutation 改变；
- mutation ground truth 不是从 sv_query 反推的；
- Verilator 独立验证 mutant 可 elaborate；
- harness 会显式区分 query_error / invalid_baseline / invalid_mutant / failed。

没证明：

- 这不是“真实历史 bug 修复” benchmark；
- 4 个任务不能证明 agent 产品有效性；
- mutation 只覆盖 driver/load 两类局部事实，未覆盖 path/condition/CDC；
- pico 任务依赖本机外部源，不作为 CI 必过项。

## 5. 测试

```text
sim/tests/unit/test_mutation_faults.py
  1 passed (verilator skip if absent)
```
