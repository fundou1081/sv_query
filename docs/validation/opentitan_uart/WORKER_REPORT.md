# sv_query × OpenTitan Onboarding Report — `hw/ip/uart`

**Date:** 2026-11-09
**Tool:** `sv_query` v1.x (`/Users/fundou/miniconda3/bin/sv_query`)
**Goal:** Bootstrap a real OpenTitan project for `sv_query`, freeze 5 real structural tasks with
ground truth, and record the onboarding problems a real user hits.

---

## 1. OpenTitan path / HEAD

| Item | Value |
|---|---|
| Source repo | `/Users/fundou/my_dv_proj/openrtl/opentitan` |
| Isolated worktree (used) | `/Users/fundou/.dsh/opencode-workers-lite/opentitan-pilot/workspace` |
| HEAD | `a82c4892e88253924b3f7af05ce7494232ab263a` |
| HEAD subject | `[doc] Update ILA debugging documentation` |
| HEAD date | `Wed Nov 27 16:25:51 2024 +0100` |
| Tracked-file modifications | **none** (`git diff --stat HEAD` empty; only untracked `AGENTS.md`) |

The worktree is a real `git worktree` of the source repo
(`.git` → `gitdir: /Users/fundou/my_dv_proj/openrtl/opentitan/.git/worktrees/workspace`),
and both report the same HEAD. **No OpenTitan tracked file and no file under
`/Users/fundou/my_dv_proj/sv_query` was modified.**

## 2. Block choice

**Chosen: `hw/ip/uart`, top module `uart`.**

The task preferred `hw/ip/uart` and it turned out to be *feasible*, so no fallback was needed.

Rationale:
- `hw/ip/uart/uart.core` declares a small, explicit `files_rtl` dependency list
  (`lowrisc:prim:all`, `lowrisc:ip:tlul`, `top_pkg`, `top_racl_pkg`) and a single toplevel `uart`.
- The real dependency closure resolves to **60 files / ~4.8k graph nodes**, which is a
  tractable snapshot size.
- The block has real structural interest for the 5 task kinds: a register file
  (`uart_reg_top`), a datapath (`uart_core` with FIFOs, a synchronizer, a majority filter and
  shift registers), a TL-UL bus interface, and an alert path.

Sizing note: the *nominal* dependency list (`lowrisc:prim:all` = 162 prim `.sv` files plus
29 tlul files) does **not** elaborate on its own — see §7. The working filelist is the
**top-reachable closure**, hand-pruned to 60 files.

## 3. Filelist — `/tmp/opentitan_svq/opentitan.f`

64 non-comment lines: 4 `+incdir+` directives + 60 source files.

Derivation: `hw/ip/uart/uart.core` `files_rtl.depend` →
`lowrisc:virtual_constants:top_pkg`, `lowrisc:prim:all`, `lowrisc:ip:tlul`,
`lowrisc:virtual_constants:top_racl_pkg`, plus the tech-mapping
`hw/ip/prim_generic/prim_generic.core` (which supplies `prim_buf` / `prim_flop` /
`prim_flop_2sync` / `prim_clock_gating` / `prim_xnor2` / `prim_xor2` / `prim_and2` / `prim_const`).

| Group | Files |
|---|---|
| prim macro/header units | `prim_assert.sv`, `prim_assert_{standard,dummy,yosys}_macros.svh`, `prim_assert_sec_cm.svh`, `prim_flop_macros.sv`, `prim_fifo_assert.svh` (7) |
| prim packages | `prim_alert_pkg.sv`, `prim_mubi_pkg.sv`, `prim_subreg_pkg.sv`, `prim_util_pkg.sv` (4) |
| prim cells | `prim_alert_{sender,receiver,to_diff}.sv`, `prim_clock_gating_sync.sv`, `prim_diff_{decode,encode,to_alert}.sv`, `prim_edge_detector.sv`, `prim_fifo_sync{,_cnt}.sv`, `prim_intr_hw.sv`, `prim_onehot_{check,enc}.sv`, `prim_reg_we_check.sv`, `prim_sec_anchor_{buf,flop}.sv`, `prim_subreg{,_ext,_shadow,_arb}.sv` (17) |
| prim secded (TL-UL integrity) | `prim_secded_pkg.sv`, `prim_secded_inv_{39_32,64_57}_{dec,enc}.sv` (5) |
| prim_generic (tech-independent cells) | `prim_buf.sv`, `prim_flop.sv`, `prim_flop_2sync.sv`, `prim_clock_gating.sv`, `prim_xnor2.sv`, `prim_xor2.sv`, `prim_and2.sv`, `prim_const.sv`, `prim_const_sec.sv` (9) |
| tlul | `tlul_pkg.sv`, `tlul_adapter_reg.sv`, `tlul_cmd_intg_chk.sv`, `tlul_rsp_intg_gen.sv`, `tlul_data_integ_{dec,enc}.sv`, `tlul_err.sv` (7) |
| uart | `uart_reg_pkg.sv`, `uart_reg_top.sv`, `uart_rx.sv`, `uart_tx.sv`, `uart_core.sv`, `uart.sv` (6) |
| top virtual constants | `hw/top_earlgrey/rtl/top_pkg.sv`, `hw/top_earlgrey/rtl/autogen/top_racl_pkg.sv` (2) |

`+incdir+` entries: `hw/ip/prim/rtl`, `hw/ip/prim_generic/rtl`, `hw/ip/tlul/rtl`, `hw/ip/uart/rtl`
(needed because the RTL uses `` `include "prim_assert.sv" `` etc.).

## 4. Snapshot

```bash
export SVQ_SNAPSHOT_DIR=/tmp/opentitan_svq/snapshots
cd /Users/fundou/.dsh/opencode-workers-lite/opentitan-pilot/workspace
python3 /Users/fundou/my_dv_proj/sv_query/tools/agent/setup_snapshot.py \
  --path . --tag opentitan_uart \
  --filelist /tmp/opentitan_svq/opentitan.f \
  --snapshot-dir /tmp/opentitan_svq/snapshots \
  --source-root . --json
```

Result:
```json
{"ok": true, "tag": "opentitan_uart", "path": "/tmp/opentitan_svq/snapshots/opentitan_uart.json",
 "files": 60, "node_count": 4804, "edge_count": 8507, "elaboration_errors": 0, "failed_files": []}
```
Note a **+1 discrepancy on nodes**: `snapshot save` reports `node_count=4804`, while
`snapshot list <tag> --json` and the snapshot file itself report **4803**
(the stored `nodes` array has 4803 entries). `edge_count` agrees at 8507 everywhere.
The canonical numbers below (4803 / 8507) are the ones `snapshot list` reports and the ones
the arrays actually contain.

| Stat | Value |
|---|---|
| Files compiled | 60 |
| Nodes | **4803** |
| Edges | **8507** |
| Elaboration errors | **0** |
| Failed files | **0** |
| `strict_mode` | `true` |
| Snapshot size | 5,343,985 bytes (5.1 MB) |
| Build time (cold, fresh `SVQ_CACHE_DIR`) | **7.57 s** (user 7.41 s / sys 0.15 s) |
| Build time (warm cache) | 7.80 s (the snapshot re-serialises regardless of the AST cache) |
| Single query from snapshot | ~0.30 s |
| `git_commit` stored in snapshot | `""` (empty — see §7, issue 6) |

### Node / edge census

| Node kind | Count | | Edge kind | Count |
|---|---|---|---|---|
| SIGNAL | 2852 | | BIT_SELECT | 3381 |
| PORT_IN | 962 | | DRIVER | 2928 |
| PORT_OUT | 496 | | CONNECTION | 1154 |
| INSTANTIATED_MODULE | 206 | | CLOCK | 320 |
| REG | 148 | | RESET | 318 |
| OP_TERNARY | 117 | | BRANCH_CONDITION | 120 |
| CONST | 21 | | BRANCH_RESULT | 117 |
| GENERATE_BLOCK | 1 | | BRANCH_FALSE | 89 |
| | | | BRANCH_TRUE | 80 |

Also stored: `dynamic_nodes=1`, `function_nodes=30`, `expr_trees` (11 entries),
`const_map`, `func_info` (5 entries).

### Elaboration status

Elaboration **succeeds**. 173 warnings/notes are emitted, all benign lint categories
(`EmptyOutputPortConn` ×~130 — mostly the reggen'd `.intg_err_o(alerts[0])`-style
deliberate discards, `CaseRedundantDefault`, `UselessCast`, `LogicalOpParentheses`,
`IntBoolConv`). **No `error:` lines.**

## 5. Frozen tasks — `/tmp/opentitan_svq/opentitan_tasks.json`

All 5 tasks use real OpenTitan UART signals, resolved against the `opentitan_uart` snapshot.
Ground truth = source inspection + `sv_query` CLI; every command is recorded.

| id | kind | Question subject | Expected result |
|---|---|---|---|
| **T1** | `direct_neighbors` | `uart.u_reg.intr_test_qe` (the INTR_TEST write-enable gate) + an **empty-side** case on `uart.u_reg.reg2hw.intr_test.tx_watermark.qe` | 1 driver (`intr_test_flds_we`), 9 loads (the 9 `reg2hw.intr_test.<field>.qe`); empty side has **2 drivers, 0 loads** |
| **T2** | `directed_path` | chip RX pin → RX shift register: `uart.cio_rx_i` → `uart.uart_core.rx_val_q` | **found**, 18 hops, 48 candidates; path through `sync_rx` (2-stage sync) → `rx_sync_q1/q2` → `rx_in_maj` → `rx_in_mx` → `rx_in` → `rx_val_q` |
| **T3** | `evidence_file_line` | Where is `rx_val_q` updated? | `hw/ip/uart/rtl/uart_core.sv` **line 306** (`source_text` = `"if (!rst_ni)            rx_val_q <= 16'h0;"`), enclosing `always_ff` spans **lines 305-308**; driver edge `rx_in → rx_val_q` at **line 308** |
| **T4** | `verify_claim` | (A) `intg_err_o` driven by the sticky `err_q`; (B) `intg_err_o` feeds the fatal-alert request; (C) negative control: can `rx_in` drive `tx_out_q`? | A **verified**, B **verified**, C **contradicted** (`rx_in is not in fanin(tx_out_q, depth=1)`) |
| **T5** | `unknown_no_path_missing_signal` | (a) path from a non-existent `uart_core.nonexistent_sig` to `rx_val_q`; (b) directed path `uart.cio_tx_o` → `uart.uart_core.tx_out_q` | (a) **unknown** (`endpoint unresolved`; CLI: `ok=false`, `signal id not found in graph`); (b) **contradicted** (`forward=False, reverse=True`) — the correct direction is `tx_out_q → tx → cio_tx_o` (3 hops, verified) |

### Verification run (all pass)

Reproduce with `bash /tmp/opentitan_svq/verify_tasks.sh` (raw command transcript).

```
PASS T1 drivers(intr_test_qe) == frozen list
PASS T1 loads(intr_test_qe) == frozen list :: 9 ids
PASS T1 drivers(reg2hw.intr_test.tx_watermark.qe) :: got=['uart.u_reg.intr_test_qe','uart.u_reg.intr_test_flds_we']
PASS T1 loads(reg2hw.intr_test.tx_watermark.qe) :: got=[]
PASS T2 paths found
PASS T2 hop_count==18 :: 18
PASS T2 path matches frozen
PASS T2 verify claim verified
PASS T3 file :: {'file': 'uart_core.sv', 'line_start': 306, 'line_end': 306, 'column': 3}
PASS T3 line 306
PASS T3 text :: "if (!rst_ni)            rx_val_q <= 16'h0;"
PASS T3 enclosing_always 305-308
PASS T3 subgraph evidence lines 307,308 :: [307, 308]
PASS T4 claim {"type":"driver","signal":"uart.u_reg.in -> verified :: verified
PASS T4 claim {"type":"path","from":"uart.u_reg.intg_err_e -> verified :: verified
PASS T4 claim {"type":"driver","signal":"uart.uart_cor -> contradicted :: contradicted
PASS T5 missing-signal status=unknown :: unknown
PASS T5 unknown reason mentions unresolved :: endpoint unresolved: 'uart.uart_core.nonexistent_sig'/'uart.uart_core.rx_val_q'
PASS T5 paths CLI ok=false
PASS T5 paths CLI error msg :: signal id not found in graph
PASS T5 reverse claim contradicted :: contradicted
PASS T5 forward direction found 3 hops :: 3
TOTAL FAILURES: 0
```

Source confirmation for the frozen answers:
- `hw/ip/uart/rtl/uart_reg_top.sv:727-729` — `logic intr_test_qe; logic [8:0] intr_test_flds_we;
  assign intr_test_qe = &intr_test_flds_we;` then `assign reg2hw.intr_test.<field>.qe = intr_test_qe;`
  for all 9 fields (lines 744, 760, 776, 792, 808, 824, 840, 856, 872).
- `hw/ip/uart/rtl/uart_core.sv:235-243, 249-257, 259-262, 264-266, 305-308` — the T2/T3 chain.
- `hw/ip/uart/rtl/uart_reg_top.sv:76-87` — `err_q` sticky flop → `assign intg_err_o = err_q | intg_err | reg_we_err;` (T4-A).
- `hw/ip/uart/rtl/uart.sv:57-72` — `uart_reg_top u_reg (... .intg_err_o (alerts[0]) )` (T4-B).

## 6. `sv_query` command surface for this project

`--from-snapshot` support (the practical split a user hits):

| Supports `--from-snapshot` | Requires `--file`/`--filelist` (re-parses SV) |
|---|---|
| `drivers`, `loads`, `paths`, `verify claim`, `trace evidence`, `trace impact` | `verify consistency`, `verify structural`, `trace profile`, `trace lookup`, `trace manifest`, `controlflow analyze`, `dataflow analyze`, `graph nodes`, `graph edges`, `graph subgraph`, `hierarchy`, `instances`, `scope`, `connections`, `ports`, `params`, `stats`, `search` |

## 7. Exact issues encountered (what a real user hits)

### Issue 1 — The declared dependency list does **not** elaborate (missing packages)

`snapshot save --filelist <all prim + tlul + uart>` fails hard:

```
prim_lc_sync.sv:33:14: error: unknown class or package 'lc_ctrl_pkg'
prim_pulse_sync.sv:75:3: error: unknown module 'prim_flop_2sync'
prim_sec_anchor_buf.sv:14:3: error: unknown module 'prim_buf'
prim_sec_anchor_flop.sv:17:3: error: unknown module 'prim_flop'
```

`lowrisc:prim:all` pulls in the whole prim library, including lifecycle-control and
crypto prims that need `lc_ctrl_pkg`, plus the *technology-specific* `prim_buf`/`prim_flop`
that live in `hw/ip/prim_{generic,xilinx,asap7}` (a **target-dependent mapping**, not a
plain file list). A naive "all prim files" filelist cannot work.

**Fix:** build the top-reachable closure. `sv_query filelist prune --filelist <full> --top uart`
does this automatically (207 → 56 files) but it is *conservative* and still keeps
`prim_util_memload.svh` / `prim_secded_inc.svh` / `prim_util_get_scramble_params.svh`,
which are **include-only macro helpers, not standalone compile units**:

```
prim_util_memload.svh:48:37: error: use of undeclared identifier 'Depth'
prim_util_memload.svh:51:24: error: use of undeclared identifier 'mem'
```

These must be removed by hand (or supplied via `+incdir+` and never listed).

**What a user hits:** "the block's `.core` file lists dependencies I can't turn into a
filelist with `find`/`ls`". The mapping layer (`hw/ip/prim_generic/prim_generic.core`
`mapping:` block) is the real answer, and it is not machine-readable by a generic tool.

### Issue 2 — Technology-dependent prim cells must be resolved manually

`prim_buf`, `prim_flop`, `prim_flop_2sync` do not exist in `hw/ip/prim/rtl/`. They live in
**three** technology variants (`prim_generic`, `prim_xilinx`, `prim_asap7`), and OpenTitan's
build picks one via the `prim_generic.core` mapping. The tool has no notion of this, so
the user must pick `prim_generic` (the portable choice) and add
`hw/ip/prim_generic/rtl/{prim_buf,prim_flop,prim_flop_2sync,prim_clock_gating,prim_xnor2,prim_xor2,prim_and2,prim_const,prim_const_sec}.sv`.

**What a user hits:** 4 rounds of "unknown module 'prim_flop'" until you realise the
prim library is split by technology and you must mirror OpenTitan's core-file mapping by hand.

### Issue 3 — `+incdir+` is required and not optional

Every OpenTitan RTL file starts with `` `include "prim_assert.sv" `` (and `prim_flop_macros.sv`,
`prim_fifo_assert.svh` are pulled in from inside it). Without `+incdir+hw/ip/prim/rtl` etc.
the macro expansion fails with `TooFewArguments`. The tool's `--preprocess` (default on) handles
cross-file `MACRO` expansion, but the include *search path* still has to be supplied.

### Issue 4 — `top_pkg` / `top_racl_pkg` are *top-level* files, not block files

`uart.sv` and `uart_reg_top.sv` reference `top_pkg::TL_AW` and `top_racl_pkg::racl_policy_sel_t`,
but those packages live under `hw/top_earlgrey/rtl/` (and `.../rtl/autogen/`), i.e. **outside**
`hw/ip/uart`. This is the `lowrisc:virtual_constants:*` dependency in `uart.core` — a virtual
fileset with no files of its own.

The tool auto-injects the imports (`[auto-import] tlul_pkg: injected imports for
['prim_mubi_pkg', 'prim_secded_pkg', 'top_pkg']`), which helps, but the packages still have to
be **compiled** — so `hw/top_earlgrey/rtl/top_pkg.sv` and
`hw/top_earlgrey/rtl/autogen/top_racl_pkg.sv` must be listed explicitly.

### Issue 5 — Snapshot mode loses source evidence (the biggest functional gap)

The snapshot stores the **graph**, not the **source text**. Queries run with
`--from-snapshot` return `file: null, line: null` for every driver/load, and
`trace evidence --from-snapshot` returns:

```
source_location None | source_text '' | is_verified False
```

So **T3 (file/line evidence) cannot be answered from the snapshot at all** — it needs
`--filelist` (re-parse, ~0.3 s warm thanks to the AST cache) or `graph subgraph --evidence`.
The `--evidence` flag on `drivers`/`loads` is a no-op when loading from a snapshot.

**What a user hits:** "I built a snapshot to make queries fast, and then I can't answer
'where is this assigned?' from it." The snapshot is a *graph* snapshot, not a *source* snapshot.

### Issue 6 — `git_commit` is empty in the snapshot

`opentitan_uart.json` has `"git_commit": ""` even though the worktree is a real git
worktree at a known HEAD. `snapshot save` has a `--git` flag for this, but
`setup_snapshot.py` does **not** pass it. A user who wants reproducible snapshots must add
`--git` themselves; otherwise the snapshot cannot be tied back to a commit.

### Issue 7 — `paths` and `drivers` disagree through ternary expressions

`uart_core.sv:217` — `assign tx = line_loopback ? rx : tx_out_q ;`

| Query | Result |
|---|---|
| `paths --directed tx_out_q → cio_tx_o` | **found**, 3 hops: `tx_out_q → tx.ternary_line_loopback → tx → cio_tx_o` |
| `drivers cio_tx_o` | `tx_out_q` **absent** from the fanin list |

The `drivers` fanin traversal does not follow the arms of a ternary into the fanin of the
enclosing signal; `paths` does (via the `OP_TERNARY` node). The same asymmetry makes
`verify claim --claim '{"type":"driver","signal":"uart.cio_tx_o","driver":"uart.uart_core.tx_out_q"}'`
return **contradicted**, even though `paths` says the directed path exists.

**What a user hits:** two tools in the same suite disagree about the same design fact.
Both are "correct" under their own definitions, but the answer depends on which command
you happen to reach for. (This is why T5 uses the *reverse* direction, where both agree
it is false.)

### Issue 8 — `drivers` fanin stops at module-port boundaries

`drivers uart.uart_core.rx_sync` returns exactly **1** driver
(`uart.uart_core.sync_rx.q_o`, the output port of the `prim_flop_2sync` instance) and does
not continue into `prim_flop_2sync`'s internals — even with `--depth 3` and
`truncated_by_depth=false`. `paths`, by contrast, traverses the full 10-hop chain
`rx → sync_rx.d_i → … → sync_rx.q_o → rx_sync`.

**What a user hits:** "the fanin looks truncated but the tool says it isn't truncated."

### Issue 9 — Bit-level queries are coarse-only on this design

`paths --bits 0,0` on `reg2hw.intr_test.tx_watermark.qe` → `found=false`,
`coarse_fallback=true`. `verify claim --claim '{"type":"bit",...}'` → `unknown`,
`reason='bit node missing; only parent bus exists'`. The snapshot's `BIT_SELECT` edges
(3381 of them) are not exposed as addressable bit nodes for these packed-struct fields.

### Issue 10 — `verify consistency` reports 487 violations on a clean design

```
verified=false  total_violations=487
  reciprocity : fail  (checked 141, skipped 59,  5 violations)
  bit_mapping : fail  (checked 1833,             482 violations)
  connection  : pass  (checked 1374,               0 violations)
```

Violations by kind: `width_mismatch` ×476, `id_parent_mismatch` ×6,
`fanin_not_reciprocal` ×5.

The 482 `bit_mapping` violations are concentrated on **packed struct fields whose child is
wider than the parent** — e.g.
`uart.u_reg.reg2hw.intr_test.rx_break_err.qe` reports `node_bits=2, parent_bits=1`.
This is the reggen packed-struct convention (`{q, qe}` packed into one bit) being
mis-measured, plus the 2-bit diff-encoded alert fields
(`alert_rx_i.ack_p/ack_n/ping_p/ping_n`). The 5 `fanin_not_reciprocal` violations are all in
`prim_alert_to_diff`, a module that is in the closure only because `prim_alert_sender`
references it.

**Impact on the frozen tasks:** T1 touches `reg2hw.intr_test.*.qe`, which *is* in the
violation list — but only at the **bit-node** level; the **struct-field-level** driver/load
lists that T1 asks about are clean, and the `verify claim` results are unaffected.

**What a user hits:** running `verify consistency` on a *correct* OpenTitan block produces
hundreds of "violations". A user cannot distinguish tool artifacts from real bugs without
knowing the reggen packing convention. This is a real onboarding trap.

### Issue 11 — Minor CLI friction

- `snapshot list` has **no** `--pretty` flag (only `--json`). `snapshot list <tag> --json`
  does report `node_count`/`edge_count` (4803 / 8507), but `snapshot list` (no tag) returns a
  *list* of every snapshot and includes the whole `files` array per entry — noisy.
- `stats` requires `--file`/`--filelist` and does not read a snapshot.
- `hierarchy`, `instances`, `scope`, `connections`, `ports`, `params`, `class` all require
  `--file`/`--filelist` and have **no** `--from-snapshot` — so the "canonical entry points"
  advertised in `capabilities` cannot be used in snapshot mode.
- `dataflow analyze` has **no** `--from-snapshot` even though it is the richer path command
  (it reports `primary_latency_cycles`, `timing_risk`, `all_conditions`).
- `verify claim` needs the JSON key **`type`**, not `kind` (the docs table says "type" but the
  error message only surfaces as `unknown claim type: None (driver|path|connection|bit)`).
- `paths` has a **9-vs-18-hop ambiguity** for the T2 pair: without `--canonical`,
  `paths --directed` returns a **9-hop** path (the "first" simple path found), while
  `paths --directed --canonical` returns the **18-hop** path (policy
  `max_nodes_then_lexicographic`). `paths --all` shows **48** distinct directed paths for the
  same pair, with hop counts spread from 10 to 19 (`{10:1, 11:3, 12:4, 13:5, 14:7, 15:8,
  16:8, 17:7, 18:4, 19:1}`), `truncated=false`. The 9-hop and 18-hop variants differ in
  whether wrapper/ternary ports are collapsed or retained — exactly the ambiguity the
  `--canonical` flag was added to remove.
  **A harness that omits `--canonical` will silently grade against a different answer.**

## 8. Remaining risks

1. **T3 is not snapshot-only.** A benchmark harness that assumes "one snapshot, then all
   questions from `--from-snapshot`" would fail T3 (no file/line). The harness must keep
   `--filelist` available for evidence questions. Mitigation: keep both the snapshot *and*
   the filelist in the task record, and state per task which mode is required.
2. **T1/T4/T5 sit near known tool artifacts.** T1's `.qe` fields are in the
   `verify consistency` `bit_mapping` violation set, and T4-A/T4-B involve `intg_err_o`
   / `alerts[0]`, which are adjacent to the alert-interface artifacts. The *field-level*
   answers are stable, but a harness that runs `verify consistency` as a gate would see
   487 pre-existing violations on this design. Recommendation: treat `verify consistency`
   as advisory on OpenTitan, not as a pass/fail gate.
3. **Task 2's 18-hop path is one of 48 candidates, and `--canonical` is mandatory.**
   `paths --all` enumerates 48 directed paths for `cio_rx_i → rx_val_q` (10-19 hops).
   `--canonical` deterministically selects the 18-hop max-node path, but **without
   `--canonical` the same command returns the 9-hop path**. The frozen answer is the
   canonical one; a harness must pass `--canonical` or it will grade against a different
   (also valid) path.
4. **The filelist is hand-curated.** It is correct for `hw/ip/uart` at this HEAD, but it is
   *not* machine-derived. A different block, or a rebase that changes `uart.core`'s `depend`
   list, would need the same manual work. `filelist prune` gets close (56/60) but keeps
   include-only `.svh` files that then fail to elaborate.
5. **`top_pkg` / `top_racl_pkg` are `hw/top_earlgrey`-specific.** The UART RTL is shared
   across top-levels (`top_earlgrey`, `top_darjeeling`, `top_englishbreakfast`); this
   snapshot uses the `earlgrey` variants. A different top may have different `TL_AW`/`TL_DW`
   and therefore a different graph.
6. **No git provenance in the snapshot** (`git_commit=""`). If the benchmark moves the
   worktree, the snapshot cannot be validated against a commit.
7. **Snapshot size** is 5.1 MB for a 60-file block. Scaling to `hw/top_earlgrey` would be
   far larger and the 7.6 s build would grow; the filelist+prune approach may not scale to
   full-chip.

## 9. Artifact index

| Path | Contents |
|---|---|
| `/tmp/opentitan_svq/opentitan.f` | 64-line filelist (60 source files + 4 `+incdir+`) |
| `/tmp/opentitan_svq/snapshots/opentitan_uart.json` | The snapshot (4803 nodes / 8507 edges, 0 elaboration errors, 5.1 MB) |
| `/tmp/opentitan_svq/snapshots/opentitan_uart.meta.json` | Tag / snapshot path / source_root / filelist / query_bin (written by `setup_snapshot.py`) |
| `/tmp/opentitan_svq/snapshots/opentitan_uart.env.sh` | `export SVQ_SNAPSHOT_DIR=… SVQ_SOURCE_ROOT=… SVQ_QUERY_BIN=…` |
| `/tmp/opentitan_svq/opentitan_tasks.json` | The 5 frozen tasks (`meta` + `tasks[]`), each with `id, block, snapshot, source_root, kind, question, expected, ground_truth_command` |
| `/tmp/opentitan_svq/verify_tasks.sh` | Re-runnable ground-truth transcript script (all commands + result extraction) |
| `/tmp/opentitan_svq/REPORT.md` | This report |

### Reproduce end-to-end

```bash
export SVQ_SNAPSHOT_DIR=/tmp/opentitan_svq/snapshots
cd /Users/fundou/.dsh/opencode-workers-lite/opentitan-pilot/workspace

# rebuild the snapshot (~7.6 s)
python3 /Users/fundou/my_dv_proj/sv_query/tools/agent/setup_snapshot.py \
  --path . --tag opentitan_uart --filelist /tmp/opentitan_svq/opentitan.f \
  --snapshot-dir "$SVQ_SNAPSHOT_DIR" --source-root . --json

# re-verify all 5 tasks
bash /tmp/opentitan_svq/verify_tasks.sh
```
