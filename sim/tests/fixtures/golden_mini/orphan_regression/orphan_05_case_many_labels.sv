// orphan_05: case with many label items (pa_fcnvt pattern)
module orphan_05(
    input [4:0] sel,
    output reg [3:0] y
);
    always @(*) begin
        case (1'b1)
            sel[0]: y = 4'd1;
            sel[1]: y = 4'd2;
            sel[2]: y = 4'd3;
            sel[3]: y = 4'd4;
            sel[4]: y = 4'd5;
            default: y = 4'd0;
        endcase
    end
endmodule
