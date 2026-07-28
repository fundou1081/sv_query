// generate_if_alu.sv - V6.3+5 2026-07-28: minimal picorv32 alu_shr reproducer.
//
// picorv32.v wraps alu_shr assignments in `generate if (TWO_CYCLE_ALU)`.
// With TWO_CYCLE_ALU=0 (default), only the `else` branch's `always @*`
// block is active. This fixture isolates that pattern to verify
// driver extraction works inside generate-if/else branches.

`timescale 1ns/1ps
module generate_if_alu #(
    parameter [0:0] TWO_CYCLE_ALU = 0
) (
    input clk,
    input  [31:0] reg_op1, reg_op2,
    input        instr_sra, instr_srai,
    output reg [31:0] alu_shr,
    output reg [31:0] alu_shl
);

    // generate-if wrapping alu_shr — same structure as picorv32 line 1229
    generate if (TWO_CYCLE_ALU) begin
        always @(posedge clk) begin
            alu_shl <= reg_op1 << reg_op2[4:0];
            alu_shr <= $signed({instr_sra || instr_srai ? reg_op1[31] : 1'b0, reg_op1})
                       >>> reg_op2[4:0];
        end
    end else begin
        always @* begin
            alu_shl = reg_op1 << reg_op2[4:0];
            alu_shr = $signed({instr_sra || instr_srai ? reg_op1[31] : 1'b0, reg_op1})
                      >>> reg_op2[4:0];
        end
    end endgenerate

endmodule