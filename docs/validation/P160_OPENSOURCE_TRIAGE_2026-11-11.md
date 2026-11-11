# P160 opensource test triage

**日期**: 2026-11-11
**状态**: ✅ 分诊完成；P161 已修复（114 passed / 17 skipped / 0 failed）
**基线**: `2106bac2` + 本地 canonical baseline (see INDEX)

---

## 1. 运行结果

```text
python3 -m pytest sim/tests/ -m "opensource" -q -p no:randomly -rA
38 failed, 98 passed, 5 skipped, 2677 deselected
```

skips：

```text
3 × test_benchmark_pr5  (wrapper benchmark 300s timeout)
2 × test_run_long_range_runner (pilot axi/serv 无 .v)
```

> worker `svq-p160-opensource` 因 MiniMax 429 配额中断，本报告由主会话完成。
> 所有分类均来自实际失败输出，不是按测试名猜的。

---

## 2. 分类汇总

| 类别 | 数量 | 处理原则 |
|---|---:|---|
| A. 已退休 `exp` 子命令 | 19 | 更新到现行命令，或明确归档；不能永久 skip |
| B. 过期 golden / benchmark baseline | 5 | 必须人工/RTL oracle 复核后 rebless，禁止自动 bless |
| C. 外部 fixture / filelist 缺失 | 4 | 环境分类；显式 fail/skip with reason，不进 canonical 假绿 |
| D. 旧 signal id / 旧 contract 断言 | 10 | 按当前语义更新测试，或确认是产品 bug |
| **合计** | **38** | |

**目前没有确认的“核心产品 real bug”**；最需要警惕的是 B 和 D 中可能混有语义回归，
不能直接改 expected。

---

## 3. A. 已退休 `exp` 子命令（19）

`sv_query exp` 入口已不存在；这些测试仍调用 `exp sva/timing/cdc/risk/...`，rc=2。

### A1. `test_subfunction_golden_open_source.py` 11

```text
strict_uart-sva_extract
strict_uart-sva_coverage
strict_uart-timing_analyze
strict_uart-cdc_analyze
strict_uart-risk_analyze
prim_arbiter-sva_extract
prim_arbiter-sva_coverage
prim_arbiter-timing_analyze
prim_arbiter-cdc_analyze
prim_arbiter-risk_analyze
n2_strict_uart_partial_graph_all_8_subfunctions
```

证据：

```text
No such command 'exp'.
```

结论：测试的**命令契约已过期**；不是当前 CLI 的行为失败。
建议：把 sva/timing/cdc/risk 迁到现行命令（若仍存在）或归档测试并更新
P145 corpus 的 equivalent；n2 要么重写为现行命令，要么明确退休。

### A2. `test_naplespu_filelist.py` 8

```text
test_m02_risk_filelist
test_m03_cdc_filelist
test_m04_sva_extract_filelist
test_m05_sva_coverage_filelist
test_m06_sva_timing_filelist
test_m07_timing_filelist
test_m08_verify_gap_filelist
test_m09_coverage_suggest_filelist
```

同样 `No such command 'exp'`。

注意：同文件的 `m10_controlflow` / `m11_dataflow` **通过**，说明 filelist 本身可用，
问题只在 `exp` 命令路径。

---

## 4. B. 过期 golden / benchmark baseline（5）

### B1. `stats` golden ×2

```text
strict_uart-stats
prim_arbiter-stats
```

实测差异（strict_uart）：

```text
golden: nodes 39, edges 42, modules []
actual: nodes 35, edges 51, modules [sync_fifo, synchronizer, uart_top]
```

这**不是自动 bless 的场景**：可能包含 P158.1/P158.3 后的合理图变化
（modules 已填充、BIT_SELECT 计数上升），必须用 RTL/图语义复核后才更新 golden。

### B2. `test_golden_dataflow_arbiter`

```text
actual: n_intermediate=0
golden: n_intermediate=8
```

这可能是数据边语义修正后的预期变化，也可能是 `DataFlowSegment` 收集回归；
需要对照 RTL 路径手工确认，不能直接改 golden。

### B3. picorv32 benchmark baseline ×2

```text
test_picorv32_l2_node_count_matches_baseline
test_baseline_matches_current_behavior
actual nodes=676, baseline=438
```

这是 **baseline 过期** 或图行为变化；`regen_baselines.py` 前必须评审。

---

## 5. C. 外部 fixture / filelist 缺失（4）

| 测试 | 缺失 |
|---|---|
| `test_p3_latency_cva6_alu_0_cycle_combinational` | cva6 `Flist.ariane` 多文件/incdir 缺失，elaboration 失败 |
| `test_real_opentitan_prim_fifo_sync_passthrough` | `prim_util_pkg` / `prim_fifo_sync_cnt` 缺失 |
| `test_p6_opentitan_tlul_controlflow_list_conditioned` | `opentitan_tlul.f` 中 `tlul_xbar.sv` 缺失 + tlul_pkg 等 |
| `test_n3_opentitan_tlul_dataflow_unresolvable` | 同上；测试原本期望 “not found”，实际先撞 elaboration |

这些不是“产品必然失败”，但不能静默：应在测试里显式检查 fixture/依赖并给出环境
skip/fail 分类，或把依赖闭包固化进 repo。

---

## 6. D. 旧 signal id / 旧 contract 断言（10）

| 测试 | 观察 |
|---|---|
| `test_p1_naplespu_dataflow_analyze` | 查询 `synchronizer.sync0`，图中无此 id；图现在是 `uart.*` 命名 |
| `test_p2_naplespu_controlflow_analyze` | 同上类旧 id |
| `test_p7_picorv32_dataflow_analyze` | `picorv32.clk` not found；需要正确 top/hierarchical id |
| `test_p8_picorv32_controlflow_list_conditioned` | 同上 |
| `test_n1_latency_two_flop_sync_async_crossing` | 查询 `sub_a.data_a_i`，实际是 `two_flop_sync.u_a...` |
| `test_n4_picorv32_controlflow_nonexistent_signal` | 断言 rc=0，但当前 nonexistent signal 显式 rc=1（新契约更正确） |
| `strict_uart-controlflow_analyze` | 需要确认为 P158.1 后路径/信号变化 |
| `prim_arbiter-controlflow_analyze` | 同上 |
| `strict_uart-dataflow_analyze` | 同上 |
| `prim_arbiter-dataflow_analyze` | 同上 |

建议：先按当前 canonical ID 解析修复测试；如果 ID 确实丢失，开产品 bug，
不要把 not found 改成 skip。

---

## 7. CI 策略建议

1. **opensource 必须可见**：保留 non-blocking report，但报告必须给
   `failed/passed/skipped` 分类，并链接本文件/后续 P160 修复记录。
2. **A 类立即处理**：19 个 `exp` 测试不能长期红；更新或归档，归档要有
   “命令已退休”证据。
3. **B 类单独审批**：golden/baseline rebless 必须附 RTL/语义说明，不允许 auto-bless。
4. **C 类环境隔离**：外部 fixture 缺失显式环境分类；不进入 canonical。
5. **D 类逐个修**：优先修 stale ID（p1/p2/p7/p8/n1）和错误断言（n4），
   再复核 controlflow/dataflow 的 4 个 golden。
6. **指标**：opensource 失败数进入 CI summary；`canonical 0 skipped` 不能代表
   opensource 健康。

---

## 8. 结论

- 38 个失败中，**19 个是命令契约过期**，不是产品当前失败；
- 4 个是外部依赖缺失；
- 5 个是 golden/baseline 需要人工复核；
- 10 个是旧 signal id / 旧断言，其中可能混有真实语义回归，必须逐个查。

下一步 P160 修复顺序：

```text
1. 清理/迁移 19 个 exp 测试
2. 修 6 个 stale ID + 2 个错误断言
3. 复核 4 个 controlflow/dataflow golden
4. 复核 stats/dataflow/picorv32 baseline
5. 固化外部依赖或显式环境分类
```
