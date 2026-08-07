// golden_dataflow_15_nested_ifelse.sv — 多层嵌套 if-else
module nested_ifelse(
    input clk, rst_n,
    input [7:0] a, b, c, d,
    input [1:0] mode,
    output reg [7:0] y
);
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            y <= 8'd0;
        end else if (mode == 2'b00) begin
            if (a > b)
                y <= a;
            else
                y <= b;
        end else if (mode == 2'b01) begin
            if (c > 8'd100)
                y <= c - d;
            else
                y <= c + d;
        end else begin
            y <= a + b + c;
        end
    end
endmodule
