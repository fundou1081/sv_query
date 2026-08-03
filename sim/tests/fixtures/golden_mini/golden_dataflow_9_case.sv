// golden_dataflow_9_case.sv — case 多路选择
module with_case(
    input [1:0] sel,
    input [7:0] a, b, c, d,
    output reg [7:0] y
);
    always @(*) begin
        case (sel)
            2'b00: y = a;
            2'b01: y = a + b;
            2'b10: y = c;
            default: y = d;
        endcase
    end
endmodule
