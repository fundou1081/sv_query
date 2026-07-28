// binary_ops.sv - V6.3+5 2026-07-28: binary operator decomposition.
//
// Tests that driver extraction correctly decomposes RHS expressions
// containing binary operators into leaf signal drivers.
//
// Patterns:
//   1. y_arith:           y = a + b;
//   2. y_shift:           y = a << b[4:0];
//   3. y_signed:          y = $signed(a) >>> b;
//   4. y_signed_concat:   y = $signed({instr_sra ? a[31] : 1'b0, a}) >>> b[4:0];
//                          ← picorv32 alu_shr pattern (no generate-if)
//   5. y_mixed:           y = (a + b) & mask;
//   6. y_pipe:            y = ((a | b) & c) | d;

`timescale 1ns/1ps
module binary_ops_test(
    input        clk,
    input  [7:0] a, b, c, d, mask,
    input        instr_sra,
    input  [4:0] shift_amount,
    output [7:0] y_arith,
    output [7:0] y_shift,
    output [7:0] y_signed,
    output [7:0] y_signed_concat,
    output [7:0] y_mixed,
    output [7:0] y_pipe
);

    // Pattern 1: simple addition
    assign y_arith = a + b;

    // Pattern 2: shift with range select
    assign y_shift = a << shift_amount;

    // Pattern 3: $signed wrapping (type cast, should be transparent)
    assign y_signed = $signed(a) >>> b;

    // Pattern 4: picorv32 alu_shr pattern without generate-if wrapping
    assign y_signed_concat = $signed({instr_sra ? a[7] : 1'b0, a}) >>> b[4:0];

    // Pattern 5: nested binary (parens around binary)
    assign y_mixed = (a + b) & mask;

    // Pattern 6: deeply nested binary
    assign y_pipe = ((a | b) & c) | d;

endmodule