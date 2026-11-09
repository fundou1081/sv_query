# sv_query × OpenTitan Onboarding Report — Second Block: `hw/ip/i2c`

**Date:** 2026-11-09
**Tool:** `sv_query` (`/Users/fundou/miniconda3/bin/sv_query`)
**Purpose:** onboard a second OpenTitan block using the recipe proven on `hw/ip/uart`.
**UART artifacts (`/tmp/opentitan_svq/`) were NOT modified by this work.**

---

## 1. Source path / HEAD

| Item | Value |
|---|---|
| Source repo | `/Users/fundou/my_dv_proj/openrtl/opentitan` |
| Worktree (used) | `/Users/fundou/.dsh/opencode-workers-lite/opentitan-pilot/workspace` |
| HEAD | `a82c4892e88253924b3f7af05ce7494232ab263a` (same commit as the UART pilot) |
| HEAD subject | `[doc] Update ILA debugging documentation` |
| Tracked-file modifications | **none** (`git status --porcelain` → only pre-existing untracked `AGENTS.md`) |

## 2. Block choice

`hw/ip/i2c`, top module `i2c`. This was the survey's #1 recommendation: 10 own RTL files,
15 direct prim/tlul instantiations, only 2 tech-specific cells (`prim_flop`, `prim_flop_2sync` —
both already present in the working UART filelist), no async-RAM/CDC, and a larger register file
than UART (210 `logic` fields in `i2c_reg_pkg.sv` vs UART's 107).

`.core` `files_rtl.depend` (`hw/ip/i2c/i2c.core`):
`virtual_constants:top_pkg`, `prim:all`, `prim:ram_1p_pkg`, `prim:ram_1p_adv`, `ip:tlul`,
`ip:i2c_pkg`, `virtual_constants:top_racl_pkg`. Toplevel: `i2c`.

## 3. Filelist — `/tmp/opentitan_svq_i2c/opentitan_i2c.f`

**103 lines total: 4 `+incdir+` + 67 source files (+ 32 comment/blank lines).**

| Group | Files |
|---|---|
| prim macro/header units (include-only) | `prim_assert.sv`, `prim_assert_{standard,dummy,yosys}_macros.svh`, `prim_assert_sec_cm.svh`, `prim_flop_macros.sv`, `prim_fifo_assert.svh` (7) |
| prim packages | `prim_alert_pkg`, `prim_mubi_pkg`, `prim_subreg_pkg`, `prim_util_pkg` (4) |
| prim cells (direct) | `prim_alert_sender`, `prim_arbiter_tree`, `prim_count`, `prim_diff_decode`, `prim_fifo_sync`, `prim_fifo_sync_cnt`, `prim_intr_hw`, `prim_onehot_check`, `prim_onehot_enc`, `prim_ram_1p_adv`, `prim_reg_we_check`, `prim_sec_anchor_buf`, `prim_sec_anchor_flop`, `prim_subreg`, `prim_subreg_arb`, `prim_subreg_ext` (16) |
| prim secded | `prim_secded_pkg` + 8 hamming/22_16/39_32 inv variants + `prim_secded_inv_64_57_{dec,enc}` (11) |
| prim_generic (tech-independent) | `prim_buf`, `prim_flop`, `prim_flop_2sync`, `prim_xnor2`, `prim_xor2`, `prim_and2`, `prim_const`, `prim_const_sec`, `prim_ram_1p`, `prim_ram_1p_pkg` (10) |
| tlul | `tlul_pkg`, `tlul_adapter_reg`, `tlul_cmd_intg_chk`, `tlul_rsp_intg_gen`, `tlul_data_integ_{dec,enc}`, `tlul_err` (7) |
| i2c | `i2c_pkg`, `i2c_reg_pkg`, `i2c_reg_top`, `i2c_fifo_sync_sram_adapter`, `i2c_fifos`, `i2c_core`, `i2c_bus_monitor`, `i2c_controller_fsm`, `i2c_target_fsm`, `i2c.sv` (10) |
| top virtual constants | `hw/top_earlgrey/rtl/top_pkg.sv`, `hw/top_earlgrey/rtl/autogen/top_racl_pkg.sv` (2) |

`+incdir+`: `hw/ip/prim/rtl`, `hw/ip/prim_generic/rtl`, `hw/ip/tlul/rtl`, `hw/ip/i2c/rtl`.

## 4. Snapshot

```bash
export SVQ_SNAPSHOT_DIR=/tmp/opentitan_svq_i2c/snapshots
cd /Users/fundou/.dsh/opencode-workers-lite/opentitan-pilot/workspace
python3 /Users/fundou/my_dv_proj/sv_query/tools/agent/setup_snapshot.py \
  --path . --tag opentitan_i2c --filelist /tmp/opentitan_svq_i2c/opentitan_i2c.f \
  --snapshot-dir /tmp/opentitan_svq_i2c/snapshots --source-root . --json
```

| Stat | i2c | UART (ref) |
|---|---|---|
| Files compiled | 67 | 60 |
| Nodes | **9370** | 4803 |
| Edges | **17599** | 8507 |
| Elaboration errors | **0** | 0 |
| Failed files | 0 | 0 |
| `strict_mode` | true | true |
| Snapshot size | 12,739,756 B (12.1 MB) | 6,183,653 B (5.9 MB) |
| Build time (cold) | **16.50 s** | 7.57 s |
| Build time (warm) | 16.41 s | 7.80 s |
| Query latency from snapshot | 0.45 s | 0.30 s |
| Elaboration warnings | 378 | 173 |
| `dynamic_nodes` | **247** | 1 |
| `function_nodes` | 0 | 30 |

Node kinds: SIGNAL 5706, PORT_IN 1853, PORT_OUT 987, INSTANTIATED_MODULE 307, OP_TERNARY 253,
REG 234, CONST 28, GENERATE_BLOCK 2.
Edge kinds: BIT_SELECT 6995, DRIVER 6505, CONNECTION 2149, CLOCK 547, RESET 537,
BRANCH_CONDITION 257, BRANCH_RESULT 253, BRANCH_FALSE 183, BRANCH_TRUE 173.

Note the `dynamic_nodes` jump (1 → 247): the I2C FIFO/arbiter/SRAM instances create far more
dynamically-indexed nodes (`i2c.storage[fifo_rptr]`, `i2c.gnt_o[idx_o]`, `i2c.mem[addr_i]`).
The I2C is noticeably more array/pointer-heavy than UART.

## 5. Frozen tasks — `/tmp/opentitan_svq_i2c/opentitan_i2c_tasks.json`

All 3 are answerable **from the snapshot alone** (`--from-snapshot`); no task needs source text.

| id | kind | Subject | Expected |
|---|---|---|---|
| **I2C-T1** | `direct_neighbors` | `i2c.u_reg.intr_test_qe` (the INTR_TEST write-enable gate) + empty-side case on `i2c.u_reg.reg2hw.intr_test.fmt_threshold.qe` | 1 driver (`i2c.u_reg.intr_test_flds_we`), **15** loads (the 15 `reg2hw.intr_test.<field>.qe`); empty side: 2 drivers, **0 loads** |
| **I2C-T2** | `directed_path` | `i2c.i2c_core.scl_out_fsm` → `i2c.cio_scl_en_o` | **found**, **4 hops** (canonical), 2 candidates; path `scl_out_fsm → scl_o.ternary_override → scl_o → scl_int → cio_scl_en_o` |
| **I2C-T3** | `verify_claim` | 5 claims + 1 reverse-direction control | A `verified`, B `verified`, C `contradicted`, D `verified`, E `contradicted` (documented inversion false-negative), control `contradicted` |

### Verification (all pass — 0 failures)

```
PASS T1 drivers
PASS T1 loads == frozen 15 :: 15
PASS T1 empty-side drivers
PASS T1 empty-side loads == 0
PASS T2 canonical path == frozen :: hops=4
PASS T2 non-canonical hops==3 :: 3
PASS T2 --all count==2 :: 2
PASS T3 verified :: verified      (claim A: err_q -> intg_err_o)
PASS T3 verified :: verified      (claim B: intg_err_o -> alerts[0])
PASS T3 contradicted :: contradicted  (claim C: sda_out_fsm -> scl_out_fsm)
PASS T3 verified :: verified      (claim D: scl_out_fsm -> scl_o)
PASS T3 contradicted :: contradicted  (claim E: scl_out_fsm -> cio_scl_en_o)
PASS T3 contradicted :: contradicted  (control: intg_err_o -> err_q)
=== TOTAL FAILURES: 0 ===
```

Source confirmation:
- `hw/ip/i2c/rtl/i2c_reg_top.sv:1177-1179` — `logic intr_test_qe; logic [14:0] intr_test_flds_we;
  assign intr_test_qe = &intr_test_flds_we;` then exactly **15**
  `assign reg2hw.intr_test.<field>.qe = intr_test_qe;` statements (lines 1194…1402).
- `hw/ip/i2c/rtl/i2c_core.sv:247, 266-275, 534, 590` — the T2 chain.
- `hw/ip/i2c/rtl/i2c_reg_top.sv:76-87` and `hw/ip/i2c/rtl/i2c.sv:84, 101` — the T3 alert chain.
- `hw/ip/i2c/rtl/i2c.sv:154` — `assign cio_scl_en_o = ~scl_int;` (the T3 claim-E inversion).

## 6. Was the i2c closure actually easier than UART?

**Yes — substantially, in effort; but bigger in output.**

| Dimension | UART | i2c | Verdict |
|---|---|---|---|
| Elaboration iterations to reach 0 errors | **4** | **1** | **much easier** |
| Direct prim/tlul deps to resolve | 20 | 15 | easier |
| Tech-specific cells needing manual mapping | 9 (`prim_buf`, `prim_flop`, `prim_flop_2sync`, `prim_clock_gating`, `prim_xnor2`, `prim_xor2`, `prim_and2`, `prim_const`, `prim_const_sec`) | 10 (`prim_buf`, `prim_flop`, `prim_flop_2sync`, `prim_xnor2`, `prim_xor2`, `prim_and2`, `prim_const`, `prim_const_sec`, `prim_ram_1p`, `prim_ram_1p_pkg`) | similar, but **2 of the 10 were new discoveries** (`prim_ram_1p` + `prim_ram_1p_pkg`, pulled in by `prim_ram_1p_adv`) |
| Files in closure | 60 | 67 | similar |
| Nodes / edges | 4803 / 8507 | 9370 / 17599 | **~2× bigger** |
| Build time | 7.6 s | 16.5 s | **~2× slower** |
| `verify consistency` violations | 487 | 806 | **more** (same class, larger reg file) |
| `reciprocity` check | **fail** (5 violations) | **pass** (0) | **better** |
| `dynamic_nodes` | 1 | 247 | **much worse** (array/pointer-heavy) |

**Why it was easier:** the UART pilot's cost was almost entirely *discovering* the rules — which
prim cells live in `hw/ip/prim/rtl` vs `hw/ip/prim_generic`, that `.svh` macro files must not be
listed as compile units, that `top_pkg`/`top_racl_pkg` live under `hw/top_earlgrey/rtl`, and that
`+incdir+` is mandatory. All of that was already known, so the i2c filelist was derived directly
by source inspection (direct instantiations → one level of transitive prim deps → tech-specific
mapping) rather than by trial and error. **Zero elaboration errors on the first attempt.**

**Why it is bigger:** the I2C has a much larger register file (210 vs 107 reg_pkg `logic` fields),
three FIFOs with an arbiter tree, a dual-port SRAM adapter, two FSMs and a bus monitor — i.e.
roughly twice the datapath. Build time and snapshot size scale accordingly.

**New difficulty specific to i2c:** the SRAM path. `prim_ram_1p_adv` instantiates the
technology-specific `prim_ram_1p` and imports `prim_ram_1p_pkg` — **neither exists in
`hw/ip/prim/rtl`**; both live only in `hw/ip/prim_generic/rtl/`. This was the one dependency the
UART recipe had no precedent for.

## 7. Exact onboarding issues encountered

### Issue 1 — `prim_ram_1p` / `prim_ram_1p_pkg` are technology-specific and were not in the UART set
`prim_ram_1p_adv` (pulled in by `i2c_fifo_sync_sram_adapter`) instantiates `prim_ram_1p` and
`import prim_ram_1p_pkg::*`. Neither file exists in `hw/ip/prim/rtl/`; only
`hw/ip/prim_generic/rtl/{prim_ram_1p,prim_ram_1p_pkg}.sv` do (plus `prim_xilinx/rtl/prim_ram_1p.sv`).
The `.core` lists `lowrisc:prim:ram_1p_pkg` explicitly, so the dependency *is* declared — but it
is the only i2c dependency that the UART recipe did not already cover.

### Issue 2 — `prim_ram_1p_adv` drags in 8 secded ECC variants
`prim_ram_1p_adv` instantiates `prim_secded_inv_{22_16,39_32,hamming_22_16,hamming_39_32}_{dec,enc}`
— 8 extra files that the UART closure never needed (UART only needed the 64_57 pair for TL-UL
integrity). This is the single largest driver of the i2c filelist delta.

### Issue 3 — `.core` `depend` lists are a strict superset of the true closure
`hw/ip/i2c/i2c.core` lists `lowrisc:prim:all` (162 files) — which cannot elaborate (see the UART
report). The real closure had to be derived from actual `pkg::` references and instantiations.
As with UART, `lc_ctrl_pkg`-style dead deps are a hazard (here `prim:all` itself is the dead dep).

### Issue 4 — `top_pkg` / `top_racl_pkg` are still required from outside the block
`hw/ip/i2c/rtl/i2c.sv` and `i2c_reg_top.sv` reference `top_pkg::` (3 refs) and `top_racl_pkg::`
(8 refs) — exactly like UART. The `top_earlgrey` variants must be listed explicitly even though
they live under `hw/top_earlgrey/rtl/`, not `hw/ip/i2c`.

### Issue 5 — `drivers` does not traverse bitwise-NOT (new false negative, I2C-specific)
`i2c.sv:154` is `assign cio_scl_en_o = ~scl_int;`. The driver fanin of `i2c.cio_scl_en_o` reports
`i2c.scl_int` at distance 1 and `i2c.i2c_core.scl_o` at distance 2, but **`scl_out_fsm` is absent**,
so `verify claim --type driver` returns **contradicted** for a claim that is true in the RTL.
The **path** claim for the same pair (`scl_out_fsm → cio_scl_en_o`) **is verified**, and the
canonical path in I2C-T2 traverses the inversion happily. This is the same
family of `drivers` vs `paths` disagreement documented for the UART ternary case, but triggered by
`~` instead of a ternary. **Any grader that reads `contradicted` as "wrong" will mis-grade this.**

### Issue 6 — `drivers` fanin omits a term of a compound continuous assign
`i2c_bus_monitor.sv:113` is
`assign start_det = monitor_enable && start_det_pending && (ctrl_det_count >= 14'(thd_dat_i));`
and `start_det_trigger` (line 112) depends on `sda_i_q`/`scl_i_q`. The reported drivers of
`u_i2c_bus_monitor.start_det` include `monitor_enable`, `start_det_pending`, `ctrl_det_count` and
`thd_dat_i`, but **not** `sda_i_q` — so `paths --directed` finds **no** path from
`i2c.cio_sda_i` to `i2c.i2c_core.start_detect` even though the RTL clearly connects them
(`sda_i_q` → `start_det_trigger` → `start_det_pending` → `start_det` → `start_detect_o`).
This is a genuine **fanin-completeness gap** for compound boolean expressions.

### Issue 7 — Same `paths` canonical ambiguity as UART
For I2C-T2, `paths --directed` returns a **3-hop** path while `paths --directed --canonical`
returns the **4-hop** path; `--all` shows exactly 2 distinct directed paths (4 and 5 hops). The
canonical policy (`max_nodes_then_lexicographic`) is deterministic, but `--canonical` **must** be
pinned in any frozen expectation. Same failure mode that produced the
`ot_uart_rx_path` false_confident in the earlier benchmark.

### Issue 8 — `verify consistency` reports 806 violations on a correct design
```
verified=false  total_violations=806
  reciprocity : pass  (checked 14,   skipped 186,    0 violations)   <- better than UART
  bit_mapping : fail  (checked 3756, skipped 0,    806 violations)
  connection  : pass  (checked 2657, skipped 0,      0 violations)
```
Violations: `width_mismatch` ×781, `id_parent_mismatch` ×15, `parent_range_out_of_bounds` ×10.
Same root cause as UART — the reggen packed-struct convention (`{q, qe}` packed into one bit)
being mis-measured (e.g. `i2c.gen_alert_tx[0].u_prim_alert_sender.alert_rx_i.ack_n` reports
`node_bits=2, parent_bits=1`). **Impact on the frozen tasks: none** — the violations are at
*bit-node* level; the field-level driver/load lists T1 asks about are clean, and no task signal
(`intr_test_qe`, `scl_out_fsm`, `err_q`, `intg_err_o`, `alerts[0]`, `cio_scl_en_o`) has a
violation on the node itself. `i2c.u_reg.reg2hw.intr_test.*` has 30, all at bit level.
**Treat `verify consistency` as advisory on OpenTitan, not as a gate.**

### Issue 9 — `dynamic_nodes` explosion
247 dynamic nodes (vs UART's 1), from FIFO storage (`i2c.storage[fifo_rptr]`), the arbiter
(`i2c.gnt_o[idx_o]`, `i2c.req_i[idx_o]`), and the SRAM (`i2c.mem[addr_i]`). These are indexed
by non-constant expressions, so their edges are weaker than static ones. Any task touching the
FIFO/arbiter/SRAM internals should expect coarser answers than the register-file tasks.

### Issue 10 — Instance naming surprise
The register-file instance is `i2c.u_reg` (module type `i2c_reg_top`), **not**
`i2c.i2c_reg_top`. The same pattern as UART's `uart.u_reg`. A task author who greps the module
name rather than the instance name will pick non-existent ids.

### Issue 11 — Snapshot evidence: partially fixed since the UART pilot
`trace evidence --from-snapshot` now returns a **populated `source_location`**
(`{'file': 'i2c_core.sv', 'line_start': 267, ...}`) where the UART pilot got `None` — the
P119.4 "snapshot trace evidence fallback" landed. But `source_text` is still `''` from the
snapshot, and with `--filelist` the location differs slightly (line 267 vs 268, different column)
because the snapshot stores the *driver* site and the live parse reports the *reset* site.
**Source text still requires `--filelist`**, so an evidence task is still not snapshot-only —
which is why I chose `verify claim` for task 3.

## 8. Remaining risks

1. **Task I2C-T3 claim E encodes a tool bug as ground truth.** It is *correct* as a record of the
   tool's output, but a future tool fix (traversing `~`) would flip it to `verified` and break the
   frozen expectation. This is the same fragility the UART pilot had with the ternary
   `tx_out_q` case. Mitigation: the task JSON documents the RTL truth and the interpretation
   explicitly, so a grader can distinguish "tool regression" from "wrong answer".
2. **`reciprocity` skipping is high on i2c** (186 of 200 nodes skipped vs 59 of 200 on UART) —
   the checker is exercising far fewer nodes on this design, so a `pass` is weaker evidence.
3. **247 dynamic nodes** weaken the FIFO/arbiter/SRAM parts of the graph. The 3 frozen tasks
   deliberately avoid them (register file + controller/target FSM + alert path), but a future
   task set wanting FIFO datapath questions should expect coarser answers.
4. **`bit_mapping` false positives scale with the register file** (487 → 806). As blocks get
   bigger, `verify consistency` becomes progressively noisier and less usable as a signal.
5. **The filelist is hand-curated again**, though less painfully: it was derived from source
   inspection using the now-known rules, so a third block (e.g. `spi_device`) should be
   cheaper still — but it is still not machine-derived, and `filelist prune` remains unusable
   because it retains include-only `.svh` files.
6. **`top_pkg`/`top_racl_pkg` remain `top_earlgrey`-specific.** A different top has different
   `TL_AW`/`TL_DW` and therefore a different graph.
7. **Snapshot `git_commit` is still empty** (`setup_snapshot.py` does not pass `--git`).
8. **Build time is now 16.5 s and the snapshot 12 MB.** For a full-top snapshot the filelist
   approach may not scale; the growth from 60→67 files costing 7.6→16.5 s suggests superlinear
   cost in the number of elaborated modules.

## 9. Artifact index

| Path | Contents |
|---|---|
| `/tmp/opentitan_svq_i2c/opentitan_i2c.f` | 103-line filelist (67 source files + 4 `+incdir+`) |
| `/tmp/opentitan_svq_i2c/snapshots/opentitan_i2c.json` | The snapshot (9370 nodes / 17599 edges, 0 elaboration errors, 12.1 MB) |
| `/tmp/opentitan_svq_i2c/snapshots/opentitan_i2c.meta.json` | Tag / snapshot path / source_root / filelist / query_bin |
| `/tmp/opentitan_svq_i2c/snapshots/opentitan_i2c.env.sh` | `export SVQ_SNAPSHOT_DIR=… SVQ_SOURCE_ROOT=… SVQ_QUERY_BIN=…` |
| `/tmp/opentitan_svq_i2c/opentitan_i2c_tasks.json` | The 3 frozen tasks (`meta` + `tasks[]`) with `id, block, snapshot, source_root, snapshot_dir, kind, question, expected, ground_truth_command, verification` |
| `/tmp/opentitan_svq_i2c/verify_i2c_tasks.sh` | Re-runnable ground-truth transcript script |
| `/tmp/opentitan_svq_i2c/REPORT.md` | This report |

### Reproduce end-to-end

```bash
export SVQ_SNAPSHOT_DIR=/tmp/opentitan_svq_i2c/snapshots
cd /Users/fundou/.dsh/opencode-workers-lite/opentitan-pilot/workspace

# rebuild the snapshot (~16.5 s)
python3 /Users/fundou/my_dv_proj/sv_query/tools/agent/setup_snapshot.py \
  --path . --tag opentitan_i2c --filelist /tmp/opentitan_svq_i2c/opentitan_i2c.f \
  --snapshot-dir "$SVQ_SNAPSHOT_DIR" --source-root . --json

# re-verify all 3 tasks
bash /tmp/opentitan_svq_i2c/verify_i2c_tasks.sh
```
