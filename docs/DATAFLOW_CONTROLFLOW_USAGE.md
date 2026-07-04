# Designer Workflow: 看 A→B 的 Dataflow + Controlflow

**Audience**: RTL designer / verification engineer 接手新 RTL 项目时, 想看 signal A 到 signal B 的数据流跟 if/case 条件.

**Status**: 当前用 3 命令组合 (A 方案). 需要时升级到 1 复合命令 (B 方案).

**Last updated**: 2026-07-04

---

## 🎯 这个 doc 解决什么问题

新人接手 RTL 项目 (e.g. CPU core, bus, FIFO), 最常问的 3 个问题:

1. **"signal A 到 signal B 怎么连?"** (dataflow)
2. **"中间过哪些 if/case 条件?"** (controlflow)
3. **"这段 path 几个 cycle 延迟?"** (latency)

传统方法: 读 always_ff + grep if/case, 5-10 min/段.

**A 方案**: 3 命令组合, 30s 看 1 段. **10x 加速**.

---

## 🚀 Quick Start (3 命令组合)

### 场景: 看 `A` → `B` 的 dataflow + if/case + 源码

```bash
# 1️⃣ dataflow: 找 A→B 路径 + segments + latency
sv_query -q dataflow analyze A B --no-strict --file x.sv --json
# 输出: latency_cycles, primary_is_async, paths[].segments[], 每个 segment 含 condition

# 2️⃣ controlflow: 看 A 跟 B 的 if/case 条件
sv_query -q controlflow analyze A --no-strict --file x.sv --json
sv_query -q controlflow analyze B --no-strict --file x.sv --json
# 输出: conditioned_drivers[].conditions[].expr (e.g. "push_i && !full_o")

# 3️⃣ evidence: 拿 A 或 B 所在 always/if 源码
sv_query -q trace evidence B --no-strict --file x.sv --json
# 输出: source_location (line), enclosing_if, enclosing_always, source_text
```

### 跑 1 段: 12 命令, ~30s

> 1 个 dataflow + 2 个 controlflow (A + B) + 1 个 evidence = 4 命令/段
> 跑 3 段 (e.g. CPU 5-stage IF/ID/EX) = 12 命令, ~30s

---

## 📊 Step-by-step 例子: darkriscv 5-stage RISC-V

**目标**: 看 4 段 pipeline 路径, 找 IF/ID/EX stage 的 if/case 条件.

### 输入

```bash
DARKRISCV=~/my_dv_proj/darkriscv/rtl/darkriscv.v
```

### 段 1: IF stage - PC 怎么输出

```bash
sv_query -q dataflow analyze darkriscv.IFPC darkriscv.IADDR \
  --no-strict --file $DARKRISCV --json | jq '.result | {latency: .primary_latency_cycles, async: .primary_is_async, note: .paths[0].latency_note, segments: [.paths[0].segments[] | {from: .from_signal, to: .to_signal, condition}]}'
```

**实际输出**:
```json
{
  "latency": 0,
  "async": false,
  "note": "no register boundary (combinational only)",
  "segments": [{"from": "darkriscv.IFPC", "to": "darkriscv.IADDR", "condition": ""}]
}
```

**结论**: PC → 地址输出是 **combinational** (0 cycle), 不是 1 cycle. **没 if 条件** (assign).

### 段 2: ID stage - 指令怎么到 ID reg

```bash
sv_query -q dataflow analyze darkriscv.IDATA1 darkriscv.IDATA2 \
  --no-strict --file $DARKRISCV --json | jq '.result | {latency: .primary_latency_cycles, segments: [.paths[0].segments[] | {from: .from_signal[-15:], to: .to_signal[-15:], condition}]}'
```

**实际输出**:
```json
{
  "latency": 1,
  "segments": [{"from": "darkriscv.IDATA1", "to": "darkriscv.IDATA2", "condition": "HLT2^HLT"}]
}
```

```bash
# controlflow 找 B 的 if 条件
sv_query -q controlflow analyze darkriscv.IDATA2 \
  --no-strict --file $DARKRISCV --json | jq '.result.conditioned_drivers[].conditions[].expr'
# 输出: "HLT2^HLT" (重复 2 次)
```

```bash
# evidence 拿源码
sv_query -q trace evidence darkriscv.IDATA2 \
  --no-strict --file $DARKRISCV --json | jq '.result.signals[0].evidence | {line: .source_location.line_start, if: .enclosing_if.text, always: .enclosing_always.text}'
```

**实际输出**:
```json
{
  "line": 178,
  "if": "if(HLT2^HLT) IDATA2 <= IDATA1;",
  "always": "(none)"
}
```

**结论**: ID stage 关键 if 是 **`HLT2 XOR HLT`** (halt 同步). 1 cycle latency.

### 段 3: EX stage - 怎么到 EX reg

```bash
sv_query -q dataflow analyze darkriscv.IDATA2 darkriscv.XIDATA \
  --no-strict --file $DARKRISCV --json | jq '.result | {latency: .primary_latency_cycles, segs: [.paths[0].segments[] | {from: .from_signal[-15:], to: .to_signal[-15:]}]}'
```

**实际输出**:
```json
{
  "latency": 1,
  "segs": [
    {"from": "darkriscv.IDATA2", "to": "darkriscv.IDATAX"},
    {"from": "darkriscv.IDATAX", "to": "darkriscv.XIDATA"}
  ]
}
```

**结论**: EX stage 内部 2 segments, 中间 signal `IDATAX`. 1 cycle latency.

### 段 4: 跨 stage 不可达 (真信息)

```bash
sv_query -q dataflow analyze darkriscv.IFPC darkriscv.IDATA2 \
  --no-strict --file $DARKRISCV --json | jq '.result.is_reachable'
# 输出: false
```

**结论**: PC 跟 inst 走**不同 data flow** (PC 走 IF → IADDR → 外部 memory; inst 从 IDATA input 回来). **designer 用此确认 stage 边界**, 不是 bug.

---

## 📚 4 命令 output schema 详解

### `dataflow analyze A B`

```json
{
  "result": {
    "is_reachable": true,
    "paths_count": 3,
    "primary_latency_cycles": 1,         // 关键: 几 cycle 延迟
    "primary_is_async": false,            // 关键: 是否跨 clk
    "intermediate_signals": [...],
    "all_conditions": [...],
    "clock_domain": "clk_i",
    "timing_risk": "safe",
    "paths": [
      {
        "path_id": 0,
        "segments": [
          {
            "from_signal": "darkriscv.IDATA1",
            "to_signal": "darkriscv.IDATA2",
            "driver": "IDATA1",            // 驱动表达式
            "condition": "HLT2^HLT",       // 关键: if 条件
            "timing": "clk_i",
            "assign_type": "nonblocking",
            "distance": 1
          }
        ],
        "distance": 1,
        "latency_cycles": 1,
        "is_async_crossing": false,
        "latency_note": "1 sync stages (cycle latency)",
        "stage_breakdown": [...]           // 复用 detect_pipeline, 标 stage_id
      }
    ]
  }
}
```

**关键字段**:
- `primary_latency_cycles`: 主路径 cycle 数. 异步返 `null`.
- `primary_is_async`: 是否跨 clk.
- `paths[].segments[].condition`: **每个 segment 的 if 条件** (e.g. "HLT2^HLT", "push_i && !full_o")
- `paths[].latency_note`: "N sync stages" / "no register boundary" / "async crossing"

### `controlflow analyze <sig>`

```json
{
  "result": {
    "signal": "darkriscv.IDATA2",
    "conditioned_drivers": [
      {
        "to_node": "darkriscv.IDATA2",
        "conditions": [
          {
            "expr": "HLT2^HLT",           // 关键: if 表达式
            "edge": {
              "src": "darkriscv.clk_i",
              "dst": "darkriscv.IDATA2",
              "kind": "CLOCK",
              "condition": "HLT2^HLT"
            }
          }
        ]
      }
    ]
  }
}
```

**关键字段**:
- `conditioned_drivers[]`: 这个 signal 的所有条件驱动
- `conditions[].expr`: **if/case 表达式文本**
- `conditions[].edge.condition`: 边上的条件 (与 expr 一致)

### `trace evidence <sig>`

```json
{
  "result": {
    "signals": [
      {
        "evidence": {
          "source_location": {
            "file": "...",
            "line_start": 178,
            "line_end": 178,
            "column": 9
          },
          "enclosing_if": {                // 注意: 是 dict, 不是 str
            "file": "...",
            "line_start": 178,
            "text": "if(HLT2^HLT) IDATA2 <= IDATA1;"
          },
          "enclosing_always": {
            "file": "...",
            "line_start": 174,
            "text": "always @(posedge CLK or negedge RES) begin\n  HLT2 <= HLT; ... if(HLT2^HLT) IDATA2 <= IDATA1; ..."
          }
        }
      }
    ]
  }
}
```

**关键字段**:
- `source_location.line_start`: **源码行号**
- `enclosing_if.text`: **if 表达式源码**
- `enclosing_always.text`: 整个 always block 源码 (含 if 嵌套)

---

## 🎯 真实使用场景

### 场景 1: 接手新 CPU, 看 5-stage pipeline
- 跑 4-5 段: PC → IF_reg → ID_reg → EX_reg → MEM_reg → WB
- 找每段的 if 条件 (stall, flush, branch)
- 看 if/case 是否合理
- **时间**: 5 min (vs 30 min 读代码)

### 场景 2: 改一个 signal 之前
- 跑 `dataflow impact <sig>` 看影响范围
- 跑 `dataflow analyze <sig> <destination>` 看具体 path
- 跑 `controlflow` 找 if 条件 (改了条件要改哪里)
- 跑 `evidence` 确认源码位置
- **时间**: 1 min/段

### 场景 3: 写 SVA 之前
- 找关键 signal 路径
- 看 if 条件 (SVA 要覆盖所有 if 分支)
- 跑 `risk analyze` 排高风险 signal 优先
- **时间**: 5 min/段

### 场景 4: 找 CDC 风险
- 跑 `dataflow analyze` 跨 clk signal
- 看 `is_async_crossing=true` 自动标
- 找哪些路径没 synchronizer
- **时间**: 1 min/段

---

## ⚠️ 限制 (诚实)

1. **`dataflow analyze A B` 的 `condition` 字段**: 是驱动条件 (e.g. `push_i && !full_o`), 跟"if 嵌套"不同. 复杂嵌套 if (e.g. `if (a) begin if (b) c = d; end`) 看不到 b.
2. **`controlflow analyze <sig>` 只看单 signal**, 不看 A→B path. 需要对 path 上每个 signal 各跑一次.
3. **跨 stage 不可达是**真信息, designer 要能理解 (e.g. PC 跟 inst 走不同 path).
4. **`enclosing_always` 是 dict** (含 file/line/text), 不是简单 string. 提取源码用 `.text` 字段.
5. **大项目 (CVA6 137K 行)**: filelist 不全会报"missing submodule" warnings, 跑慢 (~10-15s), 但仍能用 --no-strict.
6. **pyslang 内存敏感**: 200K+ 行项目在 8GB MBA 上可能 OOM. 建议每个 CPU core 跑一次, 不要一次跑整个 SoC.

---

## 🚀 高级用法

### 批量跑多段 (shell loop)

```bash
# 跑 CPU 5 stage pipeline 5 段
DARKRISCV=~/my_dv_proj/darkriscv/rtl/darkriscv.v
for seg in "IFPC IADDR" "IDATA1 IDATA2" "IDATA2 XIDATA" "XIDATA REGS[0]"; do
  set -- $seg
  echo "=== $1 → $2 ==="
  sv_query -q dataflow analyze darkriscv.$1 darkriscv.$2 \
    --no-strict --file $DARKRISCV --json | \
    jq '.result | {lat: .primary_latency_cycles, async: .primary_is_async, segs: [.paths[0].segments[] | {from: .from_signal[-20:], to: .to_signal[-20:], cond: .condition}]}'
done
```

### 跑 1 段全 pipeline (3 命令串起来)

```bash
run_path() {
  local A=$1 B=$2 FILE=$3
  echo "=== $A → $B ==="
  echo "  [dataflow]"
  sv_query -q dataflow analyze $A $B --no-strict --file $FILE --json | \
    jq -r '.result | "  latency=\(.primary_latency_cycles) async=\(.primary_is_async) | \(.paths[0].latency_note)"'
  echo "  [controlflow B]"
  sv_query -q controlflow analyze $B --no-strict --file $FILE --json | \
    jq -r '.result.conditioned_drivers[]?.conditions[]?.expr' | head -3 | sed 's/^/    if: /'
  echo "  [evidence B]"
  sv_query -q trace evidence $B --no-strict --file $FILE --json | \
    jq -r '.result.signals[0].evidence | "    line \(.source_location.line_start): \(.enclosing_if.text // "(no if)")"'
}

run_path "darkriscv.IFPC" "darkriscv.IDATA2" "~/my_dv_proj/darkriscv/rtl/darkriscv.v"
```

### 用 LLM 批量分析 (LLM-friendly schema)

`dataflow analyze` 的 JSON output 已经是 LLM-friendly:

```json
{
  "primary_latency_cycles": 1,
  "primary_is_async": false,
  "latency_note": "1 sync stages (cycle latency)",
  "paths": [{
    "segments": [{
      "from_signal": "...",
      "to_signal": "...",
      "condition": "HLT2^HLT"  // LLM 看得懂
    }]
  }]
}
```

LLM 可以直接:
- 解释: "从 A 到 B 经过 1 cycle, 中间条件是 HLT2^HLT"
- 提 SVA: "always @(posedge clk) if (HLT2^HLT) IDATA2 == IDATA1"
- 找 bug: "HLT2^HLT 是 XOR, 但 HLT 持续 1 cycle, 漏 cycle"

---

## 🔄 何时升级到 B 复合命令

**当前 A 方案够用**, 但**升级触发点**:

| 场景 | 命令数 | 升级建议 |
|------|--------|----------|
| 偶尔看 1 段 | 4 命令 | 不用升级 |
| 看 5 段 (1 CPU stage) | 20 命令 | 考虑 B |
| 看 25 段 (5 stage × 5 path) | 100 命令 | **B 必须** |
| 每次 review 都看 1 段 | 4 命令/次 | 考虑 B |

**B 复合命令** (计划中, 1h):
```bash
sv_query -q dataflow-controlflow analyze A B --no-strict --file x.sv --json
```
输出 1 个 JSON 含 path + latency + 所有 if/case + 源码. 不用 3 命令 join.

**C 复合命令** (B + evidence, 2h): 加 evidence 源码, 不用额外跑.

如果你**经常**跑 A→B 路径, 1 周跑 10+ 次, 升级 B 1h 值得. 否则 A 够用.

---

## 📚 相关 doc

- `docs/CONTROL_FLOW_ANALYSIS.md` - controlflow 详细原理
- `docs/DATAFLOW_ANALYSIS_ARCHITECTURE.md` - dataflow 架构
- `docs/CDC_ANALYSIS.md` - 跨 clk 检测
- `docs/CONTROL_FLOW_DESIGN.md` - controlflow 设计意图
- `sim/tests/integration/test_dataflow_latency_open_source.py` - 13 tests + 1 golden (金标准验证)

---

## 🪞 真实使用反馈

实测 darkriscv 5-stage RISC-V 4 段:
- 4 path × 3 命令 = 12 命令, **~30s**
- 关键 if 条件 (`HLT2^HLT`) 自动识别
- EX stage 内部 2 segments (via IDATAX) 完整追踪
- 跨 stage 不可达是**真信息** (PC 跟 inst 走不同 path)

**对比传统读代码**: 4 段 5-10 min/段 = 20-40 min vs 30s = **40-80x 加速**.

**限制**: 复杂嵌套 if 不能完整还原, 大项目 OOM, 跨 stage 不可达需要 designer 理解.

---

## 📅 维护

- 创建: 2026-07-04 (A 方案实跑 darkriscv 验证后)
- 更新: 升级到 B 复合命令时
- 反馈: 跑更多真项目 (OpenTitan / CVA6 / vortex) 后, 加案例

---

**TL;DR**: 跑 A→B 用 3 命令 (`dataflow` + `controlflow` + `evidence`), 30s 看 1 段完整 dataflow + if/case + 源码. 比读代码快 10-80x.
