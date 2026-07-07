# Signal Tracing 实战案例 (openwifi-hw PHY)

> **场景**: 真实工业 Wi-Fi OFDM PHY 上跑 sv_query `trace` + `visualize` 命令, 看 signal tracing 比 `arch` 多给什么设计 insight.
> 
> **项目**: [open-sdr/openwifi-hw](https://github.com/open-sdr/openwifi-hw) — Linux mac80211 compatible full-stack IEEE 802.11/Wi-Fi design based on SDR (Software Defined Radio). 包含 **openofdm_tx** (TX 802.11 OFDM PHY) + **xpu** (low-MAC CSMA/CA) + **rx_intf** (RX interface) + **side_ch**.
> 
> **关键 insight**: sv_query `trace` + `visualize` 给出 **dataflow + signal classification + pipeline timing**, 而 `arch` 只给 **static structure**. 真正的设计理解需要两者结合.

---

## 为什么 PHY 是好测试场景

Wi-Fi OFDM PHY 比普通 CPU 更 deep:
- 6-stage IFFT pipeline (radix-2/4 butterfly)
- 3 个 FIFO (CP / bits_enc / pkt)  
- 4 个 training ROMs (l_stf / l_ltf / ht_stf / ht_ltf)
- Cross-module port connections 147+

直接看 `arch` 输出, 知道**有这些模块**, 但**数据怎么流** / **信号怎么同步** / **pipeline 多少 stage** 都看不到. 走 `trace` + `visualize` 才能真理解设计.

---

## 0. 准备: filelist + timescale fix

openwifi-hw 的 .v 文件 **缺 timescale** (22/25), 跑前先 fix:

```bash
# 1. 复制 .v 到独立目录 (不动原文件)
mkdir -p /tmp/ofdm_tx_fixed
cp ~/my_dv_proj/openwifi-hw/ip/openofdm_tx/src/*.v /tmp/ofdm_tx_fixed/

# 2. 自动修复 timescale
sv_query fix timescale --filelist /tmp/ofdm_tx_fix.f --apply
# → 22 fixed, 0 skipped

# 3. 跑 filelist (25 files + openofdm_tx + helpers)
cat > /tmp/ofdm_tx_fixed.f << 'EOF'
+incdir+/tmp/ofdm_tx_fixed
EOF
for f in /tmp/ofdm_tx_fixed/*.v; do echo "$f" >> /tmp/ofdm_tx_fixed.f; done

# 4. 释放内存 (避免 pyslang OOM 假阳性)
python3 -c "import time; a = bytearray(4 * 1024**3); time.sleep(2); del a"
```

---

## 1. `arch` 在 openofdm_tx 上跑 — 静态结构

```bash
sv_query arch show --filelist /tmp/ofdm_tx_fixed.f --target openofdm_tx \
    --depth 5 --no-strict --format summary
```

**输出**:
```
Total instances:  31
Hierarchy depth:  4 levels
Port connections: 147 (cross-module)

Top module types:
  convround          6   ← radix-2 butterfly rounding
  fftstage           4   ← IFFT radix-2 stages (64→32→16→8)
  axi_fifo_bram      3   ← CP FIFO + bits_enc FIFO + pkt FIFO
  dpram              3   ← internal RAM
  dot11_tx           1   ← main TX pipeline
```

**但是 arch 没告诉你**:
- 数据从哪进, 哪出 (dataflow)
- 哪些信号是 clock / control / data (classification)
- pipeline 多少 stage, 多少 cycle latency (timing)
- signal purpose (是 CP prefix? 还是训练序列?)

![openofdm_tx Architecture](images/openwifi_arch_openofdm_tx.png)

---

## 2. `trace fanout` — 信号往哪流

### 2.1 数据输入: i_sample (32-bit IQ sample)

```bash
sv_query trace fanout ifftmain.i_sample \
    --filelist /tmp/ofdm_tx_fixed.f --no-strict --human --depth 4
```

**输出** (单条链):
```
signal 1/1: ifftmain.i_sample
Fanout of ifftmain.i_sample
  ifftmain.i_sample → ifftmain.stage_64.i_data
                    → fftstage.i_data
                    → fftstage.imem[Expression(ExpressionKind.NamedValue)]
                    → fftstage.ib_a
                    → fftstage.ib_b
```

**洞察**: 数据从 `i_sample` 进入 stage_64, 写到 internal memory (`imem`), 然后 `ib_a` / `ib_b` 是 butterfly 的两个 input.

### 2.2 时钟使能: i_ce (clock enable) — 看广播范围

```bash
sv_query trace fanout ifftmain.i_ce \
    --filelist /tmp/ofdm_tx_fixed.f --no-strict --human --depth 4
```

**输出** (树状):
```
signal 1/1: ifftmain.i_ce
Fanout of ifftmain.i_ce
|-- ifftmain.stage_64.i_ce → fftstage.i_ce
|-- ifftmain.stage_32.i_ce
|-- ifftmain.stage_16.i_ce
|-- ifftmain.stage_8.i_ce
|-- ifftmain.stage_4.i_ce → qtrstage.i_ce
```

**洞察**: `i_ce` 广播到 6 个 FFT stages. 同步控制 (sync control) — 6 stages 同时 enable / disable.

### 2.3 时钟: i_clk — 看所有 reg

```bash
sv_query trace fanout ifftmain.i_clk \
    --filelist /tmp/ofdm_tx_fixed.f --no-strict --human --depth 3 \
    --include-clock
```

**输出** (部分):
```
signal 1/1: ifftmain.i_clk
Fanout of ifftmain.i_clk
|-- ifftmain.r_br_started (reset reg)
|-- ifftmain.br_start (combinational from r_br_started)
|-- ifftmain.o_sync (output reg)
|-- ifftmain.o_result (output reg)
|-- ifftmain.stage_64.i_clk → fftstage.i_clk
|-- ifftmain.stage_32.i_clk
|-- ... (all 6 stages + qtrstage + revstage)
|-- ifftmain.stage_4.do_rnd_sum_r.i_clk
```

**洞察**: `i_clk` 跑到 39+ 个 register (output reg + 6 stages × butterfly subregs). 这就是 pipeline 寄存器的总数.

### 2.4 输出: o_result — fanin 看来源

```bash
sv_query trace fanin ifftmain.o_result \
    --filelist /tmp/ofdm_tx_fixed.f --no-strict --human --depth 3
```

**输出**:
```
signal 1/1: ifftmain.o_result
Fanin of ifftmain.o_result
  ifftmain.revstage.o_out → ifftmain.br_result → ifftmain.o_result
```

**洞察**: 输出从 **bit-reverse stage** 出来 → 进 `br_result` (中间 wire) → 写到 `o_result` reg. 确认 IFFT pipeline 最后一步是 bit-reversal (802.11 OFDM 必需, 因为 IFFT 算法输出的顺序是 bit-reversed).

---

## 3. `visualize pipeline` — 自动 pipeline detection

```bash
sv_query visualize pipeline \
    --filelist /tmp/ofdm_tx_fixed.f --module ifftmain --no-strict \
    --dot /tmp/ifft_pipeline.dot
dot -Tpng /tmp/ifft_pipeline.dot -o docs/images/openwifi_ifft_pipeline.png
```

**输出 (metadata)**:
```
Pipeline regs: 39
Control regs: 7
State regs: 5
Stages: 39
✓ DOT: /tmp/ifft_pipeline.dot
```

**洞察**:
- **39 个 pipeline registers** — 6 stages × (butterfly input/output/working) ≈ 6×6=36 + output registers
- **7 个 control registers** — `i_ce` / `i_sync` 同步, fifo_turn 等 state
- **5 个 state registers** — bit-reversal 启动状态机

**Pipeline 流图**:

![ifftmain Pipeline](images/openwifi_ifft_pipeline.png)

- **左→右**布局 = 时间流方向
- 每个 **stage** 一个 subgraph: 包含 registers + 组合逻辑
- **控制信号** (valid/stall) 标记为**跨 stage 虚线**

---

## 4. `visualize dataflow` — 信号分类着色

```bash
sv_query visualize dataflow \
    --filelist /tmp/ofdm_tx_fixed.f --module ifftmain --no-strict \
    --dot /tmp/ifft_dataflow.dot
dot -Tpng /tmp/ifft_dataflow.dot -o docs/images/openwifi_ifft_dataflow.png
```

**输出 (metadata)**:
```
Data nodes: 159
Control nodes: 72
Clock nodes: 26
✓ DOT: /tmp/ifft_dataflow.dot
```

**洞察**:
- 159 个 data 信号 (i_sample / w_d64 / w_d32 / ... bit-reverse 链)
- 72 个 control 信号 (i_ce / sync / fifo_turn / state machine outputs)
- 26 个 clock 信号 (每个 stage × 2-4 个内部 clk nets)

**Data flow 图**:

![ifftmain Dataflow](images/openwifi_ifft_dataflow.png)

图例:
- **蓝色实线** = data path (标注运算表达式 `a+b`, `{rx, sreg[10:1]}`)
- **橙色虚线** = control edges (valid/ready/enable → 数据目标)
- **粗边** = MUX (多源数据汇聚, e.g. butterfly add/sub select)
- **粗边框** = register (clocked)

---

## 5. `visualize graph` — 完整信号图 (--module-only)

```bash
sv_query visualize graph \
    --filelist /tmp/ofdm_tx_fixed.f --module-only --no-strict \
    --cluster-modules --dot /tmp/ifft_graph.dot --max-edges 100
dot -Tpng /tmp/ifft_graph.dot -o docs/images/openwifi_ifft_graph.png
```

**Signal Graph 图**:

![ifftmain Signal Graph](images/openwifi_ifft_graph.png)

节点颜色:
- 🟡 黄色 = `PORT_IN` (input port)
- 🟢 绿色 = `REG` (register output, 可能在 `🚨` 高风险)
- ⚪ 白色 = 内部信号

---

## 6. arch vs trace+visualize 对比总结

| 维度 | arch | trace | visualize pipeline | visualize dataflow | visualize graph |
|------|------|-------|---------------------|---------------------|------------------|
| **静态结构** (instances + ports) | ✅ 31 inst / 4 层 / 147 ports | ❌ | ❌ | ❌ | ⚠️ 部分 |
| **数据流向** | ❌ | ✅ fanout/fanin 链 | ✅ | ✅ | ✅ |
| **信号分类** (data/control/clock) | ❌ | ⚠️ need --include-clock | ❌ | ✅ 着色 | ✅ 着色 |
| **Pipeline 时序** | ❌ | ⚠️ 需要人工分析 | ✅ 自动 39 stages | ⚠️ | ⚠️ |
| **Register 数量** | ❌ | ⚠️ | ✅ 自动统计 | ✅ | ⚠️ |
| **协议标注** (AXI / 私有) | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Spec link** (802.11 §17) | ❌ | ❌ | ❌ | ❌ | ❌ |

**结论**: 单用 `arch` = 静态结构; 加上 `trace` + `visualize` = dataflow + signal classification + pipeline timing. 真正理解 PHY 需要**两者结合**, 不是 arch 单独.

---

## 7. 踩坑记录 (供未来 reference)

### 7.1 dot11_tx.v 有 `UsedBeforeDeclared` 错误

`dot11_tx.v` (openofdm_tx 主 pipeline) 有 Verilog forward reference (line 614: `pkt_fifo_space > 2 && CP_fifo_space > 2`, 但 `CP_fifo_space` 在 line 680 才声明). pyslang strict 模式不接受, 即使 `--no-strict` 也会导致 **partial AST** — 内部 wires 看不见, trace 出 "no loads".

**解决**: 不要 trace 顶层 `dot11_tx`, 直接 trace self-contained 子模块 `ifftmain` (无 forward ref).

### 7.2 缺 timescale

openwifi-hw .v 文件缺 timescale (22/25). 跑前必须 `sv_query fix timescale --apply` (在副本目录, 不动原文件).

### 7.3 memory 限制 (8GB MBA)

跑 openofdm_tx 全套 24 .v + AXI bus interface, pyslang SWAP 用 4-5 GB. 跑前:
```bash
python3 -c "import time; a = bytearray(4 * 1024**3); time.sleep(2); del a"
```
强制系统回收 inactive pages. 否则 SWAP 用满 pyslang 报 "elaboration 不完整" 但**不报 OOM 错**, 结果是 silently missing modules.

---

## 8. 完整命令复现

```bash
# === Setup ===
mkdir -p /tmp/ofdm_tx_fixed
cp ~/my_dv_proj/openwifi-hw/ip/openofdm_tx/src/*.v /tmp/ofdm_tx_fixed/

cat > /tmp/ofdm_tx_fix.f << EOF
EOF
for f in /tmp/ofdm_tx_fixed/*.v; do echo "$f" >> /tmp/ofdm_tx_fix.f; done

sv_query fix timescale --filelist /tmp/ofdm_tx_fix.f --apply

cat > /tmp/ofdm_tx_fixed.f << EOF
+incdir+/tmp/ofdm_tx_fixed
EOF
for f in /tmp/ofdm_tx_fixed/*.v; do echo "$f" >> /tmp/ofdm_tx_fixed.f; done

# === 释放内存 ===
python3 -c "import time; a = bytearray(4 * 1024**3); time.sleep(2); del a"

# === arch ===
sv_query arch show --filelist /tmp/ofdm_tx_fixed.f --target openofdm_tx \
    --depth 5 --no-strict --format summary

# === trace ===
sv_query trace fanout ifftmain.i_sample --filelist /tmp/ofdm_tx_fixed.f \
    --no-strict --human --depth 4
sv_query trace fanout ifftmain.i_ce --filelist /tmp/ofdm_tx_fixed.f \
    --no-strict --human --depth 4
sv_query trace fanout ifftmain.i_clk --filelist /tmp/ofdm_tx_fixed.f \
    --no-strict --human --depth 3 --include-clock
sv_query trace fanin ifftmain.o_result --filelist /tmp/ofdm_tx_fixed.f \
    --no-strict --human --depth 3

# === visualize ===
sv_query visualize pipeline --filelist /tmp/ofdm_tx_fixed.f \
    --module ifftmain --no-strict --dot /tmp/ifft_pipeline.dot

sv_query visualize dataflow --filelist /tmp/ofdm_tx_fixed.f \
    --module ifftmain --no-strict --dot /tmp/ifft_dataflow.dot

sv_query visualize graph --filelist /tmp/ofdm_tx_fixed.f \
    --module-only --cluster-modules --no-strict \
    --dot /tmp/ifft_graph.dot --max-edges 100

# === render PNG ===
dot -Tpng /tmp/ifft_pipeline.dot -o docs/images/openwifi_ifft_pipeline.png
dot -Tpng /tmp/ifft_dataflow.dot -o docs/images/openwifi_ifft_dataflow.png
dot -Tpng /tmp/ifft_graph.dot -o docs/images/openwifi_ifft_graph.png
```

---

## 9. 相关文档

- [ARCH_EXAMPLES.md](ARCH_EXAMPLES.md) — `arch` 命令的 5 个开源项目实测 (含 openwifi-hw openofdm_tx)
- [ARCH_VISUALIZATION.md](ARCH_VISUALIZATION.md) — arch + visualize 总览
- [VISUALIZATION.md](VISUALIZATION.md) — `visualize graph/dataflow/pipeline/gap` 详解
- [USER_GUIDE.md](USER_GUIDE.md) — sv_query 完整 user guide
- [PYSLANG_MEMORY_ISSUE.md](PYSLANG_MEMORY_ISSUE.md) — 8GB 机器 pyslang elaboration 坑