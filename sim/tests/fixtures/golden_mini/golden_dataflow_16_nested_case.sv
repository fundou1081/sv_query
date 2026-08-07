// golden_dataflow_16_nested_case.sv — 嵌套 case (case 内嵌 case)
module nested_case(
    input [1:0] sel,
    input [1:0] sub_sel,
    input [7:0] a, b, c, d,
    output reg [7:0] y
);
    always @(*) begin
        case (sel)
            2'b00: y = 8'd0;
            2'b01: begin
                case (sub_sel)
                    2'b00: y = a + b;
                    2'b01: y = a - b;
                    default: y = a;
                endcase
            end
            2'b10: begin
                case (sub_sel)
                    2'b00: y = c & d;
                    2'b01: y = c | d;
                    default: y = c;
                endcase
            end
            default: y = 8'd255;
        endcase
    end
endmodule
