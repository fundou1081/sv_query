module top(input [7:0] a, output [7:0] y);
  assign y[3:0] = a[7:4];
endmodule
