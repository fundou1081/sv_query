// orphan_06: compound && in if condition (picorv32 pattern)
module orphan_06(
    input enable, ready, valid,
    output reg [7:0] y
);
    always @(*) begin
        if (enable && ready && valid)
            y = 8'd1;
        else
            y = 8'd0;
    end
endmodule
