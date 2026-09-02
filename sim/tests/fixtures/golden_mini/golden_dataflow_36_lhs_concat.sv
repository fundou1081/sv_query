// golden_dataflow_36_lhs_concat.sv — LHS 拼接位置映射 1:1 truth
// 1:1 预期 (iter_101 缺陷 C 修复后实测):
//   - 节点: lhs_concat.a / b / y_hi / y_lo (4)
//   - 边: a→y_hi, b→y_lo (位置对齐, 无笛卡尔积跨边)
module lhs_concat(input [7:0] a, b, output [7:0] y_hi, y_lo);
    assign {y_hi, y_lo} = {a, b};
endmodule
