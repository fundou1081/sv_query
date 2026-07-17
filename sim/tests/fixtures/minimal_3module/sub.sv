`timescale 1ns/1ps
// Sub module: instantiates leaf_pipeline + leaf_adder (multi-file pattern)
module sub_aggregator(
    input  wire        clk,
    input  wire        rst_n,
    input  wire        valid_i,
    input  wire [7:0]  data_i,
    output wire        ready_o,
    output reg  [7:0]  sum_o
);
    reg ready_q;
    wire leaf_ready;

    leaf_pipeline lp1 (.clk(clk), .rst_n(rst_n), .data_i(valid_i), .data_o(leaf_ready));
    leaf_adder   la1 (.a(data_i), .b(8'd5), .sum(sum_o));

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) ready_q <= 0;
        else ready_q <= leaf_ready;
    end
    assign ready_o = ready_q;
endmodule
