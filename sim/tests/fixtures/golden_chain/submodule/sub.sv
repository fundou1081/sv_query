`timescale 1ns/1ps
module sub (
    input  wire [7:0] a_i,
    output wire [7:0] b_o
);
    assign b_o = a_i + 8'h1;
endmodule
