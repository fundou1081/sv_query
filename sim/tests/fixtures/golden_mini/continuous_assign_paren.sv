// continuous_assign_paren.sv - V6.3+4 2026-07-28: continuous assign patterns.
//
// Tests that _handle_normal_assign correctly handles:
//   1. y_simple_paren: assign y = (g ? a : b);      ← paren-wrapped ternary
//   2. y_double_paren: assign y = ((g ? a : b));    ← double-paren
//   3. y_tern_in_expr: assign y = sel ? (x | mask) : (x & mask);  ← ternary arms
//      that are parenthesized binary expressions (NOT ternaries).
//
// Before V6.3+4: continuous assigns with paren-wrapped ternaries lost their
// compound conditions on driver edges. E.g. y_simple_paren would emit
// 2 driver edges (a → y, b → y) with no condition label, even though the
// condition `g` is what gates them.
//
// After V6.3+4: edges carry `g` / `!g` (or its string form) so the
// graph correctly shows the guarding logic.

`timescale 1ns/1ps
module continuous_assign_paren(
    input        g, h, sel,
    input  [7:0] a, b, c, d,
    input  [7:0] x,
    input  [7:0] mask,
    output [7:0] y_simple_paren,
    output [7:0] y_double_paren,
    output [7:0] y_tern_in_expr
);

    // ----------------------------------------------------------------------
    // Pattern 1: paren-wrapped ternary in continuous assign
    //   Before V6.3+4: `_handle_normal_assign` did NOT pass the unwrapped
    //   ConditionalOp to get_signals_with_conditions, so driver edges
    //   for a and b had no condition labels.
    //   After V6.3+4: edges a → y carry `g`, b → y carry `!g`.
    // ----------------------------------------------------------------------
    assign y_simple_paren = (g ? a : b);

    // ----------------------------------------------------------------------
    // Pattern 2: double-paren-wrapped ternary
    //   Verifies unwrap() handles multiple layers of Paren wrappers
    //   (recursive strip until non-wrapper).
    // ----------------------------------------------------------------------
    assign y_double_paren = ((g ? a : b));

    // ----------------------------------------------------------------------
    // Pattern 3: ternary arms are parenthesized binary expressions
    //   Tests that paren around a binary expression is NOT mistaken for
    //   a paren around a ternary. Only the OUTER ternary's condition
    //   (`sel`) should appear on the driver edges.
    //   Expected drivers: x, mask (the binary operands), with `sel` /
    //   `!sel` conditions.
    // ----------------------------------------------------------------------
    assign y_tern_in_expr = sel ? (x | mask) : (x & mask);

endmodule