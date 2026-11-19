# Task — CVA6 MMU Sv39 spurious page-fault (issue #3404)

## Target

The design under `rtl/` is the CVA6 memory-management unit: the address
translation block together with its TLB, shared TLB, page-table walker and PMP
logic, plus a small simulation top. It is configured for **Sv39** (39-bit
virtual addresses, three translation levels). `filelist.f` lists everything
needed to build it.

## Symptom

Under Sv39 translation, the following sequence reproduces the bug:

1. A legal memory access is made at virtual address **N**; it translates and
   completes normally.
2. A subsequent access is made at virtual address **N+1**, whose upper bits do
   not match the sign extension of bit 38 — i.e. it is a **non-canonical**
   address.
3. After this sequence, the earlier access **N** is reported as a
   `LOAD_PAGE_FAULT` or `STORE_PAGE_FAULT`, even though N is itself legal and
   fully translated.
4. The fault's `tval` is observed to hold a **canonical** address, rather than
   the non-canonical address that was supplied.

## Reproduction evidence

- With the bundled top-level harness, the pre-fix `tohost` signature values
  **13** and **15** are observed for the two failing cases.
- A tandem run against the Spike reference model **passes**: Spike does not
  raise the fault, which confirms that the report on the CVA6 side is spurious
  and not a genuine architectural fault.

## Objective

Locate the RTL defect responsible for this spurious fault and produce a minimal,
semantics-preserving correction. Keep the change local and ensure that all other
legal and illegal translation cases continue to behave correctly.
