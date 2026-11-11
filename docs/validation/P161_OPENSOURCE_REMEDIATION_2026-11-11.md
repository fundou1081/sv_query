# P161 opensource remediation

**日期**: 2026-11-11
**状态**: ✅ 完成
**基线**: `2106bac2` + P160 triage

---

## 1. 前

```text
38 failed, 98 passed, 5 skipped
```

P160 分类：

```text
19 已退休 exp 命令
5 过期 golden/baseline
4 外部 fixture/filelist 缺失
10 旧 signal id / 旧断言
```

---

## 2. 后

```text
114 passed, 17 skipped, 0 failed
```

---

## 3. 做了什么

### A. 已退休 `exp`（19）

- `test_subfunction_golden_open_source.py`：
  - 删除 sva/timing/cdc/risk 的 10 个过期参数化用例；
  - 保留并重写 `stats` / `controlflow_analyze` / `dataflow_analyze`；
  - 3 个 sub-function × 2 fixture = 6 个 golden；
  - 删除 `n2` 对 8 个命令的旧假设，改为现行 3 个命令；
  - `_read_golden` 不再自动创建；缺失 baseline 直接失败，禁止 auto-bless。
- `test_naplespu_filelist.py`：
  - 修复原先两个 `pytestmark` 赋值互相覆盖的 bug（skip 被 opensource 覆盖）；
  - 8 个 `exp` 测试显式 `skip`，理由“命令已退休”；m01/m10/m11 继续运行。

### B. 旧 ID / 旧断言（10）

- NaplesPU：
  - `synchronizer.sync0` → `uart.u_uart_receive.rx_synchronizer.sync0`
  - `synchronizer.data_o` → `...rx_synchronizer.data_o`
- PicoRV32：
  - `picorv32.clk` → `picorv32_wb.clk`
  - `picorv32.mem_valid` → `picorv32_wb.mem_valid`
  - `picorv32_axi_adapter.xfer_done` → `picorv32_axi.axi_adapter.xfer_done`
- two_flop_sync：
  - `sub_a.data_a_i` → `two_flop_sync.u_a.data_a_i`
  - `sub_b.data_b_o` → `two_flop_sync.u_b.data_b_o`
- N4：不存在 signal 的 `controlflow` 从“静默 rc=0”改为显式 `rc=1` + `not found`
  （与 P158 的 unknown/not_found 契约一致）。

### C. Golden / baseline（5）

- `subfunction_open_source` 的 stats/controlflow/dataflow 6 个 golden 重新生成；
  旧 stats golden 的 modules/BIT_SELECT 计数已过时；
- `prim_arbiter_tree_req_to_gnt.json` 的 `n_intermediate` 8 → 0；
  8 条路径是 bit→bit 直接路径，旧的 8 个 intermediate 是 BIT_SELECT 结构点；
- `tools/benchmark/baselines/picorv32.json` 通过
  `regen_baselines.py picorv32` 重新生成（nodes 438 → 676）。
- 这两类都记录为**有意 rebaseline**，不是自动 bless：
  - 旧 `_read_golden` / `_read_golden_dataflow_data` 的 auto-create 已删除。

### D. 外部 fixture（4）

以下改为显式环境 skip，理由写入 skip message：

```text
CVA6 Flist.ariane 依赖缺失
OpenTitan tlul filelist 缺 tlul_xbar.sv / tlul_pkg
OpenTitan prim_fifo_sync 缺 prim_util_pkg / prim_fifo_sync_cnt
```

这不是产品通过，也不是产品失败；是环境证据不足。

---

## 4. 剩余 skip（17）

```text
3  benchmark_pr5 timeout
2  long-range pilot 无 .v
2  tlul fixture incomplete
2  cva6 / prim_fifo fixture incomplete
8  naplespu retired exp commands
```

全部有显式 reason；不再用 fail->skip 掩盖真实失败。

---

## 5. 证据

```text
pytest sim/tests/ -m opensource -q -p no:randomly
→ 114 passed, 17 skipped, 0 failed
```

canonical 不受影响：

```text
2677 passed, 0 failed
```

---

## 6. 结论

P157 的“0 skipped”问题现在有了更完整的答案：

- canonical 仍然独立；
- opensource 不再有 27% 红色；
- 8 个 retired exp 测试是**显式 skip**，不是隐藏失败；
- golden/baseline 的变更都有记录，不再 auto-bless；
- 环境缺失不再伪装成产品失败。
