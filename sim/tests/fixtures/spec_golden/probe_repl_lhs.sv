// probe_repl_lhs.sv — SV 标准禁止: Replication 作 LHS (反例 probe)
// [iter_082] 补缺失 fixture + 实测修正:
//   - 原测试引用 /tmp/spec_probe_repl_lhs.sv (幽灵文件, 从未创建)
//   - pyslang 实测: 等宽复制 {4{q}} = q 报 "expression is not assignable"
//     (ExpressionNotAssignable); 非等宽 {4{q},4{q},4{q}} = q 竟被接受
//   - 正例对照: probe_replication_rhs.sv (RHS 合法)
module probe_repl_lhs(input wire [7:0] q, output wire [7:0] y);
  assign {4{q}} = q;  // 非法: replication 作 LHS
endmodule
