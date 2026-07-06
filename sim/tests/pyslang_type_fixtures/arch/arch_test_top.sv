// arch_test_top.sv
//
// [2026-07-06] Hand-written fixture for testing arch show --with-ports
//
// 4-level hierarchy + cross-instance wire (NOT through root) to verify
// arch's L2 cross-module port extraction:
//   - cross_instance_wire connects i_master.out -> i_slave.in directly
//     (NO root intermediary), so MIG captures instance-to-instance edge
//
// Hierarchy:
//   arch_test_top
//     ├── i_master (arch_test_master)
//     │     └── i_alu (arch_test_alu)
//     │           └── i_sub (arch_test_sub) [depth 3]
//     └── i_slave (arch_test_slave)

module arch_test_sub(
  input  logic [3:0] a,
  input  logic [3:0] b,
  output logic [3:0] q
);
  assign q = a + b;  // 4-bit add
endmodule

module arch_test_alu(
  input  logic [7:0] data_a,
  input  logic [7:0] data_b,
  output logic [7:0] alu_out,
  input  wire sub_a,
  input  wire sub_b
);
  // pipe data through sub-instances (cross-instance)
  wire [3:0] sub_lo, sub_hi;
  arch_test_sub i_sub_lo (
    .a(data_a[3:0]),
    .b(data_b[3:0]),
    .q(sub_lo)
  );
  arch_test_sub i_sub_hi (
    .a(data_a[7:4]),
    .b(data_b[7:4]),
    .q(sub_hi)
  );
  assign alu_out = {sub_hi, sub_lo};
endmodule

module arch_test_master(
  input  logic         clk,
  input  logic [7:0]   data_in,
  output logic [7:0]   data_out,
  input  wire          direct_in
);
  // ALU 子 instance
  wire [7:0] alu_result;
  arch_test_alu i_alu (
    .data_a(data_in),
    .data_b({8{1'b0}}),
    .alu_out(alu_result),
    .sub_a(direct_in),
    .sub_b(direct_in)
  );
  always_ff @(posedge clk) begin
    data_out <= alu_result;
  end
endmodule

module arch_test_slave(
  input  logic [7:0] master_out,
  output logic [7:0] echoed
);
  assign echoed = master_out;
endmodule

module arch_test_top(
  input  logic         clk,
  input  logic [7:0]   data_in,
  output logic [7:0]   data_out,
  input  logic         direct_signal
);
  // Master 实例
  wire [7:0] master_data;
  arch_test_master i_master (
    .clk(clk),
    .data_in(data_in),
    .data_out(master_data),
    .direct_in(direct_signal)
  );

  // Slave 实例
  wire [7:0] slave_data;
  arch_test_slave i_slave (
    .master_out(master_data),  // *cross-instance* wire (NO root intermediary)
    .echoed(slave_data)
  );

  assign data_out = slave_data;
endmodule
