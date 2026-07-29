// cva6_alu_pattern.sv — 从 CVA6 ALU 抽取的典型 CPU 代码模式
//
// 模式 1: generate for 循环 (bit reversal)
// 模式 2: 多操作符 assign (adder, comparator)
// 模式 3: always_comb 大 case (ALU operation dispatch)
// 模式 4: 嵌套 if-else (branch resolution)

module cva6_alu_pattern #(
    parameter int XLEN = 64
) (
    input  logic                   clk_i,
    input  logic                   rst_ni,
    input  logic [      XLEN-1:0] operand_a,
    input  logic [      XLEN-1:0] operand_b,
    input  logic [           4:0] alu_op_i,
    input  logic                   is_branch_i,
    output logic [      XLEN-1:0] result_o,
    output logic                   branch_taken_o
);

  // ── 模式 1: generate for 循环 (CVA6 ALU 经典模式) ──
  logic [XLEN-1:0] operand_a_rev;
  generate
    genvar k;
    for (k = 0; k < XLEN; k++) begin : gen_rev
      assign operand_a_rev[k] = operand_a[XLEN-1-k];
    end
  endgenerate

  // ── 模式 2: 多操作符 assign ──
  logic [XLEN:0] adder_in_a, adder_in_b;
  logic           adder_op_b_negate;
  assign adder_in_a = {1'b0, operand_a};
  assign adder_in_b = adder_op_b_negate ? {1'b0, ~operand_b} : {1'b0, operand_b};

  // ── 模式 3: always_comb 大 case dispatch (CVA6 ALU 核心) ──
  logic [XLEN-1:0] result_comb;
  always_comb begin
    result_comb = '0;
    branch_taken_o = 1'b0;
    case (alu_op_i)
      5'd0:  result_comb = operand_a;
      5'd1:  result_comb = operand_b;
      5'd2:  result_comb = operand_a + operand_b;
      5'd3:  result_comb = operand_a - operand_b;
      5'd4:  result_comb = operand_a & operand_b;
      5'd5:  result_comb = operand_a | operand_b;
      5'd6:  result_comb = operand_a ^ operand_b;
      5'd8:  result_comb = operand_a << operand_b[5:0];
      5'd9:  result_comb = operand_a >> operand_b[5:0];
      5'd16: begin // branch eq
        branch_taken_o = (operand_a == operand_b);
        result_comb = operand_a;
      end
      5'd17: begin // branch ne
        branch_taken_o = (operand_a != operand_b);
        result_comb = operand_a;
      end
      default: result_comb = operand_a;
    endcase
  end

  // ── 模式 4: 嵌套 if-else (branch resolution 经典模式) ──
  always_comb begin
    if (is_branch_i) begin
      if (adder_op_b_negate)
        result_o = result_comb - operand_b;
      else
        result_o = result_comb + operand_b;
    end else begin
      result_o = result_comb;
    end
  end

endmodule
