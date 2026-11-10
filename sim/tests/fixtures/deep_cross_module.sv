module leaf(input logic a, output logic b);
  assign b = a;
endmodule

module mid(input logic a, output logic b);
  leaf u_leaf(.a(a), .b(b));
endmodule

module top(input logic x, output logic y);
  mid u_mid(.a(x), .b(y));
endmodule
