// nested_mux_demo.sv - 复杂嵌套 mux 模式全面测试 (V6.3+1+ validation)
//
// 16 种复杂嵌套模式:
//   1.  y_case_in_case:       case 套 case (nested case)
//   2.  y_case_with_if:       case 套 if/else
//   3.  y_if_with_case:       if 套 case
//   4.  y_nested_if:          if 套 if (with begin/end)
//   5.  y_tern_in_tern:       ternary 套 ternary (3 levels deep)
//   6.  y_tern_both_branches: 三元两边都是 ternary
//   7.  y_case_in_if_in_case: case 套 if 套 case (3 levels)
//   8.  y_full_zoo:           全套 (case 套 ternary 套 ternary)
//   9.  y_4level_tern:        ternary 4 levels deep (g ? h ? i ? ... : ...)
//   10. y_case_with_tern:     case 套 ternary (no extra nesting)
//   11. y_case_3way_branch:   case each branch is independent ternary
//   12. y_case_xnor_pattern:  case with non-overlapping selector values
//   13. y_concat_in_mux:      concatenations in mux branches (bit slicing)
//   14. y_default_chain:      case default chain with mixed conditional types
//   15. y_inside_func_call:   ternary as argument to function call
//   16. y_array_index_mux:    array indexed by case selector

`timescale 1ns/1ps
module nested_mux_demo(
    input clk,
    input  [1:0] a, b, c, d, e, f,
    input        g, h, i, j, k, l, m, n, o, p, q, r, s,
    input  [7:0] x0, x1, x2, x3, x4, x5, x6, x7,
    input  [7:0] x8, x9, x10, x11, x12, x13, x14, x15,
    input  [7:0] arr [0:15],
    output reg [7:0] y_case_in_case,
    output reg [7:0] y_case_with_if,
    output reg [7:0] y_if_with_case,
    output reg [7:0] y_nested_if,
    output     [7:0] y_tern_in_tern,
    output     [7:0] y_tern_both_branches,
    output reg [7:0] y_case_in_if_in_case,
    output reg [7:0] y_full_zoo,
    output     [7:0] y_4level_tern,
    output reg [7:0] y_case_with_tern,
    output reg [7:0] y_case_3way_branch,
    output reg [7:0] y_case_xnor_pattern,
    output reg [7:0] y_concat_in_mux,
    output reg [7:0] y_default_chain,
    output     [7:0] y_inside_func_call,
    output     [7:0] y_array_index_mux
);

    // ----------------------------------------------------------------------
    // Pattern 1: case 套 case
    //   outer case by a, inner case by b
    //   Expected edge conditions: (a == X) && (b == Y)
    // ----------------------------------------------------------------------
    always @(posedge clk) begin
        case (a)
            2'd0: begin
                case (b)
                    2'd0:    y_case_in_case <= x0;
                    2'd1:    y_case_in_case <= x1;
                    default: y_case_in_case <= x2;
                endcase
            end
            2'd1: begin
                case (b)
                    2'd0:    y_case_in_case <= x3;
                    2'd1:    y_case_in_case <= x4;
                    default: y_case_in_case <= x5;
                endcase
            end
            default: y_case_in_case <= x6;
        endcase
    end

    // ----------------------------------------------------------------------
    // Pattern 2: case 套 if/else
    //   each case branch contains an if/else
    //   Expected: (a == X) && (g) / (a == X) && (!g)
    // ----------------------------------------------------------------------
    always @(posedge clk) begin
        case (a)
            2'd0:    if (g) y_case_with_if <= x0; else y_case_with_if <= x1;
            2'd1:    if (h) y_case_with_if <= x2; else y_case_with_if <= x3;
            default: if (i) y_case_with_if <= x4; else y_case_with_if <= x5;
        endcase
    end

    // ----------------------------------------------------------------------
    // Pattern 3: if 套 case
    //   if g, then case by a selects x0-x2; else case by a selects x3-x5
    //   Expected: (g) && (a == X)  /  (!g) && (a == X)
    // ----------------------------------------------------------------------
    always @(posedge clk) begin
        if (g) begin
            case (a)
                2'd0:    y_if_with_case <= x0;
                2'd1:    y_if_with_case <= x1;
                default: y_if_with_case <= x2;
            endcase
        end else begin
            case (a)
                2'd0:    y_if_with_case <= x3;
                2'd1:    y_if_with_case <= x4;
                default: y_if_with_case <= x5;
            endcase
        end
    end

    // ----------------------------------------------------------------------
    // Pattern 4: nested if (if 套 if)
    //   if g then if h then ... else ...
    //   Expected: g && h / g && !h / !g (3 leaf signals each as 1 driver)
    // ----------------------------------------------------------------------
    always @(posedge clk) begin
        if (g) begin
            if (h)
                y_nested_if <= x0;
            else
                y_nested_if <= x1;
        end else
            y_nested_if <= x2;
    end

    // ----------------------------------------------------------------------
    // Pattern 5: ternary 套 ternary (3 levels)
    //   y = g ? (h ? x0 : x1) : x2
    //   Expected: g && h / g && !h / !g
    // ----------------------------------------------------------------------
    assign y_tern_in_tern = g ? (h ? x0 : x1) : x2;

    // ----------------------------------------------------------------------
    // Pattern 6: 三元两边都是 ternary
    //   y = g ? (h ? x0 : x1) : (i ? x2 : x3)
    //   Expected: g && h / g && !h / !g && i / !g && !i
    // ----------------------------------------------------------------------
    assign y_tern_both_branches = g ? (h ? x0 : x1) : (i ? x2 : x3);

    // ----------------------------------------------------------------------
    // Pattern 7: case 套 if 套 case (3-level)
    //   outer a, inner case contains if, innermost case by c
    //   Expected: (a == X) && (g) && (c == Y) / (a == X) && (!g) && (c == Y)
    // ----------------------------------------------------------------------
    always @(posedge clk) begin
        case (a)
            2'd0: begin
                if (g) begin
                    case (c)
                        2'd0:    y_case_in_if_in_case <= x0;
                        default: y_case_in_if_in_case <= x1;
                    endcase
                end else begin
                    case (c)
                        2'd0:    y_case_in_if_in_case <= x2;
                        default: y_case_in_if_in_case <= x3;
                    endcase
                end
            end
            default: y_case_in_if_in_case <= x4;
        endcase
    end

    // ----------------------------------------------------------------------
    // Pattern 8: 全套 — case 套 ternary 套 ternary
    //   case (a) 2'd0: y = g ? (h ? x0 : x1) : (i ? x2 : x3); endcase
    //   Expected: (a == 0) && g && h / ... 4 leaf signals in 1 case branch
    // ----------------------------------------------------------------------
    always @(posedge clk) begin
        case (a)
            2'd0:    y_full_zoo <= g ? (h ? x0 : x1) : (i ? x2 : x3);
            2'd1:    y_full_zoo <= j ? (k ? x4 : x5) : (l ? x6 : x7);
            default: y_full_zoo <= m ? (n ? x8 : x9) : (o ? x10 : x11);
        endcase
    end

    // ----------------------------------------------------------------------
    // Pattern 9: 4-level ternary — extreme depth
    //   y = g ? (h ? (i ? x0 : x1) : x2) : (j ? x3 : x4)
    //   Tests recursive unwrap reaches 4 levels deep without losing branches.
    //   Expected: g && h && i / g && h && !i / g && !h / !g && j / !g && !j
    // ----------------------------------------------------------------------
    assign y_4level_tern = g ? (h ? (i ? x0 : x1) : x2) : (j ? x3 : x4);

    // ----------------------------------------------------------------------
    // Pattern 10: case 套 ternary (no extra nesting)
    //   each case branch is a simple ternary — no inner ternary.
    //   Tests case-item decomposition with single-level ternaries.
    //   Expected: (a == X) && g / (a == X) && !g
    // ----------------------------------------------------------------------
    always @(posedge clk) begin
        case (a)
            2'd0:    y_case_with_tern <= g ? x0 : x1;
            2'd1:    y_case_with_tern <= h ? x2 : x3;
            default: y_case_with_tern <= i ? x4 : x5;
        endcase
    end

    // ----------------------------------------------------------------------
    // Pattern 11: case each branch is independent ternary with different
    // condition signals — same shape but distinct gating.
    //   case (a) 2'd0: y = g ? x0 : x1; 2'd1: y = h ? x2 : x3; ...
    //   Tests that all gating signals (g, h, i) are tracked separately.
    //   Expected: (a == 0) && g / (a == 0) && !g / (a == 1) && h / etc
    // ----------------------------------------------------------------------
    always @(posedge clk) begin
        case (a)
            2'd0:    y_case_3way_branch <= g ? x0 : x1;
            2'd1:    y_case_3way_branch <= h ? x2 : x3;
            default: y_case_3way_branch <= i ? x4 : x5;
        endcase
    end

    // ----------------------------------------------------------------------
    // Pattern 12: case with non-overlapping selectors (XNOR pattern)
    //   case (a): 2'b00: y=x0; 2'b01: y=x1; 2'b10: y=x2; default: y=x3
    //   Tests that all 4 selectors get separate conditions and x3 is
    //   still in driver list (default branch must be tracked).
    //   Expected: (a == 0) / (a == 1) / (a == 2) / (a == default)
    // ----------------------------------------------------------------------
    always @(posedge clk) begin
        case (a)
            2'b00: y_case_xnor_pattern <= x0;
            2'b01: y_case_xnor_pattern <= x1;
            2'b10: y_case_xnor_pattern <= x2;
            default: y_case_xnor_pattern <= x3;
        endcase
    end

    // ----------------------------------------------------------------------
    // Pattern 13: concatenation in mux branches
    //   y = g ? {x0, x1} : {x2, x3};  // 16-bit concat
    //   Tests that concatenation expressions are unwrapped to leaf signals
    //   (x0, x1 in true branch; x2, x3 in false branch).
    //   Expected: g → [x0, x1]; !g → [x2, x3]
    // ----------------------------------------------------------------------
    always @(posedge clk) begin
        y_concat_in_mux <= g ? {x0, x1} : {x2, x3};
    end

    // ----------------------------------------------------------------------
    // Pattern 14: default chain with mixed conditional types
    //   case (a): 2'd0: y = g ? x0 : x1; default: y = h ? x2 : x3;
    //   Tests that partial case (one explicit + default) still extracts
    //   both ternary conditions from the default branch.
    //   Expected: (a == 0) && g / (a == 0) && !g /
    //             (a == default) && h / (a == default) && !h
    // ----------------------------------------------------------------------
    always @(posedge clk) begin
        case (a)
            2'd0:    y_default_chain <= g ? x0 : x1;
            default: y_default_chain <= h ? x2 : x3;
        endcase
    end

    // ----------------------------------------------------------------------
    // Pattern 15: ternary as argument to function call
    //   y = $clog2(g ? x0 : x1);  // System function with ternary arg
    //   Tests that the visitor handles ternaries nested in function calls.
    //   Expected: g → x0; !g → x1
    // ----------------------------------------------------------------------
    // Note: $clog2 returns an integer; assign result to a sized output.
    // We use a different shape: $signed(g ? x0 : x1) which preserves width.
    assign y_inside_func_call = $signed(g ? x0 : x1);

    // ----------------------------------------------------------------------
    // Pattern 16: array indexed by case selector
    //   case (a) 2'd0: y = arr[0]; 2'd1: y = arr[1]; ...
    //   Tests that array indexing expressions (arr[N]) are unwrapped and
    //   the array name (`arr`) is captured as the driver source.
    //   Expected: (a == 0) → arr / (a == 1) → arr / etc.
    // ----------------------------------------------------------------------
    always @(posedge clk) begin
        case (a)
            2'd0:    y_array_index_mux <= arr[0];
            2'd1:    y_array_index_mux <= arr[1];
            2'd2:    y_array_index_mux <= arr[2];
            default: y_array_index_mux <= arr[15];
        endcase
    end

endmodule