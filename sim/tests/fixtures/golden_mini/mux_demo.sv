// mux_demo.sv — Custom mux showcase for V6.3+ viz validation
//
// Designed to exercise all 4 mux patterns teach --focus --upstream should surface:
//   1) if/else (2:1 MUX)
//   2) case (4:1 MUX)
//   3) ternary (2:1 combinational MUX)
//   4) Nested mux (case → if/else, 4×2 = 8 possible inputs)
//
// All patterns drive outputs of different kinds:
//   - y_simple_if:  reg, 2:1 if/else
//   - y_case:       reg, 4:1 case
//   - y_tern:       wire, ternary
//   - y_nested:     reg, case containing nested if/else
//   - y_deep:       reg, 2-deep nested case
//
// Each output's upstream trace should show edge labels:
//   y_simple_if: "sel_a" / "!sel_a"
//   y_case:      "sel_b == 2'd0" / "sel_b == 2'd1" / "sel_b == 2'd2" / "sel_b == default"
//   y_tern:      "sel_c" / "!sel_c" (or similar)
//   y_nested:    outer case condition + inner if condition
//   y_deep:      outer + inner case conditions

`timescale 1ns/1ps
module mux_demo(
    input             clk,
    input             sel_a,           // 2:1 if/else select
    input  [1:0]      sel_b,           // 4:1 case select
    input             sel_c,           // ternary select
    input  [1:0]      sel_d,           // outer case select
    input  [1:0]      sel_e,           // inner case select
    input             sel_f,           // inner if/else select
    input  [7:0]      a, b, c, d, e, f, g, h,
    output reg [7:0]  y_simple_if,
    output reg [7:0]  y_case,
    output     [7:0]  y_tern,
    output reg [7:0]  y_nested,
    output reg [7:0]  y_deep
);

    // ----------------------------------------------------------------------
    // Pattern 1: if/else MUX
    //   y_simple_if = sel_a ? a : b
    //   ↑ edge labels: a → y [label="sel_a"], b → y [label="!sel_a"]
    // ----------------------------------------------------------------------
    always @(posedge clk) begin
        if (sel_a)
            y_simple_if <= a;
        else
            y_simple_if <= b;
    end

    // ----------------------------------------------------------------------
    // Pattern 2: case MUX (4:1)
    //   y_case = sel_b == 0 ? c : sel_b == 1 ? d : sel_b == 2 ? e : f
    //   ↑ edge labels: c → y ["sel_b == 2'd0"], d → y ["sel_b == 2'd1"], ...
    // ----------------------------------------------------------------------
    always @(posedge clk) begin
        case (sel_b)
            2'd0:    y_case <= c;
            2'd1:    y_case <= d;
            2'd2:    y_case <= e;
            default: y_case <= f;
        endcase
    end

    // ----------------------------------------------------------------------
    // Pattern 3: ternary MUX (combinational, wire)
    //   y_tern = sel_c ? g : h
    //   ↑ edge labels: g → y ["sel_c"], h → y ["!sel_c"]
    // ----------------------------------------------------------------------
    assign y_tern = sel_c ? g : h;

    // ----------------------------------------------------------------------
    // Pattern 4: nested mux (case containing if/else)
    //   y_nested depends on sel_d, then on sel_f
    //   ↑ edge labels should show BOTH outer (sel_d==X) and inner (sel_f) conditions
    // ----------------------------------------------------------------------
    always @(posedge clk) begin
        case (sel_d)
            2'd0:    y_nested <= (sel_f ? a : b);
            2'd1:    y_nested <= (sel_f ? c : d);
            2'd2:    y_nested <= (sel_f ? e : f);
            default: y_nested <= (sel_f ? g : h);
        endcase
    end

    // ----------------------------------------------------------------------
    // Pattern 5: 2-deep case
    //   y_deep depends on sel_d, then on sel_e
    //   ↑ edge labels should show BOTH outer (sel_d==X) and inner (sel_e==Y)
    // ----------------------------------------------------------------------
    always @(posedge clk) begin
        case (sel_d)
            2'd0: begin
                case (sel_e)
                    2'd0:    y_deep <= a;
                    2'd1:    y_deep <= b;
                    default: y_deep <= c;
                endcase
            end
            2'd1: begin
                case (sel_e)
                    2'd0:    y_deep <= d;
                    2'd1:    y_deep <= e;
                    default: y_deep <= f;
                endcase
            end
            default: y_deep <= g;
        endcase
    end

endmodule