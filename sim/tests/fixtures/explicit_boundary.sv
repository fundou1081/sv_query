module srcmod(input logic a, output logic b);
  assign b = a;
endmodule

module dstmod(input logic a, output logic b);
  assign b = a;
endmodule

module top(input logic x, output logic y);
  logic p, q;
  srcmod u0(.a(x), .b(p));
  dstmod u1(.a(q), .b(y));
endmodule
