module top(input logic a, output logic b);
  logic x, y;
  assign x = y;
  assign y = x;
  assign b = x;
endmodule
