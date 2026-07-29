// nested_if.sv — 嵌套 if 测试
// 预期: it_a→q 有 2 条路径，分别对应 inner if 的分支
module nested_if(
    input  wire       sel_a,
    input  wire       sel_b,
    input  wire [7:0] it_a,
    input  wire [7:0] it_b,
    output reg  [7:0] q
);
    always @* begin
        if (sel_a) begin
            if (sel_b)
                q = it_a;
            else
                q = it_b;
        end else begin
            q = 8'd0;
        end
    end
endmodule
