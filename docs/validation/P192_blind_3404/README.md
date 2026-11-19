# Blind reproduction package — P192.1 / issue #3404

This directory is a self-contained, **symptom-only** reproduction package for
the CVA6 Sv39 page-fault task described in `TASK.md`. It is intended to be handed
to a blind solver in a later step (P192.2).

## Contents

- `rtl/` — unmodified pre-fix CVA6 MMU RTL: the address-translation module
  (`cva6_mmu`), TLB, shared TLB, page-table walker, PMP, leading packages, helper
  units, and the simulation top; plus `rtl/include/` with the configuration and
  RISC-V/CVA6 package headers.
- `filelist.f` — portable file list; every path is relative to this directory.
- `TASK.md` — symptom-only problem statement (no answer, no upstream history).
- `meta/LICENSE_CVA6` — upstream license for the CVA6 sources.

## Build / smoke check

From the repository root:

    python3 run_cli.py stats --filelist docs/validation/P192_blind_3404/filelist.f --json

The command must report `ok=true`.

## Blind protocol

- Do **not** look up the upstream fix commit, diff, or any post-fix source for
  this issue.
- Do **not** read prior validation reports, value-case notes, follow-up notes,
  or handoff records concerning this issue.
- Do **not** query the tool for a known-answer signal name; derive the diagnosis
  only from `rtl/`, `filelist.f` and `TASK.md`.
- No fix diff and no root-cause explanation are included in this package.

## Integrity note

A package-wide scan for the upstream fix commit identifier must come back empty:

```bash
grep -RIn '47b72e31' docs/validation/P192_blind_3404   # empty
```

Narrative files (`TASK.md`, `README.md`, `filelist.f`) must not contain fix
signals or root-cause text. The RTL is the unmodified pre-fix source; as such it
necessarily contains ordinary registered request/address signals, which are
part of the baseline design and are not fix content.

Verified locally:

```text
47b72e31:       absent package-wide
narrative scan: clean (ordinary word "fix" only means "do not look up fix")
TASK/README:    no lsu_req_q / lsu_vaddr_q / _i->_q answer
stats:          ok=true, 10715 nodes
cva6_mmu.sv:    byte-identical to C1 parent
```
