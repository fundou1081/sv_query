// golden_dataflow_13_complex.sv — 复杂复合场景
module complex_design(
    input clk, rst_n,
    input [7:0] data_in, offset, scale, threshold,
    input [1:0] mode,
    input en, valid,
    output reg [7:0] result,
    output reg overflow
);
    // 中间运算
    wire [7:0] scaled   = data_in * scale;
    wire [8:0] shifted  = scaled + offset;
    wire [7:0] clamped  = (shifted > 9'd255) ? 8'd255 : shifted[7:0];
    wire [7:0] data_minus_1 = data_in - 8'd1;

    // function: 饱和处理
    function [7:0] saturate(input [8:0] val);
        saturate = (val > 9'd255) ? 8'd255 : val[7:0];
    endfunction

    wire [7:0] data_sat = saturate({1'b0, data_in} + offset);

    // 嵌套三目+条件选择
    always_comb begin
        case (mode)
            2'd0: result = data_in;
            2'd1: result = scaled;
            2'd2: result = valid ? data_minus_1 : offset;
            2'd3: result = data_sat;
            default: result = data_in;
        endcase
    end

    // if-else 溢出检测
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            overflow <= 1'b0;
        else if (en)
            overflow <= (shifted > 9'd255) || (scaled > 8'd250);
    end
endmodule
