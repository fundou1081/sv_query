// arch_soc_top.sv
//
// [2026-07-06] Hand-written fixture: SoC-style (crossbar + multiple peripherals)
//
// Hierarchy:
//   arch_soc_top (root)
//     ├── i_xbar (arch_xbar)             depth 1  — full cross-instance
//     ├── i_master (arch_soc_master)     depth 1  — wire to xbar
//     ├── i_slave1 (arch_soc_peripheral) depth 1
//     └── i_slave2 (arch_soc_peripheral) depth 1
//
// Cross-instance wires (NOT through root):
//   i_master.m_out → i_xbar.master_in
//   i_xbar.slave1_out → i_slave1.in_data

module arch_soc_peripheral(
  input  logic [7:0]  in_data,
  output logic [7:0]  out_data
);
  assign out_data = in_data + 1;
endmodule

module arch_soc_master(
  output logic [7:0]  m_out,
  input  logic        m_ready
);
  assign m_out = 8'hAA;
endmodule

module arch_xbar(
  input  logic [7:0] master_in,
  input  logic        slave_sel,
  output logic [7:0] slave1_out,
  output logic [7:0] slave2_out
);
  // 2x1 mux: select slave
  assign slave1_out = slave_sel ? master_in : 8'h00;
  assign slave2_out = slave_sel ? 8'h00 : master_in;
endmodule

module arch_soc_top(
  input  logic         clk,
  input  logic         sel,
  output logic [7:0]  data_out
);
  wire [7:0] m_w, s1_w, s2_w;
  arch_soc_master i_master (
    .m_out(m_w),
    .m_ready(1'b1)
  );
  arch_xbar i_xbar (
    .master_in(m_w),
    .slave_sel(sel),
    .slave1_out(s1_w),
    .slave2_out(s2_w)
  );
  arch_soc_peripheral i_slave1 (
    .in_data(s1_w),       // cross-instance wire
    .out_data(data_out)
  );
  arch_soc_peripheral i_slave2 (
    .in_data(s2_w),
    .out_data()
  );
endmodule
