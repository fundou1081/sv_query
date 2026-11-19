# P187 CVA6 experiment archive (2026-11-19)

> **Purpose**: keep the complete local evidence bundle for the CVA6 historical bug
> comparison. This directory is a validation artifact, not product source.
> **Main report**: [../P187_VALUE_CASES_CVA6_2026-11-19.md](../P187_VALUE_CASES_CVA6_2026-11-19.md)
> **CVA6 source**: historical blobs from `https://github.com/openhwgroup/cva6`;
> see [meta/commits.txt](meta/commits.txt) and [meta/LICENSE_CVA6](meta/LICENSE_CVA6).

## Layout

```text
case1/                 C1 (47b72e31) parent/fix source + includes + harness
case2/                 C2 (378ed3bc) parent/fix source + includes + harness
fl_c1_parent.f         portable filelist for C1 parent
fl_c1_fix.f            portable filelist for C1 fix
fl_c2_parent.f         portable filelist for C2 parent
fl_c2_fix.f            portable filelist for C2 fix
scripts/run_all.py     measured driver/dataflow/profile matrix
scripts/run_bit.py     C2 bit-select drill-down
results/               captured JSON / stderr / timing summary
meta/                  commit hashes + upstream license
```

The filelists are relative to this directory; no `/tmp` paths are required.

## Reproduce

From the `sv_query` repository root:

```bash
B=docs/validation/p187_cva6_2026-11-19
python3 run_cli.py stats --filelist "$B/fl_c1_parent.f" --json
python3 run_cli.py drivers p187_mmu_top.u_mmu.canonical_addr_check \
  --filelist "$B/fl_c1_parent.f" --json --evidence
python3 run_cli.py graph nodes --filelist "$B/fl_c2_parent.f" \
  --match lsu_dtlb_ppn_o --json
python3 "$B/scripts/run_all.py"
```

Expected historical signals:

```text
C1 parent driver: lsu_req_i / lsu_vaddr_i
C1 fix driver:    lsu_req_q / lsu_vaddr_q
C2 parent bit nodes: [PPNWMin:12] and shifted PPN slice
C2 fix bit nodes:    [0:MegaPageSubstWidth] and [PPNWMin - 12:0]
```

## Caveats

- The harness `p187_mmu_top.sv` is explicitly **not historical**; it supplies a
  concrete top and stub interface types so the historical `cva6_mmu.sv` blob can
  elaborate without the full CVA6 vendor tree.
- The static source is historical, but no dynamic Verilator/Spike oracle was
  rerun locally. The oracle is the upstream fix diff (plus the issue description
  for C1).
- This is a non-blind case study: cases were selected from fix commits, and query
  targets were chosen from the fix diff. It does not measure discovery rate.
- C2 bus-level queries miss the bit-select defects; the report records that
  limitation honestly.

## License

CVA6 source files retain their upstream headers. The upstream license is copied
to [meta/LICENSE_CVA6](meta/LICENSE_CVA6); see the CVA6 repository for the
authoritative license text.
