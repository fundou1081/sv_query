module top(input logic [1:0] a, output logic [1:0] b);
  logic [1:0] bus;
  assign bus[0] = a[0];
  assign bus[1] = a[1];
  assign b = bus;
endmodule
