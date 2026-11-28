# P194.5m — SERV `bit_mapping` violation triage

**Status**: triage complete; **tool false positive**, not an RTL bug.
**Project**: SERV `/tmp/serv.f` (25 files), 2026-11-28.
**Command**: `verify consistency --checks bit --filelist /tmp/serv.f --json` on a fresh cache.

## Result

```text
total_violations = 4
kind = parent_range_out_of_bounds
nodes:
  serv_rf_top.rdata0[1:1]        parent_range [0,0]
  serv_rf_top.rdata1[0:1]        parent_range [0,0]
  serv_synth_wrapper.rdata0[1:1] parent_range [0,0]
  serv_synth_wrapper.rdata1[0:1] parent_range [0,0]
```

## Source evidence

```verilog
// serv_rf_top.v
wire [W-1:0] rdata0;   // W default 1 -> 1 bit at the top
wire [W-1:0] rdata1;
```

```verilog
// serv_rf_ram_if.v
reg [width-1:0] rdata0;        // width = RF_WIDTH = 2 at this instance
reg [width-1-W:0] rdata1;
...
rdata0 <= {{W{1'b0}}, rdata0[width-1:W]};   // bit [1:1] is valid here
rdata1 <= ... rdata1[width-W-1:W] ...;
```

The graph contains the correct nested nodes:

```text
serv_rf_top.rf_ram_if.rdata0      width (1,0)  (2 bits)
serv_rf_top.rf_ram_if.rdata0[1:1] valid child
```

It also contains **top-anchored** bit nodes such as
`serv_rf_top.rdata0[1:1]`, which are artifacts of the hierarchical
bit-select walker prefixing nested selects with the top instance path.
The top `rdata0` is only 1 bit, so the checker flags the artifact.

## Conclusion

- RTL is valid; the `W=1` top net is not indexed at bit 1.
- The 4 violations are a **tool false positive** from nested bit-select
  parent-path scoping.
- Workaround: `verify consistency --checks reciprocity,connection` for SERV,
  or ignore these four nodes until the walker is fixed.

## Follow-up

Tracked as **P194.5.17**: hierarchy-aware bit-select walker must anchor
nested selects under their elaborated instance path (`...rf_ram_if.rdata0`),
not the top module prefix. A regression must reproduce SERV's
`rdata0[1:1]` without requiring the external checkout.
