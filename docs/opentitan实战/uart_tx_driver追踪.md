# UART_TX Driver 追踪验证

**验证日期**: 2026-05-13  
**RTL 路径**: `opentitan/hw/ip/uart/rtl/uart_tx.sv`  
**验证目标**: 验证 sv_query 对 UART 发送模块的信号 driver 追踪能力

---

## RTL 源码分析

```systemverilog
module uart_tx (
  input               clk_i,
  input               rst_ni,
  input               tx_enable,
  input               tick_baud_x16,
  input  logic        parity_enable,
  input               wr,
  input  logic        wr_parity,
  input   [7:0]       wr_data,
  output              idle,
  output logic         tx
);

  // Internal registers
  logic    [3:0] baud_div_q;
  logic          tick_baud_q;
  logic    [3:0] bit_cnt_q, bit_cnt_d;
  logic   [10:0] sreg_q, sreg_d;
  logic          tx_q, tx_d;

  assign tx = tx_q;

  // Clock divider register
  always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      baud_div_q  <= 4'h0;
      tick_baud_q <= 1'b0;
    end else if (tick_baud_x16) begin
      {tick_baud_q, baud_div_q} <= {1'b0,baud_div_q} + 5'h1;
    end else begin
      tick_baud_q <= 1'b0;
    end
  end

  // Bit counter and shift register
  always_ff @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      bit_cnt_q <= 4'h0;
      sreg_q    <= 11'h7ff;
      tx_q      <= 1'b1;
    end else begin
      bit_cnt_q <= bit_cnt_d;
      sreg_q    <= sreg_d;
      tx_q      <= tx_d;
    end
  end

  // Combinational logic for state transitions
  always_comb begin
    if (!tx_enable) begin
      bit_cnt_d = 4'h0;
      sreg_d    = 11'h7ff;
      tx_d      = 1'b1;
    end else begin
      bit_cnt_d = bit_cnt_q;
      sreg_d    = sreg_q;
      tx_d      = tx_q;
      if (wr) begin
        sreg_d    = {1'b1, (parity_enable ? wr_parity : 1'b1), wr_data, 1'b0};
        bit_cnt_d = (parity_enable ? 4'd11 : 4'd10);
      end else if (tick_baud_q && (bit_cnt_q != 4'h0)) begin
        sreg_d    = {1'b1, sreg_q[10:1]};
        tx_d      = sreg_q[0];
        bit_cnt_d = bit_cnt_q - 4'h1;
      end
    end
  end

  assign idle = (tx_enable) ? (bit_cnt_q == 4'h0) : 1'b1;
endmodule
```

---

## 金标准 (手动推导)

### 信号 driver 关系表

| 信号 | 类型 | 驱动源 | 驱动类型 | 说明 |
|------|------|--------|----------|------|
| `uart_tx.tx` | output | `uart_tx.tx_q` | assign | 直接赋值 |
| `uart_tx.tx_q` | reg | `uart_tx.tx_d` | always_ff | 时序逻辑 |
| `uart_tx.tx_d` | wire | `uart_tx.sreg_q[0]` | always_comb | 条件赋值 |
| `uart_tx.idle` | output | `uart_tx.bit_cnt_q` | assign | 组合逻辑 |
| `uart_tx.bit_cnt_q` | reg | `uart_tx.bit_cnt_d` | always_ff | 时序逻辑 |
| `uart_tx.sreg_q` | reg | `uart_tx.sreg_d` | always_ff | 时序逻辑 |
| `uart_tx.tick_baud_q` | reg | `uart_tx.tick_baud_x16` | always_ff | 计数器 |
| `uart_tx.baud_div_q` | reg | `uart_tx.tick_baud_x16` | always_ff | 分频计数器 |

### 关键 Driver 链

**tx 输出信号的完整 driver 链**:
```
uart_tx.tx
  ← uart_tx.tx_q (always_ff)
    ← uart_tx.tx_d (always_comb)
      ← uart_tx.sreg_q[0] (条件赋值)
        ← uart_tx.sreg_d (条件赋值)
          ← {wr_data, ...} (wr 赋值) 或 uart_tx.sreg_q[10:1] (移位)
```

**idle 信号依赖**:
```
uart_tx.idle
  ← uart_tx.bit_cnt_q (always_comb)
    ← uart_tx.bit_cnt_d (always_comb)
```

---

## sv_query 实际输出

```python
import pyslang
from trace.unified_tracer import UnifiedTracer

# 读取 RTL 源码
with open('opentitan/hw/ip/uart/rtl/uart_tx.sv', 'r') as f:
    source = f.read()

tree = pyslang.SyntaxTree.fromText(source)
tracer = UnifiedTracer(trees={'uart_tx.sv': tree})
tracer.build_graph()
graph = tracer.get_graph()

# 追踪 tx 的 drivers
print("=== Drivers of uart_tx.tx ===")
drivers = graph.find_drivers('uart_tx.tx')
for d in drivers:
    print(f"  {d.id}")

# 追踪 idle 的 drivers
print("\n=== Drivers of uart_tx.idle ===")
drivers = graph.find_drivers('uart_tx.idle')
for d in drivers:
    print(f"  {d.id}")

# 追踪 bit_cnt_q 的 drivers
print("\n=== Drivers of uart_tx.bit_cnt_q ===")
drivers = graph.find_drivers('uart_tx.bit_cnt_q')
for d in drivers:
    print(f"  {d.id}")

# 查看所有时钟边
print("\n=== Clock Edges ===")
for src, dst in graph.edges():
    edge = graph.get_edge(src, dst)
    if edge.kind.name == 'CLOCK':
        print(f"  {src} --CLOCK--> {dst}")
```

**预期输出**:
```
=== Drivers of uart_tx.tx ===
  uart_tx.tx_q

=== Drivers of uart_tx.idle ===
  (depends on implementation)

=== Drivers of uart_tx.bit_cnt_q ===
  uart_tx.bit_cnt_d
```

---

## 对比验证结果

| 信号 | 金标准 (预期) | sv_query 实际 | 一致性 |
|------|---------------|---------------|--------|
| `uart_tx.tx` | `uart_tx.tx_q` | 待运行 | - |
| `uart_tx.tx_q` | `uart_tx.tx_d` | 待运行 | - |
| `uart_tx.idle` | `uart_tx.bit_cnt_q` | 待运行 | - |

---

## 运行验证

```bash
cd ~/my_dv_proj/sv_query
PYTHONPATH=src python -c "
import pyslang
from trace.unified_tracer import UnifiedTracer

with open('/Users/fundou/my_dv_proj/opentitan/hw/ip/uart/rtl/uart_tx.sv', 'r') as f:
    source = f.read()

tree = pyslang.SyntaxTree.fromText(source)
tracer = UnifiedTracer(trees={'uart_tx.sv': tree})
tracer.build_graph()
graph = tracer.get_graph()

# tx drivers
drivers = graph.find_drivers('uart_tx.tx')
print('Drivers of uart_tx.tx:')
for d in drivers:
    print(f'  {d.id}')

# idle drivers
drivers = graph.find_drivers('uart_tx.idle')
print('Drivers of uart_tx.idle:')
for d in drivers:
    print(f'  {d.id}')
"
```

---

## 验证结论

| 项目 | 结果 |
|------|------|
| Verilator 语法验证 | ⬜ 待执行 |
| sv_query 追踪结果 | ⬜ 待运行 |
| 与金标准对比 | ⬜ 待分析 |