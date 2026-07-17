`timescale 1ns/1ps
module if_demo(input clk, input sel, input [7:0] a, b, output reg [7:0] y);
    always @(posedge clk)
        if (sel) y <= a;
        else     y <= b;
endmodule
