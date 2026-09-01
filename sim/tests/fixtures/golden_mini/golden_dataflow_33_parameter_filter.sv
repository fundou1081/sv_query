// golden_dataflow_33_parameter_filter.sv — parameter/localparam 过滤 1:1 truth
// 1:1 预期 (iter_093 实测):
//   - 节点: param_filter.a / b / y / y.ternary_SAT_VAL_a
//   - parameter WIDTH / SAT_VAL / localparam ZERO **都不作为信号节点出现** (过滤)
//   - 条件字符串保留参数名: '!(a > SAT_VAL)' (不解析为字面量)
//   - 无 8'd0 常量边: ternary 真分支 ZERO (localparam) 未提取 (当前行为, 已知 quirk)
module param_filter #(parameter WIDTH = 8, parameter SAT_VAL = 8'd255) (
    input [WIDTH-1:0] a, b,
    output [WIDTH-1:0] y
);
    localparam ZERO = 8'd0;
    assign y = (a > SAT_VAL) ? ZERO : a + b;
endmodule
