# Worked examples from the task corpora

> Values below were reproduced on 2026-11-15 where noted. Frozen ground truth can
> drift with graph semantics; always rerun and report the current shape.

## Short: direct neighbors (P115 / long_range)

```bash
sv_query drivers picorv32_axi.axi_adapter.mem_rdata[16] \
  -f picorv32.v --depth 1 --json -q
# result.signals[0].driver_count == 1; precision=bit; coarse_fallback=false

sv_query loads picorv32_axi.axi_adapter.mem_valid \
  -f picorv32.v --depth 1 --json -q
# current local replay: 6 direct loads; count=6, truncated=false

sv_query paths picorv32_axi.axi_adapter.mem_axi_bvalid \
  picorv32_axi.axi_adapter.mem_valid --directed --canonical -f picorv32.v --json -q
# found=true; hop_count=12 (directed). Undirected would be misleading.
```

## Short: negative answer

```bash
sv_query paths picorv32_axi.axi_adapter.mem_axi_awvalid \
  picorv32_axi.axi_adapter.mem_valid --directed -f picorv32.v --json -q
# ok:true, found:false — this is a valid negative fact, not an error.
```

## Short: AXI after prune + snapshot

```bash
sv_query filelist prune --filelist axi.f --top axi_adapter --output ax.f --apply --json -q
sv_query snapshot save axi_adapter.sv --filelist ax.f --tag axi --json -q

sv_query drivers axi_adapter.s_axi_awready --from-snapshot axi --depth 1 --json -q
# drivers=1, loads=0 (replayed)
sv_query loads axi_adapter.s_axi_rready --from-snapshot axi --depth 1 --json -q
# drivers=0, loads=1
```

## Short: OpenTitan UART neighbors

```bash
sv_query drivers uart.u_reg.intr_test_qe --from-snapshot uart --depth 1 --json -q
sv_query loads   uart.u_reg.intr_test_qe --from-snapshot uart --depth 1 --json -q
# current: 1 driver, 9 loads; frozen expected had 2 drivers — report current.
```

## Short: verify claims

```bash
sv_query verify claim \
  --claim '{"type":"driver","signal":"i2c.i2c_core.scl_out_fsm","driver":"i2c.cio_scl_en_o"}' \
  --from-snapshot i2c --json -q
# status=contradicted (directness matters; do not substitute transitive path)

sv_query verify claim \
  --claim '{"type":"path","from":"uart.uart_core.nonexistent_sig","to":"uart.uart_core.rx_val_q"}' \
  --from-snapshot uart --json -q
# status=unknown; report unknown, not false.
```

## Long: 4+ round debug chain

```bash
# 1. scope
sv_query instances --from-snapshot deep --json -q

# 2. path
sv_query paths top.din top.dout --directed --canonical --from-snapshot deep --json -q

# 3. mux sink neighbors
sv_query drivers top.u_mid.u_leaf.d --from-snapshot deep --depth 1 --json -q

# 4. conditions
sv_query controlflow analyze top.u_mid.u_leaf.d --filelist deep_chain.sv --json -q

# 5. source evidence
sv_query trace evidence top.u_mid.u_leaf.d --filelist deep_chain.sv --json -q
```

Current canonical path is 10 hops (11 nodes); older ground truth expected 11 hops
including a ternary node. The ternary is a control edge, not a data path (see
[pitfalls.md](pitfalls.md)). Report the current canonical result and the semantic
reason for the difference.

## Long: class/constraint chain

```bash
sv_query class pkt --relations --filelist rand_coverage.sv --json -q
sv_query trace constraints top.e.p.len --filelist rand_coverage.sv --json -q
sv_query trace constraint-chain top.e.p.addr top.e.p.len \
  --filelist rand_coverage.sv --json -q
```

Use instance-qualified members, and state that constraint links are declared
co-membership, not SAT proof.
