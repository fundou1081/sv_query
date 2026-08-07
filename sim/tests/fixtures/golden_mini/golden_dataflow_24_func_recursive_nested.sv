// golden_dataflow_24_func_recursive_nested.sv — 函数嵌套调用 + case 内函数
module func_recursive_nested(
    input [7:0] a, b, c,
    input [1:0] mode,
    output reg [7:0] y,
    output [7:0] z
);
    // 取大
    function [7:0] max2(input [7:0] x, y);
        max2 = (x > y) ? x : y;
    endfunction

    // 取小
    function [7:0] min2(input [7:0] x, y);
        min2 = (x < y) ? x : y;
    endfunction

    // 饱和差
    function [7:0] sat_sub(input [7:0] x, y);
        sat_sub = (x > y) ? (x - y) : 8'd0;
    endfunction

    // 嵌套函数调用 + 三目
    function [7:0] mix(input [7:0] x, y, zz);
        mix = (x > 8'd128) ? max2(x, y) : min2(y, zz);
    endfunction

    assign z = sat_sub(max2(a, b), c);         // 函数嵌套: 大值减c

    always @(*) begin
        case (mode)
            2'b00: y = max2(a, b);
            2'b01: y = min2(a, c);
            2'b10: y = mix(a, b, c);
            2'b11: y = sat_sub(a, b);
            default: y = a;
        endcase
    end
endmodule
