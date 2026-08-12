// case30: generate if (编译期条件分支)
// generate_if_demo: 根据 MODE 参数选择 adder 还是 subtractor
//   genvar no genvar (single iteration per branch)
//   if (MODE == 1) begin : gen_adder
//     assign result = op1 + data;     // ONLY this branch active when MODE=1
//   end else begin : gen_subtractor
//     assign result = op2 - data;     // NOT instantiated
//   end
// 期望: pyslang 只 collect gen_adder 内的 assign, gen_subtractor 不出现

module generate_if_demo #(
    parameter MODE = 1,
    parameter W = 8
) (
    input  [W-1:0] data,
    input  [W-1:0] weights,
    output [W-1:0] result
);
    wire [W-1:0] op1;
    wire [W-1:0] op2;

    assign op1 = data + weights;
    assign op2 = data - weights;

    generate
        if (MODE == 1) begin : gen_adder
            assign result = op1 + data;
        end else begin : gen_subtractor
            assign result = op2 - data;
        end
    endgenerate
endmodule
