# P134 — Real-Use Field Pilot: sv_query on OpenTitan UART/I2C

**Date:** 2026-11-09 · **Mode:** independent verification-engineer field pilot (not a unit test)
**Workspace:** `/Users/fundou/.dsh/opencode-workers-lite/opentitan-pilot/workspace` @ `a82c4892`
**Snapshots:** I2C `/tmp/opentitan_svq_i2c/snapshots/opentitan_i2c`, UART `/tmp/opentitan_svq/snapshots/opentitan_uart`
**Artifacts:** `/tmp/p134_real_pilot/{REPORT.md, commands.log, i2c_core_arch.json, i2c_core_arch.svg, i2c_core_arch.dot, i2c_dv.f}`
Nothing was fixed; no code/tasks/snapshots/tracked files modified.

---

## Scenario 1 — RANDOM → CONSTRAINT → RTL

**Engineer question:** *"The I2C agent randomises `rcont`, `read` and `stop` together and I want to know exactly which constraint block shapes them, which random variables it ties together, and where the `nakok` flag I also randomise actually lands in the RTL."*

**Commands** (cwd = OpenTitan root; `SVQ_SNAPSHOT_DIR=/tmp/opentitan_svq_i2c/snapshots`):
`sv_query class i2c_item --filelist …/i2c_dv.f --json` ·
`sv_query trace constraints --filelist … i2c_item.rcont --json` ·
`sv_query trace constraint-neighborhood --filelist … i2c_item.rcont --json` ·
`sv_query paths --from-snapshot opentitan_i2c … --directed --canonical --json`

**Raw facts.**
- `class i2c_item` → `member_count=34`; Rand members: `fbyte` (bit[7:0]), `nakok`, `rcont`, `read`, `stop`, `start` (all bit).
- `trace constraints i2c_item.rcont` → one block `i2c_item.rcont_c`, `vars=[rcont, stop]`, `conditions=[i2c_item.read]`, `rand_vars=[rcont, stop]`.
- `constraint-neighborhood` → 3 nodes / 3 relations: `{rcont, read, stop}` all in block `rcont_c`; relations rcont→read, rcont→stop, read→stop.
- Source cross-check (`hw/dv/sv/i2c_agent/i2c_item.sv:61-70`): `solve read, stop before rcont; if (read) rcont == ~stop; else rcont dist {1:/1, 0:/2};` — the tool **captured the conditional guard correctly**, but does **not** surface the `solve…before` ordering or the `dist` weights.
- RTL leg: `i2c.i2c_core.reg2hw.fdata.nakok.q` → `i2c.i2c_core.fmt_fifo_wdata[12]` → `u_fifos.fmt_fifo_wdata_i[12]` → `u_fifos.fmt_fifo_wdata[12]` (3 hops). Source: `i2c_core.sv:348 assign fmt_fifo_wdata[12] = reg2hw.fdata.nakok.q;`

**Dead end.** The *semantically complete* question — does `nakok` reach the controller FSM? — is **not answerable**: `paths nakok.q → fmt_flag_nak_ok` → `found=False`. The chain dies at the FIFO read side (`fmt_flag_nak_ok` is driven by `fmt_fifo_rdata[12]` under `fmt_fifo_rvalid`, and no path exists back from `nakok.q`). `drivers(i2c.i2c_core.fmt_fifo_wdata)` returns **count=0** while `loads(reg2hw.fdata.nakok.q)` returns 5 — the *parent bus is orphaned* and only the bit-select `fmt_fifo_wdata[12]` carries an edge. Resolving this required **reading the RTL** to see the real path is `nakok → fmt_fifo_wdata[12] → (FIFO) → fmt_fifo_rdata[12] → fmt_flag_nak_ok → FSM`.

**Time / calls:** ~0.65 s for the three TB-side commands; ~0.3 s per snapshot query. ~10 CLI calls + 2 source greps.

**Issues:** (a) parent-bus orphaning / bit-select-only edges — **friction**; (b) FIFO/SRAM read-side not connected to write-side — **blocker** for any "random field → RTL effect" question that crosses a FIFO; (c) `solve…before` and `dist` weights not reported — **nice-to-have**; (d) no command joins a TB random field to the RTL snapshot in one shot — **friction**.

---

## Scenario 2 — VERIFY (incl. unknown)

**Engineer question:** *"Is the NAK-OK flag really what stops the controller FSM from halting on a NACK? And separately — I've been handed a signal name that doesn't seem to exist; can the tool tell me that rather than inventing something?"*

**Commands:** `sv_query verify claim --from-snapshot opentitan_i2c --claim '<json>' --json` ×4.

**Raw facts — all three statuses preserved, none degraded to an empty success:**

| claim | status | reason |
|---|---|---|
| path `fmt_fifo_rdata[12]` → `u_i2c_controller_fsm.fmt_flag_nak_ok_i` | **verified** | `''` (evidence: `{kind: reachable, bidirectional: false}`) |
| driver `reg2hw.fdata.nakok.q` → `fmt_fifo_wdata` | **contradicted** | `not in fanin(fmt_fifo_wdata, depth=1)` + counterevidence `{kind: fanin, actual_drivers: []}` |
| driver `reg2hw.fdata.nakok.q` → `fmt_fifo_wdata_typo` | **unknown** | `signal 'i2c.i2c_core.fmt_fifo_wdata_typo' not_found` |
| path `u_i2c_controller_fsm.fmt_flag_nak_ok_i` → `reg2hw.fdata.nakok.q` | **contradicted** | `path check failed (forward=False, reverse=True)` |

**Assessment.** This is the **strongest** part of the tool. The three statuses are cleanly separated, `unknown` is reserved for *unresolvable endpoints* rather than conflated with `contradicted`, and the `contradicted` case even returns actionable counterevidence (`actual_drivers: []`) that points straight at the orphan-bus bug from Scenario 1. The reverse-direction claim is correctly `contradicted` (not "unknown"), and the reason string names the asymmetry.

**Time / calls:** 1.51 s for all 4 claims; 4 CLI calls.

**Issues:** none material. Minor: `unknown` vs `contradicted` is a distinction a user must know about — the `reason` string carries it, but no explicit `unresolved_endpoint: true` flag is emitted — **nice-to-have**.

---

## Scenario 3 — ARCHITECTURE / CONNECTION

**Engineer question:** *"What are the sub-blocks inside the I2C core, and how do the bus monitor and the two FSMs talk to each other? I need the actual nets and port names."*

**Commands:** `sv_query architecture graph --filelist /tmp/opentitan_svq_i2c/opentitan_i2c.f --module i2c.i2c_core --json` (16.3 s) and the same with `--svg` / `--dot`.

**Raw facts.** `stats: {instances: 9, connections: 72, boundaries: 241}`.
Instances: `i2c.i2c_core` (i2c_core) → `u_fifos` (i2c_fifos), `u_i2c_bus_monitor` (i2c_bus_monitor), `u_i2c_controller_fsm` (i2c_controller_fsm), `u_i2c_target_fsm` (i2c_target_fsm); under `u_fifos`: four `i2c_fifo_sync_sram_adapter` (`u_{acq,fmt,rx,tx}_fifo_sram_adapter`).

Two child connections with exact nets/ports:
- `u_i2c_bus_monitor` → `u_i2c_controller_fsm` (6): `bus_free_o→bus_free_i`; `controller_enable_i→host_enable_i`; `scl_i→scl_i`; `sda_i→sda_i`; `thd_dat_i→thd_dat_i`; and `bus_active_timeout_i→stretch_timeout_i`.
- `u_i2c_controller_fsm` → `u_i2c_target_fsm` (4): `scl_i→scl_i`; `sda_i→sda_i`; `t_r_i→t_r_i`; `thd_dat_i→thd_dat_i`.

**Verified against source** (`hw/ip/i2c/rtl/i2c_core.sv:525-580`): `.stretch_timeout_i (bus_active_timeout)` — confirmed exactly. The apparent "port-name mismatch" is **correct behaviour**: the *net* is `bus_active_timeout` while the *port* is `stretch_timeout_i`. The tool is right and the source confirms it.

**Usability.** The graph is genuinely usable: JSON gives every edge as `{src, dst, net, src_port, dst_port, src_direction}`; the DOT is clean (`rankdir=LR`); the SVG renders 3320×1763 with all 66 element groups and instance names labelled. Boundaries (241) expose the top-level port surface (`i2c.cio_scl_i` ↔ `i2c.i2c_core.scl_i`).

**Time / calls:** 16.3 s per invocation (re-parses the whole filelist every time); 2–3 CLI calls.

**Issues:**
- **`--json` + `--svg` together silently produces no SVG** — the command returns `ok: true` and the JSON, but the file is not written. Verified by A/B: with `--json` → NO file; without `--json` → YES file. **Blocker** for any pipeline that wants both machine and graph output. The same likely applies to `--dot`.
- 16 s per call, and it re-parses even when only the SVG is wanted — **friction**.
- A misleading warning fires twice: `可能缺少文件: 实例 'u_chk' 的模块 'prim_secded_inv_64_57_dec' 没有找到端口定义` — but `prim_secded_inv_64_57_dec.sv` **is** in the filelist; the warning is a false positive about port definitions, not missing files. **friction** (misleads the user into re-adding files that are present).
- No `--from-snapshot` for `architecture graph`; it requires a filelist and re-parses — **friction** (the signal-graph commands do support snapshot mode).

---

## Issue list (severity ordered)

| # | Issue | Severity |
|---|---|---|
| 1 | `architecture graph --json --svg` silently skips the SVG while returning `ok:true` | **blocker** |
| 2 | FIFO/SRAM read side not connected to write side → "random field → RTL effect" unanswerable across a FIFO; parent bus orphaned (`drivers(fmt_fifo_wdata)`=0) | **blocker** |
| 3 | `architecture graph` emits a false "missing file / no port definition" warning for `prim_secded_inv_64_57_dec` which *is* in the filelist | friction |
| 4 | `architecture graph` re-parses the whole filelist every call (16 s) and has no `--from-snapshot` | friction |
| 5 | No single command joins a TB random field to the RTL snapshot; I had to hand-link `i2c_item.nakok` ↔ `reg2hw.fdata.nakok.q` via source | friction |
| 6 | Bit-select-only edges: `fmt_fifo_wdata[12]` carries the edge while parent `fmt_fifo_wdata` has no drivers | friction |
| 7 | `solve…before` / `dist` weights not reported by `trace constraints` | nice-to-have |
| 8 | `unknown` has no explicit machine-readable flag, only a `reason` string | nice-to-have |

## What worked well
`verify claim` status fidelity (verified / contradicted / unknown, with counterevidence) is production-quality and was the single most useful capability in this pilot. `trace constraint-neighborhood` gave the complete `{rcont, read, stop}` relation set in one call with correct conditional attribution. `architecture graph` produced a rich, source-verifiable connection set including the non-obvious `bus_active_timeout` → `stretch_timeout_i` port/net distinction.

## What did not
No snapshot-mode path exists across a FIFO, so the natural end-to-end question ("which random field lands where in the RTL, and what does it affect") stops at the FIFO boundary and required manual RTL reading. The `--json`+`--svg` interaction is a silent data-loss bug in the one command that produces a human-viewable artifact.
