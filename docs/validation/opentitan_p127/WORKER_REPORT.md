# OpenTitan → sv_query Intake Extension (P127) — 2 NEW tasks

**Date:** 2026-11-09
**OpenTitan source root:** `/Users/fundou/.dsh/opencode-workers-lite/opentitan-pilot/workspace`
**OpenTitan HEAD:** `a82c4892e88253924b3f7af05ce7494232ab263a` (`[doc] Update ILA debugging documentation`)
**Artifacts:** `/tmp/opentitan_intake_p127/tasks.json`, `/tmp/opentitan_intake_p127/REPORT.md`
**No OpenTitan or sv_query file was modified. No LLM/DSH agent was run.**

---

## 1. Scope and method

Exactly 2 new tasks, one UART + one I2C, on testpoints **not** used by the P125 intake:

| already used (not repeated) | UART: `rx_noise_filter`, `sys_loopback` · I2C: `host_mode_halt_on_nak`, `multi_controller_arbitration_lost_interference`, `controller_mode_bus_timeout` |
|---|---|
| **new here** | **UART: `tx_overide`** (discovery) · **I2C: `host_error_intr`** (path) |

Method per task — **source first, tool second**:

1. Pick the DV verification intent from the testplan.
2. Read the RTL + reggen package + register doc to determine the answer.
3. Write the expected answer and canonical IDs from that source reading.
4. *Only then* use the `sv_query` CLI to confirm canonical-ID spellings and cross-check.

Ground truth is therefore **source-derived**, not tool-derived. Every line reference below was
re-verified by `sed -n` after the CLI runs.

### Source artifacts read

`hw/ip/uart/data/uart_testplan.hjson`, `hw/ip/uart/doc/registers.md`,
`hw/ip/uart/rtl/uart_core.sv`, `hw/ip/uart/rtl/uart_reg_pkg.sv`,
`hw/ip/i2c/data/i2c_testplan.hjson`, `hw/ip/i2c/rtl/i2c_core.sv`,
`hw/ip/i2c/rtl/i2c_reg_pkg.sv`, `hw/ip/i2c/dv/env/seq_lib/i2c_glitch_vseq.sv`.

Snapshots used **read-only** for canonical-ID resolution only:
`opentitan_uart` (4803 nodes / 8507 edges), `opentitan_i2c` (9370 / 17599).

---

## 2. Task T1 — `DV-UART-TXOVERRIDE-DISCOVERY` (discovery)

**Testplan:** `hw/ip/uart/data/uart_testplan.hjson` testpoint `tx_overide` (V2, tests
`["uart_tx_ovrd"]`) — *"Enable override control and use register programming to drive uart
output directly."*

**Original verification intent:** software must be able to take direct control of the TX pin
instead of the transmitter. To review it in RTL you must establish *which* register bits take
part, *which* of them actually puts a value on the pin, and *what the priority is* when the
override, system loopback and the normal transmitter all want to drive TX — the RTL resolves
this as a priority chain inside one `always_ff`, which is **not** visible from the register
documentation alone.

**Question (user-style):** *"The OpenTitan UART has a register that lets software take direct
control of the TX pin instead of letting the transmitter drive it. I've been asked to confirm that
this override really works, and also to work out what happens when the override, the loopback
mode and the normal transmitter all want to drive TX at the same time. Can you tell me which
register bits are involved, which of them actually puts a value onto the TX pin, and what the
priority order is between the three possibilities? Please give me the exact canonical signal
ids."*

**Expected answer**

| item | value |
|---|---|
| override enable bit / canonical id | `OVRD.TXEN` / `uart.uart_core.reg2hw.ovrd.txen.q` |
| override enable alias | `uart.uart_core.ovrd_tx_en` |
| override value bit / canonical id | `OVRD.TXVAL` / `uart.uart_core.reg2hw.ovrd.txval.q` |
| override value alias | `uart.uart_core.ovrd_tx_val` |
| TX flop | `uart.uart_core.tx_out_q` |
| TX pin | `uart.cio_tx_o` |
| priority (high→low) | reset `1'b1` → `ovrd_tx_val` (when `ovrd_tx_en`) → `1'b1` (system loopback) → `tx_out` (normal transmitter) |
| path OVRD.TXVAL → TX pin | `reg2hw.ovrd.txval.q → ovrd_tx_val → tx_out_q → tx.ternary_line_loopback → tx → cio_tx_o` (5 hops) |

**Ground truth from source (not the tool):**
- `uart_core.sv:218-228` — one `always_ff` else-if chain: `if (!rst_ni) tx_out_q <= 1'b1; else if (ovrd_tx_en) tx_out_q <= ovrd_tx_val; else if (sys_loopback) tx_out_q <= 1'b1; else tx_out_q <= tx_out;` — **the if/else-if ordering IS the priority**.
- `uart_core.sv:88-89` — `assign ovrd_tx_en = reg2hw.ovrd.txen.q; assign ovrd_tx_val = reg2hw.ovrd.txval.q;` — establishes the canonical ids and the local aliases.
- `uart_core.sv:217` — `assign tx = line_loopback ? rx : tx_out_q;` — the flop reaches the TX port.
- `uart_reg_pkg.sv:220-226, :336` — `uart_reg2hw_ovrd_reg_t` has exactly two fields (txval, txen) at bits [26:25], so OVRD has one enable and one value bit and nothing else participates.
- `registers.md:316-330` — OVRD = "TX pin override control. Gives direct SW control over TX pin state", offset 0x28, fields TXEN/TXVAL — the documentation names the same two bits.

**requires_search: true** · **requires_verify: false**

### Caveats (all recorded in tasks.json)

1. **DIRECT-DRIVER:** `ovrd_tx_en` is **not** a driver of `tx_out_q` — the claim is
   **contradicted** (`not in fanin(..., depth=1)`) and `loads(ovrd_tx_en) == 0`. The enable
   appears only inside the per-driver **conditions**. Only the *value* bit is a real DRIVER edge.
2. **REGISTER-BIT:** `uart.reg2hw.ovrd.txen.q` and `uart.u_reg.reg2hw.ovrd.txen.q` also exist in
   the graph but are **isolated leaves with no edges**; only the `uart.uart_core`-side id is live.
3. **CANONICAL:** `paths --directed` without `--canonical` returns a **4-hop** variant; with
   `--canonical` it is **5 hops**; `--all` shows exactly 2 candidates (5 and 6 hops).
4. **PRIORITY:** the reset and system-loopback branches both surface as the *same* constant
   `1'b1` driver, so the four-way priority is only recoverable by reading the **conditions** of
   that one driver, not from four separately-named drivers.

---

## 3. Task T2 — `DV-I2C-SDA-INTERFERENCE-PATH` (path)

**Testplan:** `hw/ip/i2c/data/i2c_testplan.hjson` testpoint `host_error_intr` (V2, tests
`["i2c_host_error_intr"]`) — *"In host transmit mode, device (target/host) forces SDA or SCL
signal low within the clock pulse of host SCL that asserts `sda_interference` or `scl_interference`
interrupts"* … *"Ensure all intr_scl_interference, intr_sda_interference, and intr_sda_unstable
interrupts are asserted and stay asserted until cleared"*.

**Original verification intent:** another device pulls SDA low while the DUT is transmitting, and
the DUT must notice and raise the SDA-interference error. To review it in RTL you must trace how
the DUT observes the line going low *while it believed it was driving* — including the input
synchronizer, which is exactly where a naive trace would wrongly assume the DUT reacts to a raw
asynchronous pin.

**Question (user-style):** *"In the OpenTitan I2C, there's an error case where the DUT is
transmitting on the bus but another device pulls the SDA line low underneath it, and the DUT is
supposed to notice and raise the SDA-interference error. I'd like to understand how that detection
is actually wired up: starting from the chip's SDA input pin, what is the ordered chain of internal
signals that the DUT goes through before it concludes that the line was pulled down on it? Please
give me the exact canonical signal ids and the hop count."*

**Expected answer**

| item | value |
|---|---|
| from → to | `i2c.cio_sda_i` → `i2c.i2c_core.event_sda_interference` |
| hop_count / candidates | **13** / 3 |
| path | `cio_sda_i → sda_i → u_i2c_sync_sda.d_i → .d_o → .u_sync_1.d_i → .u_sync_1.q_o → .intq → .u_sync_2.d_i → .u_sync_2.q_o → .q_o → sda_sync → sda_released_but_low → controller_sda_interference → event_sda_interference` |
| synchronizer instance | `i2c.i2c_core.u_i2c_sync_sda` |

**Ground truth from source (not the tool):**
- `i2c_core.sv:493` — `assign sda_released_but_low = bus_event_detect && scl_sync && (sda_fsm_q != sda_sync);` — the comparison of the DUT's own last-driven SDA against the synchronized bus level: the actual "someone pulled it low" detection.
- `i2c_core.sv:495` — `assign controller_sda_interference = controller_transmitting && sda_released_but_low;` — qualified by "DUT is transmitting".
- `i2c_core.sv:498` — `assign event_sda_interference = controller_sda_interference;`.
- `i2c_core.sv:492` — `assign bus_event_detect = (bus_event_detect_cnt == '0);` — the settle/debounce qualifier.
- `i2c_core.sv:452` — the `prim_flop_2sync` instance `u_i2c_sync_sda` feeds `sda_sync`, so the detection path **necessarily** passes through the 2-flop synchronizer.
- `i2c_core.sv:730-740` — `prim_intr_hw intr_hw_sda_interference` takes `.event_intr_i(event_sda_interference)` and produces `.intr_o(intr_sda_interference_o)`, closing the loop with the testplan's "asserted and stay asserted until cleared" requirement.

**requires_search: false** · **requires_verify: false**

### Caveats

1. **CANONICAL:** without `--canonical` the tool returns a **9-hop** variant; `--canonical` gives
   **13 hops**; `--all` shows 3 candidates (10, 13, 14 hops).
2. **DIRECT-DRIVER:** the direct-driver claim from the chip pin to the event is
   **contradicted** (13 hops separate them). The task asks for the path, so this is expected.
3. **TERMINAL:** the path stops at `event_sda_interference`, **not** at the chip-level
   `intr_sda_interference_o` — the final hop goes through the `prim_intr_hw` instance, whose
   `hw2reg_intr_state_q_i` / `intr_o` structure does **not** produce a directed path to the port.
   A task demanding the full path to the pin would not be answerable as specified.
4. **SCOPE:** `host_error_intr` also covers `scl_interference` and `sda_unstable`, which are
   **separate** detections (from `scl_sync` and the controller FSM's unstable-SDA logic). Only
   the SDA-interference branch is claimed here.

---

## 4. Validation summary

27 assertions, **0 failures**:

```
T1  drivers(ovrd_tx_en)  == [reg2hw.ovrd.txen.q]        PASS
T1  drivers(ovrd_tx_val) == [reg2hw.ovrd.txval.q]       PASS
T1  loads(ovrd_tx_en)    == 0                            PASS   <- enable is condition-only
T1  loads(tx_out_q)      == 2                            PASS
T1  drivers(tx_out_q)    == 5                            PASS
T1  all 4 priority branches present in conditions         PASS
T1  canonical path == frozen, hop_count == 5              PASS
T1  non-canonical hop_count == 4                         PASS   <- canonical caveat
T1  paths --all count == 2                               PASS
T1  verify driver ovrd_tx_val  -> verified               PASS
T1  verify driver ovrd_tx_en   -> contradicted           PASS   <- documented caveat
T2  canonical path == frozen, hop_count == 13             PASS
T2  candidate_count == 3                                 PASS
T2  non-canonical hop_count == 9                         PASS   <- canonical caveat
T2  paths --all count == 3                               PASS
T2  drivers(event_sda_interference) count == 20, d1 == {controller_sda_interference}   PASS
T2  drivers(sda_released_but_low)    count == 16, d1 == {bus_event_detect, scl_sync, sda_sync, sda_fsm_q}  PASS
T2  drivers(controller_sda_interference) count == 19, d1 == {controller_transmitting, sda_released_but_low}     PASS
T2  loads(u_i2c_sync_sda.q_o) count == 23, d1 == {sda_sync}   PASS
T2  verify path  -> verified                             PASS
T2  verify driver (chip pin -> event) -> contradicted    PASS   <- documented caveat
```

A correction was made during validation: my first draft recorded the `drivers`/`loads` counts for
T2 as single-hop. The CLI returns the **transitive** fanin/fanout (20 / 16 / 19 / 23), so the
recorded expectations now state both the total and the **distance-1** subset, which is what the
answers actually depend on.

---

## 5. Risks

1. **Both tasks depend on `--canonical`.** T1 gives 5 vs 4 hops, T2 gives 13 vs 9 hops, and T2 has
   3 distinct candidate paths. A harness that omits `--canonical` will grade against a different
   (also valid) path — the same failure mode that produced the `ot_uart_rx_path`
   false_confident earlier.
2. **T1's answer is condition-encoded.** The enable bit `ovrd_tx_en` has **zero loads** and a
   **contradicted** driver claim; the priority is only visible in the *conditions* of the driver
   list. An agent that only reads driver/load edges will find only `ovrd_tx_val` and will miss
   the priority ordering entirely. The expected answer therefore includes a
   `priority_evidence` field.
3. **T1 has three live-looking ids for one register bit.** `uart.reg2hw.ovrd.txen.q`,
   `uart.u_reg.reg2hw.ovrd.txen.q` and `uart.uart_core.reg2hw.ovrd.txen.q` all exist; only the
   last has edges. A discovery agent can easily report the wrong one, and the question's
   phrasing must make the uart_core-side id the expected answer.
4. **T2's terminal is a modelling limit.** The path cannot be extended to the chip-level interrupt
   port because `prim_intr_hw` does not expose a directed edge to it. If a future tool version
   adds one, the "13 hops" answer would change — this is the same class of fragility as the
   UART ternary/`drivers` asymmetry already documented.
5. **Two of the four caveats are `contradicted` results.** For both tasks the *direct-driver*
   framing is false while the *path* framing is true. A grader that only accepts `verified` for a
   true structural relationship will mis-grade; the tasks.json records the tool's actual output and
   the reason, so a grader can distinguish "tool regression" from "wrong answer".
6. **Coverage is still narrow.** 2 new testpoints out of ~50 UART+I2C. Many I2C testpoints have
   `tests: []` (unimplemented) and were deliberately avoided because their RTL may be incomplete
   and ground truth weak.
7. **Canonical-ID spellings still originate from the tool's id scheme.** The structural facts are
   source-derived, but a change to the tool's naming convention would break the frozen IDs.
8. **The `verify` outcomes remain tool-produced judgements.** In this pair the *structure* was
   source-derived (the priority chain, the 4-stage detection chain); the CLI only confirmed it
   and supplied the condition strings.

---

## 6. Artifact index

| Path | Contents |
|---|---|
| `/tmp/opentitan_intake_p127/tasks.json` | The 2 tasks: `id`, `block`, `snapshot`, `snapshot_dir`, `source_root`, `kind`, `source_artifact`, `original_verification_intent`, `question`, `answer_schema`, `expected`, `ground_truth_confirmation`, `requires_search`, `requires_verify`, `caveats`, `validation_commands`, `expected_cli_results` |
| `/tmp/opentitan_intake_p127/REPORT.md` | This report |

### Reproduce the validation

```bash
cd /Users/fundou/.dsh/opencode-workers-lite/opentitan-pilot/workspace

# T1 (UART snapshot)
export SVQ_SNAPSHOT_DIR=/tmp/opentitan_svq/snapshots
sv_query drivers --from-snapshot opentitan_uart 'uart.uart_core.tx_out_q' --json
sv_query paths    --from-snapshot opentitan_uart 'uart.uart_core.reg2hw.ovrd.txval.q' 'uart.cio_tx_o' --directed --canonical --json

# T2 (i2c snapshot)
export SVQ_SNAPSHOT_DIR=/tmp/opentitan_svq_i2c/snapshots
sv_query paths --from-snapshot opentitan_i2c 'i2c.cio_sda_i' 'i2c.i2c_core.event_sda_interference' --directed --canonical --json
```
