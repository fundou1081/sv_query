// comprehensive.sv — 多场景测试用例 (test_dataflow_else_if_comprehensive.py)
// 覆盖: simple if, case (4 items), ternary, 嵌套 4 层, 复合条件 (a&&b), (a||b)
module comprehensive(
    input  wire        a, b, c, d,
    input  wire [3:0]  sel,
    input  wire        en,
    input  wire [7:0]  in_a, in_b, in_c,
    output reg  [7:0]  out_if, out_case, out_ternary, out_nested, out_multi
);
    always @* begin
        // out_if: 简单 if
        if (a)
            out_if = in_a;
        else
            out_if = 8'd0;

        // out_case: case 4 items + default
        case (sel)
            4'b0000: out_case = in_a;
            4'b0001: out_case = in_b;
            4'b0010: out_case = in_c;
            4'b0011: out_case = 8'd0;
            default: out_case = 8'd0;
        endcase

        // out_ternary
        out_ternary = a ? in_a : 8'd0;

        // out_nested: 4 层嵌套
        if (a)
            if (b)
                if (c)
                    if (d)
                        out_nested = in_a;
                    else
                        out_nested = 8'd0;
                else
                    out_nested = 8'd0;
            else
                out_nested = 8'd0;
        else
            out_nested = 8'd0;

        // out_multi: 不同 driver 用不同 in_*
        if (a && b)
            out_multi = in_a;
        else if (c || d)
            out_multi = in_b;
        else
            out_multi = in_c;
    end
endmodule
