module probe_repl_rhs(input wire [3:0] q, output wire [11:0] y);
  assign y = {3{q}};  // 合法: RHS replication
endmodule
