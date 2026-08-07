// golden_dataflow_17_if_case_mixed.sv — if + case 混合
module if_case_mixed(
    input clk, rst_n, en,
    input [1:0] mode,
    input [7:0] a, b, c,
    output reg [7:0] y
);
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            y <= 8'd0;
        end else if (en) begin
            case (mode)
                2'b00: y <= a + b;
                2'b01: y <= a - c;
                2'b10: y <= a * 8'd2;
                default: y <= a;
            endcase
        end else begin
            y <= b;
        end
    end
endmodule
