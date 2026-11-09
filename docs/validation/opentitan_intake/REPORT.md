# OpenTitan → sv_query Task Intake (independent, DV-artifact derived)

**Date:** 2026-11-09
**OpenTitan source root:** `/Users/fundou/.dsh/opencode-workers-lite/opentitan-pilot/workspace`
**OpenTitan HEAD:** `a82c4892e88253924b3f7af05ce7494232ab263a` (`[doc] Update ILA debugging documentation`)
**Artifacts:** `/tmp/opentitan_intake/tasks.json`, `/tmp/opentitan_intake/REPORT.md`
**No tracked file was modified. No LLM/DSH agent was run.** All validation used the `sv_query` CLI plus direct source inspection.

---

## 1. Method and independence

The three tasks were authored **only** from OpenTitan DV/RTL artifacts. The existing
`tools/benchmark/*_tasks_*.json` files were deliberately **not** consulted as task sources; the
`/tmp/opentitan_svq*/snapshots` were used **only** to resolve canonical ID spellings and to
cross-check already-source-established answers.

Workflow per task:

1. Pick a DV verification intent from a testplan / sim_cfg entry.
2. Read the RTL + reggen package + register docs to determine what the answer *is*.
3. Write the answer and its canonical IDs from that source reading.
4. Only then, confirm with the `sv_query` CLI.

Because of step 3, the ground truth is **source-derived**, not tool-derived. This is the key
difference from the existing benchmark corpus, where every ground truth was produced by the tool
itself.

### Source artifacts read

| Artifact | Role |
|---|---|
| `hw/ip/uart/dv/uart_sim_cfg.hjson` | test list, `uvm_test_seq` names, `testplan:` pointer |
| `hw/ip/uart/data/uart_testplan.hjson` | 19 testpoints with per-feature verification intent (the primary intent source) |
| `hw/ip/uart/doc/registers.md` | CTRL.NF semantics ("3-tap repetition code") |
| `hw/ip/uart/doc/theory_of_operation.md` | RX/TX behaviour context |
| `hw/ip/uart/doc/checklist.md` | read; governance only (see §5) |
| `hw/ip/uart/rtl/uart_core.sv`, `uart_rx.sv` | RTL ground truth |
| `hw/ip/i2c/dv/i2c_sim_cfg.hjson` | test list |
| `hw/ip/i2c/data/i2c_testplan.hjson` | 30+ testpoints with intent |
| `hw/ip/i2c/doc/checklist.md` | read; governance only |
| `hw/ip/i2c/rtl/i2c_core.sv`, `i2c_reg_pkg.sv` | RTL + reggen ground truth |

### Coverage of DV artifacts

| Artifact class | Used? | Tasks |
|---|---|---|
| UART testplan testpoints (19) | 2 of 19 (`rx_noise_filter`, `sys_loopback`) | T1, T3 |
| I2C testplan testpoints (30+) | 3 of 30+ (`host_mode_halt_on_nak`, `multi_controller_arbitration_lost_interference`, `controller_mode_bus_timeout`) | T2 |
| UART/I2C `checklist.md` | 0 — governance-only, no per-feature intent (§5) | — |
| `doc/registers.md`, `doc/theory_of_operation.md` | yes, as corroborating spec | T1, T3 |
| reggen packages (`*_reg_pkg.sv`) | yes, as the authoritative field-list source | T2 |
| DV env / seq_lib | referenced for provenance only (not read for ground truth) | T1, T2, T3 |

---

## 2. Task T1 — `DV-UART-NOISEFILTER-DISCOVERY` (discovery)

**Intent source:** `hw/ip/uart/data/uart_testplan.hjson` testpoint `rx_noise_filter` (stage V2,
tests `["uart_noise_filter"]`); `hw/ip/uart/dv/uart_sim_cfg.hjson` entry `uart_noise_filter`.

**Original verification intent:** "Enable noise filter and drive many glitches. Each glitch doesn't
last less than 3 clocks. Ensure the noise will be filtered out and it doesn't affect next normal
transaction." To review this in RTL one must first identify *which control bit* switches the RX
datapath between the raw synchronized input and the 3-tap repetition-code majority filter, then
confirm that bit really reaches that mux.

**Question (user-style):** *"I'm debugging the OpenTitan UART's receive path. There's a bit in the
block's control register that switches the RX datapath between the raw synchronized input and a
3-tap repetition-code majority filter (the filter that rejects glitches shorter than three IP
clocks). Which register bit is that, what is its canonical signal id in the snapshot, and which
internal signal does that bit drive on its way to the mux? Please give me the exact canonical
ids."*

**Expected answer**

| item | value |
|---|---|
| register bit | `CTRL.NF` |
| canonical id | `uart.uart_core.reg2hw.ctrl.nf.q` |
| intermediate | `uart.uart_core.rxnf_enable` |
| mux output | `uart.uart_core.rx_in_mx` |
| majority filter output | `uart.uart_core.rx_in_maj` |
| mux select node | `uart.uart_core.rx_in_mx.ternary_rxnf_enable` |
| path | `reg2hw.ctrl.nf.q → rxnf_enable → rx_in_mx.ternary_rxnf_enable → rx_in_mx` (3 hops) |

**Ground truth from source (not the tool):**
- `uart_core.sv:79` — `assign rxnf_enable = reg2hw.ctrl.nf.q;`
- `uart_core.sv:259-261` — `assign rx_in_maj = (rx_sync & rx_sync_q1) | (rx_sync & rx_sync_q2) | (rx_sync_q1 & rx_sync_q2);` — the 3-tap repetition code.
- `uart_core.sv:262` — `assign rx_in_mx = rxnf_enable ? rx_in_maj : rx_sync;`
- `uart_core.sv:264-266` — `rx_in_mx` is the last term of the `rx_in` assignment.
- `doc/registers.md:174-177` — "CTRL . NF — RX noise filter enable. … RX line goes through the 3-tap repetition code. It ignores single IP clock period noise." — independent doc confirmation.

**requires_search: true** · **requires_verify: false**

**Ambiguity / caveat (important):** the *direct-driver* claim
`ctrl.nf.q → rx_in_mx` is **contradicted** by the tool, because a mux select is not a DRIVER edge.
The *path* claim is verified. The task therefore expects the agent to traverse to the mux through
`rxnf_enable` / the ternary node, and a grader must not accept the direct-driver framing.
This mirrors the known UART ternary/`paths`-vs-`drivers` asymmetry.

**Validation commands** (all confirmed):
```bash
sv_query loads    --from-snapshot opentitan_uart 'uart.uart_core.reg2hw.ctrl.nf.q' --json   # count=1 -> ['uart.uart_core.rxnf_enable']
sv_query drivers  --from-snapshot opentitan_uart 'uart.uart_core.rxnf_enable' --json         # count=1 -> ['uart.uart_core.reg2hw.ctrl.nf.q']
sv_query paths    --from-snapshot opentitan_uart 'uart.uart_core.reg2hw.ctrl.nf.q' 'uart.uart_core.rx_in_mx' --directed --canonical --json
                                                                                             # found=true hop_count=3
sv_query verify claim --from-snapshot opentitan_uart --claim '{"type":"driver","signal":"uart.uart_core.rx_in_mx","driver":"uart.uart_core.reg2hw.ctrl.nf.q"}' --json
                                                                                             # status=contradicted  (EXPECTED)
```

---

## 3. Task T2 — `DV-I2C-CONTROLLER-HALT-VERIFY` (verify / abstain)

**Intent source:** `hw/ip/i2c/data/i2c_testplan.hjson`:
- `host_mode_halt_on_nak` — "Upon halting in response to observing a NACK, the CONTROLLER_EVENTS.NACK bit is set, and the 'controller_halt' interrupt is asserted."
- `multi_controller_arbitration_lost_interference` — "The 'controller_halt' interrupt is asserted, and CONTROLLER_EVENTS.LOST_ARBITRATION is set."
- `controller_mode_bus_timeout` — "Upon the timeout, the controller is halted, and 'controller_halt' is asserted."

**Original verification intent:** several *distinct* controller-side events must each produce the
same observable effect (the `controller_halt` interrupt). The RTL implements this as an
OR-reduction of four CONTROLLER_EVENTS bits. A reviewer must establish **which** events can halt
the controller, and must be able to distinguish a real event from one that does not exist in the
register block.

**Question (user-style):** *"For the OpenTitan I2C, the controller can be halted and raise the
'controller_halt' interrupt. I need to know exactly which controller events can cause that halt,
so please list the individual event bits that feed it, and for each one tell me whether the design
really has that event driving the halt status. Also: TARGET_EVENTS has a bit called TX_PENDING —
can that one halt the controller as well? If the bit doesn't exist where I'd expect it, say so
rather than guessing."*

**Expected answer**

| event | canonical id | status |
|---|---|---|
| nack | `i2c.i2c_core.reg2hw.controller_events.nack.q` | **verified** |
| unhandled_nack_timeout | `i2c.i2c_core.reg2hw.controller_events.unhandled_nack_timeout.q` | **verified** |
| bus_timeout | `i2c.i2c_core.reg2hw.controller_events.bus_timeout.q` | **verified** |
| arbitration_lost | `i2c.i2c_core.reg2hw.controller_events.arbitration_lost.q` | **verified** |
| tx_pending probe | `i2c.i2c_core.reg2hw.controller_events.tx_pending.q` | **unknown** (`not_found`) |

Halt status signal: `i2c.i2c_core.status_controller_halt`; interrupt: `i2c.i2c_core.intr_controller_halt_o`.

**Ground truth from source (not the tool):**
- `i2c_core.sv:864-869` — `assign status_controller_halt = | { reg2hw.controller_events.nack.q, reg2hw.controller_events.unhandled_nack_timeout.q, reg2hw.controller_events.bus_timeout.q, reg2hw.controller_events.arbitration_lost.q };` — exactly four terms.
- `i2c_reg_pkg.sv:427-440` — `i2c_reg2hw_controller_events_reg_t` declares exactly those four fields (arbitration_lost :430, bus_timeout :433, unhandled_nack_timeout :436, nack :439).
- `i2c_reg_pkg.sv:442-452` — `i2c_reg2hw_target_events_reg_t` holds arbitration_lost, bus_timeout, **tx_pending** → `tx_pending` is a TARGET_EVENTS bit and has no place under `controller_events`.
- `i2c_core.sv:106-108` — `event_nak` / `event_unhandled_nak_timeout` / `event_controller_arbitration_lost` are the separate *event* signals (hw2reg direction), distinct from the sticky reg2hw bits the OR-reduction reads.

**requires_search: false** · **requires_verify: true**

**Ambiguity / caveat:** the abstain case is `unknown` (node not found), **not** `contradicted`.
A grader must accept `unknown` as the correct answer to the TX_PENDING probe — the correct
behaviour is to refuse to invent `controller_events.tx_pending.q`. Note also that
`arbitration_lost` and `bus_timeout` exist in *both* CONTROLLER_EVENTS and TARGET_EVENTS, so
"the event named arbitration_lost" is ambiguous unless the CONTROLLER_EVENTS context is fixed —
the question fixes it by asking about the controller-halt status.

**Validation commands** (all confirmed):
```bash
# 4 x verified
sv_query verify claim --from-snapshot opentitan_i2c --claim '{"type":"driver","signal":"i2c.i2c_core.status_controller_halt","driver":"i2c.i2c_core.reg2hw.controller_events.nack.q"}' --json
#   ... .unhandled_nack_timeout.q / .bus_timeout.q / .arbitration_lost.q
# abstain
sv_query verify claim --from-snapshot opentitan_i2c --claim '{"type":"driver","signal":"i2c.i2c_core.status_controller_halt","driver":"i2c.i2c_core.reg2hw.controller_events.tx_pending.q"}' --json
#   -> status=unknown, reason "driver 'i2c.i2c_core.reg2hw.controller_events.tx_pending.q' not_found"
sv_query drivers --from-snapshot opentitan_i2c 'i2c.i2c_core.status_controller_halt' --json   # count=4
sv_query loads   --from-snapshot opentitan_i2c 'i2c.i2c_core.status_controller_halt' --json   # count=7, incl. intr_controller_halt_o
```

---

## 4. Task T3 — `DV-UART-SYSLOOPBACK-PATH` (path from a real DV check)

**Intent source:** `hw/ip/uart/data/uart_testplan.hjson` testpoint `sys_loopback` — "Enable system
loopback, then drive uart TX and data will be loopbacked through RX. After loopback is done,
uart.RDATA will be equal to the data programmed to uart.WDATA"; corroborated by the sibling
testpoint `line_loopback` — "There is not synchronizer register between uart_rx and uart_tx during
line loopback".

**Original verification intent:** in system-loopback mode the UART must feed its own transmitted
serial bit back into its receiver. To review this in RTL one must trace how the transmitter's
serial output reaches the receiver's input, and confirm the connection is *direct* (bypassing the
receiver's 2-flop synchronizer) — the testplan states there is no synchronizer between rx and tx
in this class of loopback.

**Question (user-style):** *"In the OpenTitan UART's system-loopback mode, the transmitter's serial
output has to get back into the receiver. Can you trace the directed path that the transmitted bit
takes to reach the receiver's input? I'd like the exact ordered list of canonical signal ids, and I
also want to know whether that connection goes through the receiver's input synchronizer or bypasses
it."*

**Expected answer**

| item | value |
|---|---|
| from → to | `uart.uart_core.tx_out` → `uart.uart_core.rx_in` |
| hop_count | 2 |
| candidate_count | 2 |
| path | `uart.uart_core.tx_out` → `uart.uart_core.rx_in.ternary_sys_loopback` → `uart.uart_core.rx_in` |
| bypasses input synchronizer | **true** (`uart.uart_core.sync_rx` / `sync_rx.q_o` are NOT on the path) |

**Ground truth from source (not the tool):**
- `uart_core.sv:214` — the `uart_tx` instance output is wired to `tx_out`.
- `uart_core.sv:264-266` — `assign rx_in = sys_loopback ? tx_out : line_loopback ? 1'b1 : rx_in_mx;` → in system-loopback `tx_out` feeds `rx_in` directly.
- `uart_core.sv:307` — `rx_val_q <= {rx_val_q[14:0], rx_in};` → `rx_in` is what the RX shift register consumes, closing the loop the testplan's "RDATA == WDATA" check depends on.
- `uart_core.sv:235-243` — the `prim_flop_2sync sync_rx` instance is fed by the `rx` *input port*; `rx_in` is the mux output, so the synchronizer is structurally not in the `tx_out → rx_in` path.

**requires_search: false** · **requires_verify: false**

**Ambiguity / caveat:** `paths --all` reports 2 distinct directed paths for this pair (hop counts 2
and 3) — the same `--canonical` ambiguity seen in the existing UART corpus. `--canonical` must be
pinned. Also, `uart_core.sv:217` (`assign tx = line_loopback ? rx : tx_out_q;`) is a *different*
loopback (line loopback) and must not be confused with the system loopback.

**Validation commands** (all confirmed):
```bash
sv_query paths --from-snapshot opentitan_uart 'uart.uart_core.tx_out' 'uart.uart_core.rx_in' --directed --canonical --json
#   found=true hop_count=2 candidate_count=2
sv_query paths --from-snapshot opentitan_uart 'uart.uart_core.tx_out' 'uart.uart_core.rx_in' --directed --all --json
#   count=2 truncated=false
sv_query verify claim --from-snapshot opentitan_uart --claim '{"type":"driver","signal":"uart.uart_core.rx_in","driver":"uart.uart_core.tx_out"}' --json   # verified
sv_query verify claim --from-snapshot opentitan_uart --claim '{"type":"path","from":"uart.uart_core.tx_out","to":"uart.uart_core.rx_in"}' --json                               # verified
sv_query loads --from-snapshot opentitan_uart 'uart.uart_core.rx_in' --json
#   ['uart.uart_core.rx_val_q','uart.uart_core.hw2reg.val.d','uart.uart_core.uart_rx.rx', ...] — sync_rx.q_o ABSENT
```

---

## 5. Ambiguities and risks

1. **The `checklist.md` files are not a task source.** Both `hw/ip/uart/doc/checklist.md` (279
   lines) and `hw/ip/i2c/doc/checklist.md` (268 lines) are project-governance sign-off tables
   (D1/D2/D2S/D3, V1/V2/V2S/V3) listing items like `SPEC_COMPLETE` / `SIM_ALL_TESTS_PASSING`.
   They contain **no per-feature verification intent**, so no task cites them as a source. A
   future intake should not expect feature-level items there.
2. **The per-feature intent lives in the testplan hjson, not the sim_cfg.** `uart_sim_cfg.hjson`
   is a test *list* (name → `uvm_test_seq`); the intent text is in `data/*_testplan.hjson`. The
   `sim_cfg` `testplan:` pointer is the reliable bridge between them.
3. **T1's direct-driver framing is false.** `ctrl.nf.q → rx_in_mx` is `contradicted` because a
   mux select is not a DRIVER edge. The task expects the *path* framing. If a grader insists on
   a direct driver, the task is unanswerable as written.
4. **T2's abstain answer is `unknown`, not `contradicted`.** `verify claim` distinguishes
   "node absent" from "claim refuted". A grader that only accepts `contradicted` for a false
   hypothesis will mis-grade.
5. **T2 has a same-name collision.** `arbitration_lost` and `bus_timeout` exist in *both*
   CONTROLLER_EVENTS and TARGET_EVENTS. The question must pin the CONTROLLER_EVENTS context.
6. **T3 depends on `--canonical`.** Without it the tool returns a 3-hop variant; `--all` shows 2
   candidates. Frozen expectations must pin the flag, as the existing corpus already learned.
7. **Coverage is narrow.** 5 of ~50 UART+I2C testpoints are represented. The many I2C testpoints
   with `tests: []` (unimplemented) — `target_mode_n_byte_ack_control`,
   `target_mode_bus_timeout`, `controller_mode_bus_timeout`, `multi_controller_arbitration_lost`,
   `loopback_test`, `controller_mode_idle_delay` — are good future sources but their RTL may be
   incomplete, so ground truth may be weak.
8. **Two testplans are sec_cm-only.** `uart_sec_cm_testplan.hjson` / `i2c_sec_cm_testplan.hjson`
   exist and were not used; they cover one-hot/write-enable integrity, which overlaps the
   existing `INTR_TEST`/`prim_reg_we_check` benchmark family.
9. **Ground truth was confirmed by CLI after source reading**, but the *canonical ID spellings*
   ultimately come from the tool's id scheme. If the tool's id convention changes, the frozen
   canonical IDs break even though the RTL facts do not.
10. **The `verify` outcomes are the tool's, not the design's.** T2's four `verified` results are
    consistent with the RTL OR-reduction, but they are still tool-produced judgements. T2's
    value comes from the *source-derived* event list being confirmed, not from the tool
    discovering it.

---

## 6. Artifact index

| Path | Contents |
|---|---|
| `/tmp/opentitan_intake/tasks.json` | The 3 tasks with `id`, `source_artifact`, `original_verification_intent`, `question`, `expected`, `ground_truth_confirmation`, `requires_search`, `requires_verify`, `validation_commands`, `expected_cli_results` |
| `/tmp/opentitan_intake/REPORT.md` | This report |

Snapshots used read-only (not modified): `/tmp/opentitan_svq/snapshots/opentitan_uart.json`,
`/tmp/opentitan_svq_i2c/snapshots/opentitan_i2c.json`.

### Reproduce the validation

```bash
cd /Users/fundou/.dsh/opencode-workers-lite/opentitan-pilot/workspace

# T1 (UART snapshot)
export SVQ_SNAPSHOT_DIR=/tmp/opentitan_svq/snapshots
sv_query paths --from-snapshot opentitan_uart \
  'uart.uart_core.reg2hw.ctrl.nf.q' 'uart.uart_core.rx_in_mx' --directed --canonical --json

# T2 (i2c snapshot)
export SVQ_SNAPSHOT_DIR=/tmp/opentitan_svq_i2c/snapshots
sv_query verify claim --from-snapshot opentitan_i2c --claim \
  '{"type":"driver","signal":"i2c.i2c_core.status_controller_halt","driver":"i2c.i2c_core.reg2hw.controller_events.tx_pending.q"}' --json

# T3 (UART snapshot)
export SVQ_SNAPSHOT_DIR=/tmp/opentitan_svq/snapshots
sv_query paths --from-snapshot opentitan_uart \
  'uart.uart_core.tx_out' 'uart.uart_core.rx_in' --directed --canonical --json
```
