// case31: generate case (编译期 case 匹配)
// generate_case_demo: 根据 SEL 参数选择不同实现
//   genvar no genvar (single iteration per branch)
//   case (SEL)
//     1: begin : gen_adder       // NOT instantiated (SEL=2)
//       assign result = op1 + data;
//     end
//     2: begin : gen_subtractor  // ACTIVE branch
//       assign result = op2 - data;
//     end
//     default: begin : gen_default   // NOT instantiated
//       assign result = data;
//     end
//   endcase
// 期望: pyslang 只 collect gen_subtractor 的 assign, 其他 branch 不出现

module generate_case_demo #(
    parameter SEL = 2,
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
        case (SEL)
            1: begin : gen_adder
                assign result = op1 + data;
            end
            2: begin : gen_subtractor
                assign result = op2 - data;
            end
            default: begin : gen_default
                assign result = data;
            end
        endcase
    endgenerate
endmodule
