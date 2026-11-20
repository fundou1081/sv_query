# P192 — CVA6 MMU spurious Sv39 page fault (issue #3404)

**Elapsed wall time:** ~9 minutes (08:02 → 08:11 CST, 2026-11-20).

`rtl/` was not modified. All patching/simulation was done on copies under `/tmp/p192_so/`.

---

## 1. Root cause

**A pipeline-stage mismatch on `canonical_addr_check` in `rtl/cva6_mmu.sv`.**

### The signal is combinational on the *request* inputs

`rtl/cva6_mmu.sv:142`

```systemverilog
  logic canonical_addr_check;  // canonical check on the virtual address for SV39
```

`rtl/cva6_mmu.sv:541-543` (inside `always_comb begin : data_interface`):

```systemverilog
    // we work with SV39 or SV32, so if VM is enabled, check that all bits [CVA6Cfg.VLEN-1:CVA6Cfg.SV-1] are equal to bit [CVA6Cfg.SV]
    canonical_addr_check = (lsu_req_i && en_ld_st_translation_i &&
           !((&lsu_vaddr_i[CVA6Cfg.VLEN-1:CVA6Cfg.SV-1]) == 1'b1 || (|lsu_vaddr_i[CVA6Cfg.VLEN-1:CVA6Cfg.SV-1]) == 1'b0));
```

It is computed from `lsu_req_i` / `lsu_vaddr_i`, i.e. the **current input cycle**.

### But it is consumed in the *response* stage of a registered pipeline

The data interface is a two-stage pipeline. At every posedge (`rtl/cva6_mmu.sv:771-802`) the request-cycle values are stored:

```
lsu_vaddr_q <= lsu_vaddr_n;   lsu_req_q <= lsu_req_n;
lsu_is_store_q <= lsu_is_store_n;   dtlb_hit_q <= dtlb_hit_n;
dtlb_pte_q <= dtlb_pte_n;     dtlb_is_page_q <= dtlb_is_page_n;
misaligned_ex_q <= misaligned_ex_n; ...
```

The exception/response is then produced in the **following cycle** from those `_q` registers:

- `rtl/cva6_mmu.sv:607` — DTLB-hit gate: `if (dtlb_hit_q && lsu_req_q) begin`
- `rtl/cva6_mmu.sv:615-664` — store path; fault condition at **line 630**:
  `end else if ((en_ld_st_translation_i || !CVA6Cfg.RVH) && (!dtlb_pte_q.w || daccess_err || canonical_addr_check || !dtlb_pte_q.d)) begin`
- `rtl/cva6_mmu.sv:658` — load path fault condition:
  `end else if (daccess_err || canonical_addr_check) begin`
- `rtl/cva6_mmu.sv:634-636` / `662-664` — `tval` is built from **`lsu_vaddr_q`**:
  `{ {CVA6Cfg.XLEN - CVA6Cfg.VLEN{lsu_vaddr_q[CVA6Cfg.VLEN-1]}}, lsu_vaddr_q }`

So `daccess_err` (`:547-549`) is already a response-stage quantity (uses `dtlb_pte_q`), but `canonical_addr_check` is the odd one out: it still reflects the *next* input.

### Failure sequence

Configuration is Sv39: `SV = 39` (`rtl/include/build_config_pkg.sv:199`), `VLEN = 64`
(`rtl/include/cv64a6_imafdc_sv39_config_pkg.sv:80`), so the checked range is `[63:38]`.

1. Cycle A: legal access at `N = 0x0000_003F_FFFF_FFFF` (last canonical low address). The
   walk succeeds, the DTLB is populated, `dtlb_lu_hit = 1`; at the next edge
   `dtlb_hit_q = 1`, `lsu_vaddr_q = N`, `lsu_req_q = 1`.
2. Cycle A+1: the input is switched to the non-canonical `N+1 = 0x0000_0040_0000_0000`
   (bit 38 = 1, bits `[63:39]` = 0). Now `canonical_addr_check` (combinational on
   `lsu_vaddr_i`) becomes **1**.
3. Still in cycle A+1, the DTLB-hit branch for the *previous* access N evaluates
   `dtlb_hit_q && lsu_req_q == 1` together with `canonical_addr_check == 1`, and raises
   `LOAD_PAGE_FAULT` (cause 13) / `STORE_PAGE_FAULT` (cause 15).
4. `tval` is assembled from `lsu_vaddr_q`, so it holds **N**, a canonical address — not
   the non-canonical address that caused the check to assert. This exactly matches the
   reported symptom.

Spike does not raise the fault because the CVA6 report is spurious: it attributes a
canonicality violation of the *next* input to an already-translated earlier access.

---

## 2. Minimal semantics-preserving patch (diff text, NOT applied to `rtl/`)

Registered the canonical check so it is sampled in the request cycle and consumed in
the response cycle, exactly like `lsu_vaddr_q`, `dtlb_hit_q`, `daccess_err`, etc.

```diff
--- a/rtl/cva6_mmu.sv
+++ b/rtl/cva6_mmu.sv
@@ -139,7 +139,7 @@
   logic iaccess_err;  // insufficient privilege to access this instruction page
   logic i_g_st_access_err;  // insufficient privilege at g stage to access this instruction page
   logic daccess_err;  // insufficient privilege to access this data page
-  logic canonical_addr_check;  // canonical check on the virtual address for SV39
+  logic canonical_addr_check_n, canonical_addr_check_q;  // canonical check, registered to align with the response-stage request registers
   logic d_g_st_access_err;  // insufficient privilege to access this data page
   logic ptw_active;  // PTW is currently walking a page table
   logic walking_instr;  // PTW is walking because of an ITLB miss
@@ -539,7 +539,7 @@
     misaligned_ex_n.valid = misaligned_ex_i.valid & lsu_req_i;
 
     // we work with SV39 or SV32, so if VM is enabled, check that all bits [CVA6Cfg.VLEN-1:CVA6Cfg.SV-1] are equal to bit [CVA6Cfg.SV]
-    canonical_addr_check = (lsu_req_i && en_ld_st_translation_i &&
+    canonical_addr_check_n = (lsu_req_i && en_ld_st_translation_i &&
            !((&lsu_vaddr_i[CVA6Cfg.VLEN-1:CVA6Cfg.SV-1]) == 1'b1 || (|lsu_vaddr_i[CVA6Cfg.VLEN-1:CVA6Cfg.SV-1]) == 1'b0));
 
     // Check if the User flag is set, then we may only access it in supervisor mode
@@ -627,7 +627,7 @@
               lsu_exception_o.tinst = '0;
               lsu_exception_o.gva = ld_st_v_i;
             end
-          end else if ((en_ld_st_translation_i || !CVA6Cfg.RVH) && (!dtlb_pte_q.w || daccess_err || canonical_addr_check || !dtlb_pte_q.d)) begin
+          end else if ((en_ld_st_translation_i || !CVA6Cfg.RVH) && (!dtlb_pte_q.w || daccess_err || canonical_addr_check_q || !dtlb_pte_q.d)) begin
             lsu_exception_o.cause = riscv::STORE_PAGE_FAULT;
             lsu_exception_o.valid = 1'b1;
             if (CVA6Cfg.TvalEn)
@@ -655,7 +655,7 @@
               lsu_exception_o.gva = ld_st_v_i;
             end
             // check for sufficient access privileges - throw a page fault if necessary
-          end else if (daccess_err || canonical_addr_check) begin
+          end else if (daccess_err || canonical_addr_check_q) begin
             lsu_exception_o.cause = riscv::LOAD_PAGE_FAULT;
             lsu_exception_o.valid = 1'b1;
             if (CVA6Cfg.TvalEn)
@@ -782,6 +782,7 @@
       hs_ld_st_inst_q <= '0;
       hlvx_inst_q     <= '0;
       misaligned_ex_q <= '0;
+      canonical_addr_check_q <= 1'b0;
     end else begin
       lsu_vaddr_q     <= lsu_vaddr_n;
       lsu_req_q       <= lsu_req_n;
@@ -790,6 +791,7 @@
       lsu_is_store_q  <= lsu_is_store_n;
       dtlb_is_page_q  <= dtlb_is_page_n;
       misaligned_ex_q <= misaligned_ex_n;
+      canonical_addr_check_q <= canonical_addr_check_n;
 
       if (CVA6Cfg.RVH) begin
         lsu_tinst_q     <= lsu_tinst_n;
```

Scope: 6 line changes, all inside `cva6_mmu.sv`. No other module, no architectural
behavior change for legal accesses, and genuine non-canonical faults are preserved
(validated below). `rtl/` remained pristine — verified with the bundled checksums:

```
$ shasum -c SHA256SUMS | grep -v ': OK'   # no mismatches; all rtl/*.sv OK
```

---

## 3. Evidence trail

All commands were run from `/tmp/p192_so`.

### 3.1 Source inspection

```
$ grep -n canonical_addr_check rtl/cva6_mmu.sv
142:  logic canonical_addr_check;  // canonical check on the virtual address for SV39
542:    canonical_addr_check = (lsu_req_i && en_ld_st_translation_i &&
630:          end else if ((en_ld_st_translation_i || !CVA6Cfg.RVH) && (!dtlb_pte_q.w || daccess_err || canonical_addr_check || !dtlb_pte_q.d)) begin
658:          end else if (daccess_err || canonical_addr_check) begin
```

`daccess_err` is registered-stage (uses `dtlb_pte_q` at `:547-549`), while
`canonical_addr_check` is request-stage — the mismatch.

```
$ verilator --lint-only --top-module p187_mmu_top -f filelist.f
# elaborates cleanly (only pre-existing width/latch/pin-missing warnings)
```

### 3.2 Simulation of the UNMODIFIED RTL

Built a local testbench (`tb_mmu.sv`, outside `rtl/`) that instantiates the real
`cva6_mmu`, performs a genuine Sv39 page-table walk (toy memory grants requests and
returns a valid 1 GiB leaf PTE), configures a PMP entry so the PTW read is allowed,
then issues the two-access sequence. Build (the SDK include flag works around a local
C++ toolchain header issue):

```
$ CXXFLAGS="-I/Library/Developer/CommandLineTools/SDKs/MacOSX26.2.sdk/usr/include/c++/v1 -Os" \
    verilator --binary -j 0 --timing -Wno-fatal -Wno-PINMISSING -Wno-LATCH \
    --top-module tb_mmu -f filelist.f tb_mmu.sv -o sim_tb
$ ./obj_dir/sim_tb | grep -E 'prime|resp N|legit'
[prime ] cyc=28 hit=1 valid=1 exc.valid=0 exc.cause=0 paddr=0000403fffffff
[resp N] cyc=29 in_vaddr=0000004000000000 q_vaddr=0000003fffffffff dtlb_hit_q=1 can=1 -> exc.valid=1 exc.cause=13 tval=0000003fffffffff
[resp N/store] cyc=34 in_vaddr=0000004000000000 q_vaddr=0000003fffffffff dtlb_hit_q=1 can=1 -> exc.valid=1 exc.cause=15 tval=0000003fffffffff
[legit Np1] cyc=50 in_vaddr=0000004000000000 q_vaddr=0000004000000000 dtlb_hit_q=1 can=1 -> exc.valid=1 exc.cause=15 tval=0000004000000000
```

Key observations:
- `prime`: N translates and completes normally (`valid=1`, no exception) — N is legal.
- `resp N`: `dtlb_hit_q=1` and `lsu_vaddr_q=N` (the earlier legal access), but
  `canonical_addr_check=1` because `lsu_vaddr_i` is now the non-canonical `N+1`.
  Result: spurious cause 13 with `tval = N` (canonical).
- `resp N/store`: same with cause 15 — reproduces both tohost values (13 and 15).
- `ptw_active = 0` during the spurious fault (monitored), so this is the DTLB-hit path,
  not the page-table-walk error path.

Cycle-by-cycle monitor excerpt at the fault:

```
MON cyc=29 req=1 va=0000004000000000 ... stlb_hit=0 dtlb_hit=1 d_hit_q=1 d_va_q=0000003fffffffff can=1 ex=1/13/0000003fffffffff vld=1
```

### 3.3 Validation of the patch on a copy

```
$ cp -R rtl rtl_fixed    # apply the diff above to rtl_fixed/cva6_mmu.sv only
$ CXXFLAGS=... verilator --binary ... -f filelist_fixed.f tb_mmu_fixed.sv -o sim_tb_fixed
$ ./obj_dir_fixed/sim_tb_fixed | grep -E 'prime|resp N|legit'
[prime ] cyc=28 hit=1 valid=1 exc.valid=0 exc.cause=0 paddr=0000403fffffff
[resp N] cyc=29 in_vaddr=0000004000000000 q_vaddr=0000003fffffffff dtlb_hit_q=1 can=0 -> exc.valid=0 exc.cause=0 tval=0000000000000000
[resp N/store] cyc=34 in_vaddr=0000004000000000 q_vaddr=0000003fffffffff dtlb_hit_q=1 can=0 -> exc.valid=0 exc.cause=0 tval=0000000000000000
[legit Np1] cyc=50 in_vaddr=0000004000000000 q_vaddr=0000004000000000 dtlb_hit_q=1 can=1 -> exc.valid=1 exc.cause=15 tval=0000004000000000
```

Spurious faults for N are gone; legal translation still completes; a genuine
non-canonical access (primed into the TLB, then hit) still faults with `tval = N+1`.

### 3.4 Even smaller alternative also validated

`rtl_fixed2/` changes only the assignment at `:542-543` to use the registered
request instead of the input:

```systemverilog
    canonical_addr_check = (lsu_req_q && en_ld_st_translation_i &&
           !((&lsu_vaddr_q[CVA6Cfg.VLEN-1:CVA6Cfg.SV-1]) == 1'b1 || (|lsu_vaddr_q[CVA6Cfg.VLEN-1:CVA6Cfg.SV-1]) == 1'b0));
```

It produces identical simulation results (spurious faults gone, legitimate fault
preserved). The registered `_n/_q` form in §2 is preferred only because it keeps the
canonicality computation on the request-cycle input, matching the style of all other
pipeline registers; both are semantics-preserving here since `canonical_addr_check`
is read only in the DTLB-hit branch.

---

## 4. Confidence and alternative hypotheses

**Confidence: high.** The defect is a textbook request/response pipeline-stage mixup:
a single combinational signal is computed from `lsu_vaddr_i`/`lsu_req_i` but read
alongside `dtlb_hit_q`/`lsu_vaddr_q`. The reproduction matches every stated symptom,
including the canonical `tval` and both tohost values (13/15), and the patch removes
the spurious faults without affecting legal translation or genuine canonical faults.

Alternatives considered and ruled out:

1. **PTW passes a stale/wrong `update_vaddr`.** `rtl/cva6_ptw.sv:155` assigns
   `update_vaddr_o = vaddr_q`, i.e. already registered from `shared_tlb_vaddr_i`
   (`:387`). The spurious fault occurs with `ptw_active = 0` and in the DTLB-hit
   branch, so the PTW error path is not involved.
2. **TLB tag/VPN aliasing or wrong page size.** The prime access hits (`dtlb_hit=1`,
   `lu_hit=1`) and yields the correct `paddr = 0x0000403f_ffff_ffff`. The patched
   RTL uses the identical TLB.
3. **PMP / access / dirty flags.** `ptw_access_exception = 0` and the prime access
   completes with no exception; the patch changes none of these signals.
4. **`tval` mux bug (e.g. picking `update_vaddr`).** The observed canonical `tval`
   is fully explained by `lsu_vaddr_q = N` at lines 634-636/662-664; `update_vaddr`
   is not used in the DTLB-hit branch.
5. **Instruction-side canonical check (`rtl/cva6_mmu.sv:399`).** It is computed and
   used within the same `always_comb`, with no registered pipeline in between, so it
   has no analogous mismatch.
6. **Pre-existing gap (not this bug):** canonicality is only checked in the DTLB-hit
   branch; a non-canonical address that misses in the TLB walks normally. The patch
   deliberately does not change this scope.

If any further evidence were needed, it would be a gate-level/VCD trace of
`lsu_vaddr_i`, `lsu_vaddr_q`, `dtlb_hit_q`, and `canonical_addr_check`, but the
cycle-by-cycle simulation above already exposes the mismatch directly.
