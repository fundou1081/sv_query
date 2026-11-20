# P192 — CVA6 Sv39 spurious page-fault: analysis

Elapsed wall time: ~7 min 42 s (start 08:02:59 CST, finish ~08:10:41 CST,
2026-11-20). No files under `rtl/` were modified.

## 1. Root cause

**File:** `rtl/cva6_mmu.sv`, `always_comb begin : data_interface`, lines **541–543**.

```systemverilog
// we work with SV39 or SV32, so if VM is enabled, check that all bits [CVA6Cfg.VLEN-1:CVA6Cfg.SV-1] are equal to bit [CVA6Cfg.SV]
canonical_addr_check = (lsu_req_i && en_ld_st_translation_i &&
       !((&lsu_vaddr_i[CVA6Cfg.VLEN-1:CVA6Cfg.SV-1]) == 1'b1 || (|lsu_vaddr_i[CVA6Cfg.VLEN-1:CVA6Cfg.SV-1]) == 1'b0));
```

The *expression* is a correct Sv39 canonical check: in the elaborated config
`XLEN = VLEN = 64`, `SV = 39`, so `CVA6Cfg.VLEN-1:CVA6Cfg.SV-1 = 63:38`
(sv_query's bit-select hint literally reports the driver as
`lsu_vaddr_i[32'd63:32'd38]`). Requiring `VA[63:38]` to be all-1 or all-0 is
exactly `VA[63:39] == VA[38]`.

The defect is a **pipeline-stage mismatch**. `canonical_addr_check` is a
purely combinational function of the *current* inputs (`lsu_req_i`,
`lsu_vaddr_i`), but its only consumers are lines **630** and **658**, inside the
DTLB-hit branch that starts at line **607**:

```systemverilog
if (dtlb_hit_q && lsu_req_q) begin            // line 607 — response for the REGISTERED request
  ...
  end else if ((en_ld_st_translation_i || !CVA6Cfg.RVH) &&
               (!dtlb_pte_q.w || daccess_err || canonical_addr_check || !dtlb_pte_q.d)) begin // line 630
    lsu_exception_o.cause = riscv::STORE_PAGE_FAULT;
    if (CVA6Cfg.TvalEn)
      lsu_exception_o.tval = {{CVA6Cfg.XLEN-CVA6Cfg.VLEN{lsu_vaddr_q[CVA6Cfg.VLEN-1]}}, lsu_vaddr_q}; // 634-636
  ...
  end else if (daccess_err || canonical_addr_check) begin                                    // line 658
    lsu_exception_o.cause = riscv::LOAD_PAGE_FAULT;
    if (CVA6Cfg.TvalEn)
      lsu_exception_o.tval = {{CVA6Cfg.XLEN-CVA6Cfg.VLEN{lsu_vaddr_q[CVA6Cfg.VLEN-1]}}, lsu_vaddr_q}; // 662-664
  end
```

Every other participant in that decision (`dtlb_hit_q`, `lsu_req_q`,
`lsu_vaddr_q`, `lsu_is_store_q`, `dtlb_pte_q`) is a flop updated in the
`always_ff` at lines **771–801**. `canonical_addr_check` is the lone
current-cycle signal mixed into a registered response stage.

**Cycle-by-cycle failure:**

| Cycle | Inputs | Registered state (q) | `canonical_addr_check` | Output |
|---|---|---|---|---|
| C | legal, canonical `N`; `lsu_req_i=1` | previous | 0 | `lsu_vaddr_n=N`, `lsu_req_n=1` sampled at posedge |
| C+1 | non-canonical `N+1`; `lsu_req_i=1` | `lsu_vaddr_q=N`, `lsu_req_q=1`, `dtlb_hit_q=1` | **1** (computed from `N+1`) | hit path for **N** ORs in the flag → spurious `STORE_PAGE_FAULT` / `LOAD_PAGE_FAULT`, `tval = lsu_vaddr_q = N` |
| C+2 | — | `lsu_vaddr_q=N+1` | 1 | (fault would now be correctly attributed to N+1) |

This reproduces all four reported symptoms:

* the earlier, legal access N is blamed (wrong cycle);
* causes 13 / 15 are `LOAD_PAGE_FAULT` / `STORE_PAGE_FAULT`, matching the
  pre-fix `tohost` signatures 13 and 15;
* `tval` is built from `lsu_vaddr_q` (N), which is canonical — hence a
  canonical `tval` even though the offending input was non-canonical;
* Spike does not fault, so the report is spurious, not architectural.

Since `VLEN == XLEN == 64`, the `{...{lsu_vaddr_q[63]}, lsu_vaddr_q}`
replication is empty; `tval` is literally the earlier canonical address N.

## 2. Minimal semantics-preserving patch (NOT applied)

Align the canonical check with the registered request it is used to judge.
Only two signal references change:

```diff
--- a/rtl/cva6_mmu.sv
+++ b/rtl/cva6_mmu.sv
@@ -539,8 +539,8 @@
     misaligned_ex_n.valid = misaligned_ex_i.valid & lsu_req_i;
 
     // we work with SV39 or SV32, so if VM is enabled, check that all bits [CVA6Cfg.VLEN-1:CVA6Cfg.SV-1] are equal to bit [CVA6Cfg.SV]
-    canonical_addr_check = (lsu_req_i && en_ld_st_translation_i &&
-           !((&lsu_vaddr_i[CVA6Cfg.VLEN-1:CVA6Cfg.SV-1]) == 1'b1 || (|lsu_vaddr_i[CVA6Cfg.VLEN-1:CVA6Cfg.SV-1]) == 1'b0));
+    canonical_addr_check = (lsu_req_q && en_ld_st_translation_i &&
+           !((&lsu_vaddr_q[CVA6Cfg.VLEN-1:CVA6Cfg.SV-1]) == 1'b1 || (|lsu_vaddr_q[CVA6Cfg.VLEN-1:CVA6Cfg.SV-1]) == 1'b0));
 
     // Check if the User flag is set, then we may only access it in supervisor mode
```

Why this is semantics-preserving:

* For a legal canonical access, `lsu_vaddr_i` and `lsu_vaddr_q` have the same
  canonical property for the request being responded to, so the flag stays 0
  and no behavior changes.
* For a genuinely non-canonical access, the fault is now raised in the same
  cycle that the hit path processes that address, and `tval` (from
  `lsu_vaddr_q`) correctly names the non-canonical address.
* The DTLB hit/miss, PTW, instruction side, and all other fault conditions are
  untouched. The check expression itself (the Sv39 bit range and polarity) is
  unchanged; only its sampling point moves.

An equivalent, slightly larger fix is to introduce `canonical_addr_check_n`
computed from `lsu_vaddr_i`, flop it into `canonical_addr_check_q` in the
`always_ff`, and use `canonical_addr_check_q` at lines 630/658. That form
samples the enable at request time; in practice `en_ld_st_translation_i` is a
quasi-static CSR-derived signal and any change flushes the pipeline, so the two
forms are equivalent.

## 3. Evidence trail (commands and output)

All commands run from `/tmp/p192_sq` with
`/tmp/svq-pypi-smoke2/bin/sv_query` (PyPI 0.3.1).

**(a) Locate the signal and its uses**

```
$ sv_query search canonical --file rtl --json
{
  "keyword": "canonical",
  "total_matches": 4, "file_count": 1,
  "files": [{"file": "rtl/cva6_mmu.sv", "match_count": 4, "lines": [
    {"line": 142, "text": "  logic canonical_addr_check;  // canonical check on the virtual address for SV39"},
    {"line": 542, "text": "    canonical_addr_check = (lsu_req_i && en_ld_st_translation_i &&"},
    {"line": 630, "text": "          end else if ((en_ld_st_translation_i || !CVA6Cfg.RVH) && (!dtlb_pte_q.w || daccess_err || canonical_addr_check || !dtlb_pte_q.d)) begin"},
    {"line": 658, "text": "          end else if (daccess_err || canonical_addr_check) begin"}
  ]}]
}
```
→ The flag has exactly one driver and two consumers; both consumers are the
data-side page-fault branches.

**(b) Bit-select hint confirms the Sv39 range and current-cycle source**

```
$ sv_query drivers canonical_addr_check --filelist filelist.f --json \
    | python3 -c "import json,sys; d=json.load(sys.stdin); [print(x['id'],'dist='+str(x['distance'])) for x in d['result']['signals'][0]['drivers']]"
p187_mmu_top.u_mmu.en_ld_st_translation_i dist=1
p187_mmu_top.u_mmu.lsu_req_i dist=1
p187_mmu_top.lsu_req_i dist=2
p187_mmu_top.u_mmu.lsu_vaddr_i[32'd63:32'd38] dist=1
```
→ The driver is `lsu_vaddr_i[63:38]` ( = `[VLEN-1:SV-1]` with SV=39 ), at
distance 1 from the *input* port. There is **no** driver edge from
`lsu_vaddr_q`.

**(c) Registered-vs-combinational stage check**

```
$ sv_query trace profile p187_mmu_top.u_mmu.canonical_addr_check --filelist filelist.f --json
... "kind": "SIGNAL", "source": {"file": "rtl/cva6_mmu.sv", "line": 142, ...},
    "clock_domains": [], "clocks": [],
    "sequential": {"is_sequential": true, "stage_known": false,
                   "stage_unknown_reason": "combinational", ...}, "driver_count": 3, ...

$ sv_query trace profile p187_mmu_top.u_mmu.lsu_vaddr_q --filelist filelist.f --json
... "kind": "REG", "clocks": [{"signal":"...clk_i", ...}],
    "sequential": {"is_sequential": true, "stage": 0, "stage_known": true,
                   "stage_source": "pipeline_detect", "sample": "posedge ...clk_i",
                   "always": {"file":"rtl/cva6_mmu.sv","line":771}}, ...
```
→ `canonical_addr_check` has no clock domain; `lsu_vaddr_q` is a stage-0 flop.

**(d) Control-flow evidence for the faulty branches**

```
$ sv_query controlflow analyze p187_mmu_top.u_mmu.lsu_exception_o.valid \
    --filelist filelist.f --json --pretty --evidence
... "conditions": [
  {"expr": "... && dtlb_hit_q && lsu_req_q && !lsu_is_store_q && ... && canonical_addr_check",
   "evidence": {"enclosing_chain": [... "rtl/cva6_mmu.sv:607-672" ...],
                "source_text": "if(CVA6Cfg.RVH && en_ld_st_g_translation_i && ...",
                "enclosing_if": {"line_start": 618, "line_end": 642,
                  "text": "... end else if ((en_ld_st_translation_i || !CVA6Cfg.RVH) && (!dtlb_pte_q.w || daccess_err || canonical_addr_check || !dtlb_pte_q.d)) begin
                            lsu_exception_o.cause = riscv::STORE_PAGE_FAULT;
                            ... lsu_exception_o.tval = { {CVA6Cfg.XLEN - CVA6Cfg.VLEN{lsu_vaddr_q[CVA6Cfg.VLEN-1]}}, lsu_vaddr_q }; ...",
                  "is_verified": true}},
  {"expr": "... && dtlb_hit_q && lsu_req_q && !lsu_is_store_q && !(...) && daccess_err || canonical_addr_check", ... }
]
```
→ The tool binds `canonical_addr_check` into the *same* condition as
`dtlb_hit_q && lsu_req_q`, and shows `tval` sourced from `lsu_vaddr_q` in that
very block.

**(e) Elaborated configuration**

```
$ sv_query search 'CVA6ConfigXlen|CVA6ConfigHExtEn' --file \
    rtl/include/cv64a6_imafdc_sv39_config_pkg.sv --regex --json
line 13: localparam CVA6ConfigXlen = 64;
line 27: localparam CVA6ConfigHExtEn = 0;  // always disabled
$ sv_query search VLEN --file rtl/include/cv64a6_imafdc_sv39_config_pkg.sv --json
line 80: VLEN: unsigned'(64),
```
`SV = 39` is confirmed independently by the `[63:38]` driver bit-select in (b).
Therefore `tval` has no sign-extension bits (`XLEN - VLEN = 0`).

**(f) Source inspection (read tool, this package only)**

`rtl/cva6_mmu.sv` lines 505–543, 572–671, 771–801 read directly; no other
file in `rtl/` contains a canonical-address check (search in (a)).

## 4. Confidence and alternative hypotheses

**Confidence: high (~0.95).** The evidence is a complete structural chain:
current-cycle driver (b) → flag with no register stage (c) → use inside a
`dtlb_hit_q && lsu_req_q` branch that builds `tval` from `lsu_vaddr_q` (d).
It explains every symptom, including the unusual detail that `tval` is the
canonical N rather than the offending N+1. The fix is local (two identifiers)
and does not alter any check polarity or bit range.

**Alternatives considered and rejected**

1. *PTW error / `misaligned_page` / reserved-bit PTE checks* (`cva6_ptw.sv`
   lines 430–531, 609–616). These are only consulted on a **DTLB miss**
   (`cva6_mmu.sv` 678–763) and produce `tval` from `update_vaddr` (`vaddr_q`
   inside the PTW), not from the earlier successful translation. The reported
   sequence is a hit on N, so this path is not involved.
2. *TLB storing a stale or non-canonical entry*. TLB updates are driven by
   `shared_tlb_update_o` from the PTW and keyed by `vaddr_q`; nothing there is
   a function of the *next* input address, so it cannot explain why the fault
   appears only when N+1 is presented on the following cycle.
3. *`daccess_err` stage mismatch*. It also appears in the hit path, but it is
   built from `dtlb_pte_q` (registered) plus quasi-static privilege/SUM CSRs;
   it is not a function of `lsu_vaddr_i[63:38]`, so it cannot be triggered by
   a non-canonical address.
4. *Wrong `tval` formatting / sign extension*. With `VLEN = XLEN = 64` the
   replication prefix is zero-width, so `tval = lsu_vaddr_q` exactly. The
   canonical value in `tval` is proof of wrong-cycle attribution, not of a
   formatting bug.
5. *Bit-range off-by-one in the canonical expression*. The driver bit hint is
   `[63:38]`, which matches Sv39 exactly; changing the range would break legal
   cases and is not indicated.
6. *Equivalent flop-based fix*. Adding `canonical_addr_check_q` is also
   correct; it differs only if `en_ld_st_translation_i` changes between the
   request and response cycles, which flushes the pipeline in this design.

**What is missing:** no cycle-accurate simulation was run (the bundled harness
has no stimulus and `rtl/` may not be modified). The conclusion is a static,
tool-backed structural proof plus the reported pre-fix/post-Spike signatures;
it does not include a measured waveform. Verilator is present but was not used
to avoid touching `rtl/` or inventing a non-historical stimulus.
