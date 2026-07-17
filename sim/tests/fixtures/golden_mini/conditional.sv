`timescale 1ns/1ps

// ============================================================
// Golden Mini #1: if-else conditional dataflow
// Demonstrates: dataflow branching through if-else
//   sel_i decides whether output is a_i or b_i
// ============================================================

module if_conditional(
    input  wire        clk,
    input  wire        rst_n,
    input  wire        sel_i,
    input  wire [7:0]  a_i,
    input  wire [7:0]  b_i,
    output reg  [7:0]  y_o
);
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            y_o <= 0;
        else if (sel_i)
            y_o <= a_i;       // dataflow path: a_i -> y_o when sel_i=1
        else
            y_o <= b_i;       // dataflow path: b_i -> y_o when sel_i=0
    end
endmodule


// ============================================================
// Golden Mini #2: case statement dataflow
// Demonstrates: dataflow routing through case selector
//   op_i selects one of 4 sources to drive y_o
// ============================================================

module case_routing(
    input  wire        clk,
    input  wire        rst_n,
    input  wire [1:0]  op_i,
    input  wire [7:0]  src_0_i,
    input  wire [7:0]  src_1_i,
    input  wire [7:0]  src_2_i,
    input  wire [7:0]  src_3_i,
    output reg  [7:0]  y_o
);
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            y_o <= 0;
        else
            case (op_i)
                2'b00:   y_o <= src_0_i;     // path: src_0_i -> y_o
                2'b01:   y_o <= src_1_i;     // path: src_1_i -> y_o
                2'b10:   y_o <= src_2_i;     // path: src_2_i -> y_o
                default: y_o <= src_3_i;     // path: src_3_i -> y_o
            endcase
    end
endmodule


// ============================================================
// Golden Mini #3: ternary operator dataflow
// Demonstrates: combinational select via "? :" operator
//   y_o = sel_i ? a_i : b_i   (no clock, no reset)
// ============================================================

module ternary_select(
    input  wire        sel_i,
    input  wire [7:0]  a_i,
    input  wire [7:0]  b_i,
    output wire [7:0]  y_o
);
    assign y_o = sel_i ? a_i : b_i;
    // Combinational: y_o driven by either a_i or b_i
endmodule


// ============================================================
// Golden Mini #4: simple 3-stage pipeline
// Demonstrates: dataflow propagation through pipeline registers
//   data_i -> stage1 -> stage2 -> stage3 -> data_o
// ============================================================

module pipeline_3stage(
    input  wire        clk,
    input  wire        rst_n,
    input  wire [7:0]  data_i,
    input  wire        valid_i,
    output wire [7:0]  data_o,
    output reg         valid_o
);
    reg [7:0] stage1_data;
    reg [7:0] stage2_data;
    reg [7:0] stage3_data;
    reg       stage1_valid;
    reg       stage2_valid;
    reg       stage3_valid;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            stage1_data <= 0; stage1_valid <= 0;
            stage2_data <= 0; stage2_valid <= 0;
            stage3_data <= 0; stage3_valid <= 0;
            valid_o     <= 0;
        end else begin
            stage1_data <= data_i;
            stage1_valid <= valid_i;
            stage2_data <= stage1_data;
            stage2_valid <= stage1_valid;
            stage3_data <= stage2_data;
            stage3_valid <= stage2_valid;
            valid_o     <= stage3_valid;
        end
    end

    assign data_o = stage3_data;
endmodule
