// golden_dataflow_22_case_if_nested.sv — case 内嵌 if + 三目
module case_if_nested(
    input [1:0] sel,
    input [7:0] a, b, c, d,
    input flag,
    output reg [7:0] y
);
    always @(*) begin
        case (sel)
            2'b00: y = a;
            2'b01: begin
                if (flag)
                    y = a + b;
                else
                    y = a - b;
            end
            2'b10: y = flag ? (c + d) : (c - d);
            default: y = a & b;
        endcase
    end
endmodule
