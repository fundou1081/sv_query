// arch_deep_top.sv
//
// [2026-07-06] Hand-written 5-level hierarchy fixture (for arch deep test)
//
// SoC top → AXI host bridge → AXI peripheral bridge
//   → DMA controller (multi-state machine)
//     → Bus bridge (multi-channel)
//       → Mailbox FIFO (write path + read path)
//         → Memory-Mapped registers
//           → APB peripheral (multi-register file)
//
// Hierarchy (5 levels deep):
//   arch_deep_top
//     ├── i_host (arch_host_bridge)         depth 1
//     │     └── i_periph (arch_periph_bridge) depth 2
//     │           └── i_dma (arch_dma)       depth 3
//     │                 ├── i_bridge (arch_bus_bridge) depth 4
//     │                 │     └── i_mailbox (arch_mailbox) depth 5
//     │                 │           ├── i_write (arch_fifo) depth 6
//     │                 │           └── i_read  (arch_fifo) depth 6
//     │                 │                 └── i_regs (arch_regfile) depth 7
//     │                 │                       └── i_apb (arch_apb)  depth 8
//     │                 └── i_ctrl (arch_dma_ctrl) depth 4
//     └── i_mem (arch_mem_ctrl)            depth 1
//           └── i_apb_master (arch_apb)    depth 2
//                 └── i_regfile (arch_regfile) depth 3

module arch_regfile(
  input  logic        clk,
  input  logic        we,
  input  logic [3:0]  addr,
  input  logic [7:0]  wdata,
  output logic [7:0]  rdata
);
  reg [7:0] regs [0:15];
  always_ff @(posedge clk) if (we) regs[addr] <= wdata;
  assign rdata = regs[addr];
endmodule

module arch_apb(
  input  logic        clk,
  input  logic [3:0]  paddr,
  input  logic        pwrite,
  input  logic [7:0]  pwdata,
  output logic [7:0]  prdata
);
  wire [7:0] rdata_int;
  arch_regfile i_regfile (
    .clk(clk),
    .we(pwrite),
    .addr(paddr),
    .wdata(pwdata),
    .rdata(rdata_int)
  );
  assign prdata = rdata_int;
endmodule

module arch_fifo(
  input  logic        clk,
  input  logic        we,
  input  logic [7:0]  wdata,
  input  logic        re,
  output logic [7:0]  rdata,
  output logic        full,
  output logic        empty
);
  reg [7:0] mem [0:7];
  reg [3:0] wptr, rptr;
  always_ff @(posedge clk) begin
    if (we && !full) mem[wptr[2:0]] <= wdata;
    if (re && !empty) rdata <= mem[rptr[2:0]];
  end
  always_ff @(posedge clk) begin
    if (we && !full) wptr <= wptr + 1;
    if (re && !empty) rptr <= rptr + 1;
  end
  assign full  = (wptr[2:0] == rptr[2:0]) && (wptr[3] != rptr[3]);
  assign empty = (wptr == rptr);
endmodule

module arch_mailbox(
  input  logic        clk,
  input  logic [7:0]  push_data,
  input  logic        push_we,
  input  logic        pop_re,
  output logic [7:0]  pop_data
);
  wire [7:0] w_data, r_data;
  logic w_full, w_empty, r_full, r_empty;
  arch_fifo i_write (
    .clk(clk), .we(push_we), .wdata(push_data),
    .re(1'b0), .rdata(), .full(w_full), .empty(w_empty)
  );
  arch_fifo i_read (
    .clk(clk), .we(1'b0), .wdata(8'h00),
    .re(pop_re), .rdata(r_data), .full(), .empty()
  );
  assign pop_data = r_data;
endmodule

module arch_bus_bridge(
  input  logic        clk,
  input  logic        we,
  input  logic [7:0]  wdata,
  input  logic        re,
  output logic [7:0]  rdata,
  output logic        busy
);
  wire [7:0] mb_out;
  arch_mailbox i_mailbox (
    .clk(clk),
    .push_data(wdata),
    .push_we(we),
    .pop_re(re),
    .pop_data(mb_out)
  );
  assign rdata = mb_out;
  assign busy  = 1'b0;
endmodule

module arch_dma_ctrl(
  input  logic        clk,
  input  logic [7:0]  src_addr,
  input  logic [7:0]  dst_addr,
  output logic        done
);
  assign done = 1'b1;
endmodule

module arch_dma(
  input  logic        clk,
  input  logic        start,
  output logic        done
);
  wire        busy;
  wire [7:0]  br_data;
  arch_bus_bridge i_bridge (
    .clk(clk), .we(start), .wdata(8'hAA),
    .re(start), .rdata(br_data), .busy(busy)
  );
  arch_dma_ctrl i_ctrl (
    .clk(clk),
    .src_addr(8'h00),
    .dst_addr(8'h10),
    .done(done)
  );
endmodule

module arch_periph_bridge(
  input  logic        clk,
  output logic        done
);
  arch_dma i_dma (
    .clk(clk),
    .start(1'b0),
    .done(done)
  );
endmodule

module arch_host_bridge(
  input  logic        clk,
  output logic        done
);
  arch_periph_bridge i_periph (
    .clk(clk),
    .done(done)
  );
endmodule

module arch_mem_ctrl(
  input  logic        clk,
  input  logic        we,
  input  logic [3:0]  addr,
  input  logic [7:0]  wdata,
  output logic [7:0]  rdata
);
  wire [7:0] apb_rdata;
  arch_apb i_apb_master (
    .clk(clk),
    .paddr(addr),
    .pwrite(we),
    .pwdata(wdata),
    .prdata(apb_rdata)
  );
  assign rdata = apb_rdata;
endmodule

module arch_deep_top(
  input  logic        clk,
  output logic        done
);
  arch_host_bridge i_host (
    .clk(clk),
    .done(done)
  );
  arch_mem_ctrl i_mem (
    .clk(clk),
    .we(1'b0),
    .addr(4'h0),
    .wdata(8'h00),
    .rdata()
  );
endmodule
