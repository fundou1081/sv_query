`timescale 1ns/1ps
module ternary_demo(input sel, input [7:0] a,b, output [7:0] y);
    assign y = sel ? a : b;
endmodule
