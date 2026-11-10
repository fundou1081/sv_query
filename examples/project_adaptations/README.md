# Project adaptations (outside core)

This directory is for **project-specific** semantic adapters.  They are not
imported by `src/trace` and are never applied automatically.

Contract:

```json
{
  "adapter": "opentitan-i2c-fifo",
  "project": "opentitan",
  "version": "0.1",
  "boundaries": [
    {
      "src": "i2c.i2c_core.u_fifos.fmt_fifo_wdata_i[12]",
      "dst": "i2c.i2c_core.u_fifos.fmt_fifo_rdata_o[12]",
      "kind": "fifo_state",
      "evidence": "hw/ip/i2c/rtl/i2c_fifos.sv:100,104 (explicit port assertion)",
      "confidence": "medium"
    }
  ]
}
```

Adapters must:

- emit explicit canonical signal pairs;
- include source evidence;
- mark confidence;
- be invoked explicitly, never discovered by name at build time;
- not modify RTL/project files.

Core provides only generic graph primitives; project names do not belong in
`src/trace`.
