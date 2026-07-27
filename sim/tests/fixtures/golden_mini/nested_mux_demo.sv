// nested_mux_demo.sv - 复杂嵌套 mux 模式全面测试 (V6.3+1+ validation)
//
// 8 种复杂嵌套模式:
//   1. y_case_in_case: case 套 case (nested case)
//   2. y_case_with_if: case 套 if/else
//   3. y_if_with_case: if 套 case
//   4. y_nested_if:    if 套 if (with begin/end)
//   5. y_tern_in_tern: ternary 套 ternary (3 levels deep)
//   6. y_tern_both_branches: 三元两边都是 ternary
//   7. y_case_in_if_in_case: case 套 if 套 case (3 levels)
//   8. y_full_zoo: 全套 (case 套 ternary 套 ternary)

`timescale 1ns/1ps
module nested_mux_demo(
    input clk,
    input  [1:0] a, b, c, d, e, f,
    input        g, h, i, j, k, l, m, n, o, p,
    input  [7:0] x0, x1, x2, x3, x4, x5, x6, x7,
    input  [7:0] x8, x9, x10, x11, x12, x13, x14, x15,
    output reg [7:0] y_case_in_case,
    output reg [7:0] y_case_with_if,
    output reg [7:0] y_if_with_case,
    output reg [7:0] y_nested_if,
    output     [7:0] y_tern_in_tern,
    output     [7:0] y_tern_both_branches,
    output reg [7:0] y_case_in_if_in_case,
    output reg [7:0] y_full_zoo
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

endmodule