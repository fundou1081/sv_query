# Width convention — P195.3

> **Status**: applied to port/variable width extraction and user-facing output.
> **Date**: 2026-11-22

## Canonical scalar

A one-bit scalar is represented as:

```text
width = (0, 0)   # msb=0, lsb=0
```

Rendered width is:

```text
max(0, msb - lsb + 1) = 1
```

`(1, 0)` is **not** the scalar sentinel: it means an actual `[1:0]` two-bit
range (or an explicit unknown/fallback in older extraction paths).

## User-facing fields

- `graph nodes --detail`: `"width": [0,0]` for a scalar;
- `drivers`: `width_msb=0`, `width_lsb=0`, `width=1`;
- `trace profile`: `width=[0,0]`, consistent with `type.bit_width=1`.

A two-bit `[1:0]` port still reports `[1,0]` / `width=2`.

## Scope

P195.3 updates scalar extraction in `ports_ifaces.py` and `exprs_drivers.py`,
and connection-extractor handling of missing vs scalar port widths. It does not
redesign every internal width fallback; those remain explicitly unknown until
extracted.
