// golden_dataflow_19_function_multi.sv — 多 function + 三目 + 溢出
module function_multi(
    input [7:0] a, b, c,
    input sel,
    output [7:0] y,
    output [7:0] z,
    output overflow
);
    // 饱和加
    function [7:0] sat_add(input [7:0] x, y);
        begin
            sat_add = (x + y > 8'd255) ? 8'd255 : (x + y);
        end
    endfunction

    // 绝对值
    function [7:0] abs_val(input [7:0] x);
        begin
            abs_val = (x[7]) ? 8'd0 - x : x;
        end
    endfunction

    // 限幅
    function [7:0] clamp(input [7:0] x, input [7:0] lo, input [7:0] hi);
        begin
            clamp = (x > hi) ? hi : ((x < lo) ? lo : x);
        end
    endfunction

    assign y = sel ? sat_add(a, b) : abs_val(a);          // 三目 + 函数
    assign z = clamp(sat_add(a, c), 8'd10, 8'd200);        // 函数组合
    assign overflow = (sat_add(a, b) > 8'd200) || (sat_add(c, b) > 8'd200);
endmodule
