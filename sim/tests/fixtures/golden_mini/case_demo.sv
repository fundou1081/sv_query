`timescale 1ns/1ps
module case_demo(input clk, input [1:0] op, input [7:0] d0,d1,d2,d3, output reg [7:0] y);
    always @(posedge clk)
        case(op) 2'd0: y<=d0; 2'd1: y<=d1; 2'd2: y<=d2; default: y<=d3; endcase
endmodule
