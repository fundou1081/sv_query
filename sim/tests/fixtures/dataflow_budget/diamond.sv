// dataflow budget fixture (P158.11.2b)
// 每级把路径数翻倍: s0 -> y 共有 2^7 * 2 = 256 条简单数据路径 (8 级菱形).
// 用途: 验证 dataflow 的 work budget / timeout / max_paths 截断可见.
module diamond_top(input logic a, output logic y);
  logic s0;
  logic p1_0, p1_1;
  logic p2_0, p2_1;
  logic p3_0, p3_1;
  logic p4_0, p4_1;
  logic p5_0, p5_1;
  logic p6_0, p6_1;
  logic p7_0, p7_1;
  logic p8_0, p8_1;
  assign s0 = a;
  assign p1_0 = s0;
  assign p1_1 = s0;
  assign p2_0 = p1_0 | p1_1;
  assign p2_1 = p1_0 | p1_1;
  assign p3_0 = p2_0 | p2_1;
  assign p3_1 = p2_0 | p2_1;
  assign p4_0 = p3_0 | p3_1;
  assign p4_1 = p3_0 | p3_1;
  assign p5_0 = p4_0 | p4_1;
  assign p5_1 = p4_0 | p4_1;
  assign p6_0 = p5_0 | p5_1;
  assign p6_1 = p5_0 | p5_1;
  assign p7_0 = p6_0 | p6_1;
  assign p7_1 = p6_0 | p6_1;
  assign p8_0 = p7_0 | p7_1;
  assign p8_1 = p7_0 | p7_1;
  assign y = p8_0 | p8_1;
endmodule
