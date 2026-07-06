// arch_cpu_top.sv
//
// [2026-07-06] Hand-written fixture: CPU-style hierarchy (frontend + exec + mem + cache)
// 3-level 深度 + multi cross-instance connections
//
// Hierarchy:
//   arch_cpu_top (root)
//     ├── if_stage (arch_cpu_if)         depth 1
//     │     └── i_decoder (arch_decoder) depth 2
//     └── ex_stage (arch_cpu_ex)         depth 1
//           ├── i_alu (arch_alu)         depth 2
//           │     └── i_add (arch_add)   depth 3  ← cross-instance via wire
//           └── i_regfile (arch_regfile) depth 2
//
// Cross-instance ports (NOT through root):
//   i_decoder.out_op  → i_alu.op_a      (direct wire)
//   i_decoder.out_op2 → i_alu.op_b      (direct wire)
//   i_add.q           → i_regfile.wdata  (direct wire, ALU result → regfile)

module arch_add(
  input  logic [7:0] a, b,
  output logic [7:0] q
);
  assign q = a + b;
endmodule

module arch_alu(
  input  logic [7:0] op_a,
  input  logic [7:0] op_b,
  output logic [7:0] result
);
  wire [7:0] add_q;
  arch_add i_add (
    .a(op_a),
    .b(op_b),
    .q(add_q)
  );
  assign result = add_q;
endmodule

module arch_regfile(
  input  logic        clk,
  input  logic [7:0]  wdata,
  input  logic [2:0]  waddr,
  output logic [7:0]  rdata
);
  reg [7:0] regs [0:7];
  always_ff @(posedge clk) regs[waddr] <= wdata;
  assign rdata = regs[0];
endmodule

module arch_decoder(
  input  logic [15:0] instr,
  output logic [7:0]  out_op,
  output logic [7:0]  out_op2
);
  assign out_op  = {4'b0, instr[7:0]};
  assign out_op2 = {4'b0, instr[15:8]};
endmodule

module arch_cpu_if(
  input  logic         clk,
  input  logic [15:0]  instr_in,
  output logic [7:0]   decoded_op,
  output logic [7:0]   decoded_op2
);
  arch_decoder i_decoder (
    .instr(instr_in),
    .out_op(decoded_op),
    .out_op2(decoded_op2)
  );
endmodule

module arch_cpu_ex(
  input  logic        clk,
  input  logic [7:0]  op_a,
  input  logic [7:0]  op_b,
  output logic [7:0]  alu_result,
  output logic [7:0]  regfile_data
);
  wire [7:0] alu_q;
  arch_alu i_alu (
    .op_a(op_a),
    .op_b(op_b),
    .result(alu_q)
  );
  arch_regfile i_regfile (
    .clk(clk),
    .wdata(alu_q),         // cross-instance wire: ALU → regfile
    .waddr(3'b001),
    .rdata(regfile_data)
  );
  assign alu_result = alu_q;
endmodule

module arch_cpu_top(
  input  logic         clk,
  input  logic [15:0]  instr_in,
  output logic [7:0]   decoded_op,
  output logic [7:0]   decoded_op2,
  output logic [7:0]   alu_result,
  output logic [7:0]   regfile_data
);
  wire [7:0] op_a_w, op_b_w;
  arch_cpu_if if_stage (
    .clk(clk),
    .instr_in(instr_in),
    .decoded_op(op_a_w),
    .decoded_op2(op_b_w)
  );
  arch_cpu_ex ex_stage (
    .clk(clk),
    .op_a(op_a_w),           // cross-instance wire: if → ex
    .op_b(op_b_w),
    .alu_result(alu_result),
    .regfile_data(regfile_data)
  );
  assign decoded_op  = op_a_w;
  assign decoded_op2 = op_b_w;
endmodule
