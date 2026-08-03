// golden_dataflow_10_function.sv — function 函数调用
module with_function(
    input [7:0] a, b, c,
    output [7:0] y,
    output [7:0] z
);
    // 简单 function
    function [7:0] add_sat(input [7:0] x, y);
        begin
            add_sat = (x + y > 8'd255) ? 8'd255 : (x + y);
        end
    endfunction

    assign y = add_sat(a, b);           // 函数调用 (饱和加)
    assign z = (a * b) + c;             // 对比: 普通运算
endmodule
