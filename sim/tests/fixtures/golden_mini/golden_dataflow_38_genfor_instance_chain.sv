// golden_dataflow_38_genfor_instance_chain.sv — generate-for 实例化链 (iter_109 修复)
// 1:1 预期 (iter_109 实测):
//   - 实例: top.g[0..3].U 各带端口 x/xo (路径区分, 不再折叠成单个 top.g.U)
//   - 连接: top.arr[i]→g[i].U.x (input CONNECTION) + g[i].U.xo→top.arr[i+1] (output)
//   - 子模块 rot 内部: rot.x→rot.xo DRIVER
//   - 链完整: a→arr[0]→U0→arr[1]→U1→arr[2]→U2→arr[3]→U3→arr[4]→out
module rot(input [7:0] x, output [7:0] xo);
  assign xo = x + 8'd1;
endmodule
module top(input [7:0] a, output [7:0] out);
  wire [7:0] arr [0:4];
  genvar i;
  generate for (i=0;i<4;i=i+1) begin : g
    rot U (.x(arr[i]), .xo(arr[i+1]));
  end endgenerate
  assign arr[0] = a;
  assign out = arr[4];
endmodule
