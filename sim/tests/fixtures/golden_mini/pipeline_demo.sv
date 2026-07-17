`timescale 1ns/1ps
module pipeline_demo(input clk, input [7:0] din, output [7:0] dout);
    reg [7:0] s1,s2;
    always @(posedge clk) begin s1<=din; s2<=s1; end
    assign dout = s2;
endmodule
