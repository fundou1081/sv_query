module leaf(input logic a, output logic b);
  assign b = a;
endmodule
module top(input logic x, output logic y);
  logic w;
  leaf u0(.a(x), .b(w));
  leaf u1(.a(w), .b(y));
endmodule
