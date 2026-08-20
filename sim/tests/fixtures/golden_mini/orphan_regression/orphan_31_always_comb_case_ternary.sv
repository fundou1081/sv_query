// orphan_31: case+ternary in always_comb with parameter
module orphan_31 #(parameter W = 4) (
    input [W-1:0] sel,
    input [7:0] a, b, c, d,
    output reg [7:0] y
);
    always @(*) begin
        case (sel)
            4'd0: y = a + b;
            4'd1: y = (a > b) ? a : b;
            4'd2: y = (c > d) ? c : d;
            default: y = 8'd0;
        endcase
    end
endmodule
