// test_covergroup_limitation fixture
// Covergroup body 里出现与 CovergroupBody 内建成员同名的标识符
// (IEEE 1800-2017 §19.6: start / stop / sample / get_coverage /
//  get_inst_coverage / set_inst_name)。
//
// pyslang 在 covergroup body 的**无限定名查找**中先命中这些内建成员,
// 遮蔽 (shadow) 外层作用域 (module port / class member / sample 形参)
// 的同名标识符 → 表达式类型被解析为 void →
//   InvalidCoverageExpr + VoidAssignment (coverpoint 层)
//   InvalidBinsTarget                (binsof 层)
//   InvalidCoverageExpr + VoidAssignment (cross cross_item 层)
//
// 形态对齐 OpenTitan hw/ip/i2c/dv/env/i2c_env_cov.sv:197-235。
module top(input logic clk,
           input logic [7:0] fbyte,
           input logic start,
           input logic stop,
           input logic read,
           input logic rcont,
           input logic nakok,
           input logic ack_int_recv);

  covergroup cg @(posedge clk);
    cp_fbyte : coverpoint fbyte;
    cp_start : coverpoint start;
    cp_stop  : coverpoint stop;
    cp_read  : coverpoint read;
    cp_rcont : coverpoint rcont;
    cp_nakok : coverpoint nakok;
    cp_ack : coverpoint ack_int_recv;
    cross cp_fbyte, start, stop, read, rcont, nakok, cp_ack {
      bins data_byte = binsof(start) intersect {0};
      bins stop_byte  = binsof(stop)  intersect {1};
    }
  endgroup

  cg cg_inst = new();
endmodule
