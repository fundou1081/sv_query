// golden_dataflow_8_ifelse.sv — if-else 条件判断
module with_ifelse(
    input [7:0] a, b, c,
    input clk, rst_n,
    output reg [7:0] y
);
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            y <= 8'd0;          // 复位
        end else if (a > 8'd10) begin
            y <= a + b;         // 条件分支1
        end else begin
            y <= c;             // 条件分支2
        end
    end
endmodule
