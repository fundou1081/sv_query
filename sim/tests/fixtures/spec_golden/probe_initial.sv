// 反例: initial 块
module probe_initial(input wire clk, output reg q);
  always_ff @(posedge clk) q <= ~q;
  initial q = 1'b0;  // 期望: 不被支持 (driver_extractor.py:3346-3349 显式 pass)
endmodule
