# Bus Protocol Detector — Design

## Goal

Auto-detect bus protocol (AXI/TL-UL/AHB/Wishbone/自定义) and identify backpressure
handshake paths from Verilog/SystemVerilog source, without hardcoding signal names.

**Hybrid approach:**
- **Phase A (Schema Match)**: Config-driven pattern match on port names → candidate modules
- **Phase B (Handshake Confirm)**: Analyze `if (v && r)` / `always @(posedge clk)` logic →
  confirm actual flow-control semantics
- **Result**: Per-signal confidence score, direction (input/output), protocol label

---

## Phase A — Protocol Schema Matching

### Schema Config Format (YAML)

```yaml
# config/protocols/axi.yaml
protocol: AXI4
variant:  # sub-protocol detection
  - AXI4_FULL
  - AXI4_LITE
  - AXI4_STREAM

channels:
  AW: # Address Write
    ports:
      - name: [awvalid, avalid] # valid signal name patterns
        dir: output
        type: valid
      - name: [awready, aready]        # ready signal name patterns
        dir: input
        type: ready
      - name: [awaddr, aw_addr, aaddr]
        dir: output
        type: addr
      - name: [awlen, aw_len, alen]
        dir: output
        type: len
      - name: [awsize, aw_size]
        dir: output
        type: size
      - name: [awburst, aw_burst]
        dir: output
        type: burst
    handshake: "valid_AND_ready" # semantic description

  W:   # Write Data
    ports:
      - name: [wvalid, w_valid, tvld]
        dir: output
        type: valid
      - name: [wready, w_ready, tready]
        dir: input
        type: ready
      - name: [wdata, w_data, tdata]
        dir: output
        type: data
      - name: [wstrb, w_strb, tstrb]
        dir: output
        type: strb
      - name: [wlast, w_last, tlast]
        dir: output
        type: last
    handshake: "valid_AND_ready"

  B:   # Write Response
    ports:
      - name: [bvalid, b_valid]
        dir: input
        type: valid
      - name: [bready, b_ready]
        dir: output
        type: ready
      - name: [bresp, b_resp]
        dir: input
        type: resp
    handshake: "valid_AND_ready"

  AR:  # Address Read
    ports:
      - name: [arvalid, ar_valid]
        dir: output
        type: valid
      - name: [arready, ar_ready]
        dir: input
        type: ready
      - name: [araddr, ar_addr]
        dir: output
        type: addr
      - name: [arlen, ar_len]
        dir: output
        type: len
    handshake: "valid_AND_ready"

  R:   # Read Data
    ports:
      - name: [rvalid, r_valid]
        dir: input
        type: valid
      - name: [rready, r_ready]
        dir: output
        type: ready
      - name: [rdata, r_data]
        dir: input
        type: data
      - name: [rlast, r_last]
        dir: input
        type: last
    handshake: "valid_AND_ready"

# Detection rule
detection:
  min_channels: 2 # require at least 2 channels to classify as AXI
  min_ports_per_channel: 2 # require at least 2 port matches per channel
  confidence_weights:
    exact_name: 1.0      # signal name exactly matches pattern
    prefix_match: 0.8 # signal name starts with pattern
    substring_match: 0.5 # pattern appears anywhere in signal name
```

```yaml
# config/protocols/tlul.yaml
protocol: TLUL
channels:
  A:   # Request channel
    ports:
      - name: [a_valid, a_valid_i]
        dir: input
        type: valid
      - name: [a_ready, a_ready_o]
        dir: output
        type: ready
      - name: [a_addr, a_addr_i]
        dir: input
        type: addr
      - name: [a_opcode, a_opcode_i]
        dir: input
        type: opcode
    handshake: "ready_THEN_valid"  # different from AXI!

  D:   # Response channel
    ports:
      - name: [d_valid, d_valid_o]
        dir: output
        type: valid
      - name: [d_ready, d_ready_i]
        dir: input
        type: ready
      - name: [d_data, d_data_o]
        dir: output
        type: data
      - name: [d_error, d_error_o]
        dir: output
        type: error
    handshake: "valid_THEN_ready" # d_valid must be stable before d_ready
```

### Schema Matching Algorithm

```
For each module M:
  For each protocol P in schemas/:
    For each channel C in P.channels:
      For each port pattern PP in C.ports:
        For each signal S in M.ports:
          score = name_match_score(S.name, PP.name)
          if score > threshold:
            record match: (channel=C, port_type=PP.type, signal=S, score=score)

    # Aggregate per channel
    channel_score[C] = avg(top-k matches for C)
    port_coverage[C] = matched_ports / total_ports_in_C

    # Aggregate per protocol
    protocol_score[P] = weighted_avg(channel_score for matched channels)

  # Select best protocol
  best_protocol = argmax(protocol_score)
  if protocol_score[best] > confidence_threshold:
    label module as: best_protocol
    extract: matched signals per channel
```

---

## Phase B — Handshake Semantic Confirmation

### Handshake Pattern Detection

**Goal**: For each (valid, ready) pair found in Phase A, verify the actual
handshake semantics by inspecting the surrounding logic.

#### Pattern 1: `if (valid && ready)` — 标准 AXI 握手

```verilog
if (awvalid && awready) begin
  // handshake happens here — addr latched on this cycle
end
```
This is the **canonical AXI handshake**. Both signals must be high simultaneously.
awvalid and awready are **both directions = flow control on THIS signal**.

#### Pattern 2: `if (ready)` — TL-UL 变体

```verilog
// TL-UL: a_ready must be stable BEFORE a_valid
if (a_ready && a_valid)  // wrong order semantically
if (a_ready) begin // a_ready is output, stable before request
  // ...
end
```

#### Pattern 3: `assign ready = !full` — 组合逻辑反压

```verilog
assign awready = !aw_fifo_full;
// ready is COMBINATIONAL output, driven by internal state
// This means FIFO水位控制awready
```

#### Pattern 4: `always @(posedge clk) ready <= ...` — 寄存器反压

```verilog
always @(posedge clk) begin
  if (!awready) aw_ready_reg <= awready;  // registered ready
end
// ready has been pipelined — adds1 cycle latency
```

### Handshake Detection Algorithm

```
For each (valid, ready) pair in candidate_handshakes:
  1. Find always blocks and assign statements that drive valid
  2. Find always blocks and assign statements that drive ready
  3. Find if/case conditions that involve both valid and ready
  4. Classify handshake type:
     - "STANDARD": if (v && r) found → AXI-style
     - "COMBINATIONAL_READY": ready is assign (no clk) → FIFO-driven
     - "REGISTERED_READY": ready is registered → pipeline delay
     - "LATCHED": valid/ready in latch logic
  5. Check direction: is valid driven by THIS module or passed through?
     - If valid is in port list with dir=output → THIS module DRIVES valid
     - If valid is in port list with dir=input  → UPSTREAM drives valid (反压终点)
```

### Cross-Validation

```
Phase A result: AXI, channel=AW, valid=awvalid, ready=awready (score=0.9)
Phase B result: handshake_type=STANDARD, if (awvalid && awready) found

→ CONFIRMED: This is AXI AW channel, standard handshake
→ Confidence = 0.9 * 0.95 = 0.855

Phase A result: AXI, channel=W, valid=wvalid, ready=wready (score=0.8)
Phase B result: handshake_type=COMBINATIONAL_READY, wready = !w_fifo_full

→ CONFIRMED + ENRICHED: AXI W channel, FIFO-based backpressure
→ Additional info: FIFO threshold can be extracted from !w_fifo_full logic
→ Confidence = 0.8 * 0.9 = 0.72
```

---

## Architecture

```
src/
  trace/
    core/
      protocol/
        __init__.py
        schema.py # SchemaLoader: load + match YAML schemas
        schema_matcher.py # Phase A logic
        handshake_detector.py  # Phase B logic
        bus_detector.py   # Main entry: run both phases, cross-validate
        configs/
          axi.yaml
          tlul.yaml
          ahb.yaml
          wishbone.yaml
```

---

## Key Data Structures

```python
@dataclass
class PortMatch:
    signal: str
    port_type: str # valid/ready/addr/data/etc
    direction: str         # input/output
    match_score: float    # 0.0-1.0
    matched_pattern: str

@dataclass
class ChannelMatch:
    channel: str           # AW/W/B/AR/R/A/D
    port_matches: list[PortMatch]
    coverage: float        # 0.0-1.0 (what fraction of expected ports matched)
    channel_score: float

@dataclass
class HandshakeInfo:
    valid_signal: str
    ready_signal: str
    handshake_type: str    # STANDARD / COMBINATIONAL_READY / REGISTERED_READY
    condition_ast: AST # the if condition node
    driver_info: str       # description of what drives valid/ready

@dataclass
class ProtocolDetectionResult:
    module: str
    protocol: str            # AXI4 / TLUL / AHB / Wishbone / UNKNOWN
    confidence: float       # 0.0-1.0
    channels: dict[str, ChannelMatch]
    handshakes: list[HandshakeInfo]
    enrichment: dict        # extra info (FIFO threshold, pipeline depth, etc)
```

---

## Implementation Phases

### Phase 1: Schema Framework (3-5 commands)
- [ ] `schema.py`: YAML loader + name matching (exact/prefix/substring)
- [ ] Write `configs/axi.yaml` (AW+W+B+AR+R channels)
- [ ] Write `configs/tlul.yaml` (A+D channels)
- [ ] `schema_matcher.py`: Score calculation per channel/protocol

### Phase 2: Handshake Detector (5-8 commands)
- [ ] `handshake_detector.py`: AST traversal for `if (v && r)` detection
- [ ] Combinational vs registered ready classification
- [ ] Direction inference (who drives what)

### Phase 3: Integration (2-3 commands)
- [ ] `bus_detector.py`: Run Phase A → Phase B → cross-validate
- [ ] Add `--protocol-detect` flag to `backpressure` command
- [ ] Output enrichment: FIFO threshold, pipeline stages, etc.

### Phase 4: More Protocols (2-3 commands)
- [ ] `configs/ahb.yaml`
- [ ] `configs/wishbone.yaml`
- [ ] Auto-protocol-detection without specifying config file