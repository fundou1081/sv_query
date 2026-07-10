`timescale 1ns/1ps
// [Golden Testcase 1] NORMAL — all signals properly connected, no anomalies
module normal (
    input  wire clk_i,
    input  wire rst_ni,
    input  wire [7:0] data_i,
    input  wire       valid_i,
    output wire [7:0] data_o,
    output wire       valid_o
);
    reg [7:0] data_reg;
    reg       valid_reg;

    always @(posedge clk_i or negedge rst_ni) begin
        if (!rst_ni) begin
            data_reg  <= 8'h0;
            valid_reg <= 1'b0;
        end else if (valid_i) begin
            data_reg  <= data_i;
            valid_reg <= 1'b1;
        end
    end

    assign data_o  = data_reg;
    assign valid_o = valid_reg;
endmodule
