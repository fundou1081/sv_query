// orphan_24: priority encoder (chained ternary pattern, common in picorv32)
module orphan_24(
    input [3:0] req,
    output reg [1:0] grant_idx,
    output reg grant_valid
);
    always @(*) begin
        grant_valid = |req;
        grant_idx = req[3] ? 2'd3 :
                    req[2] ? 2'd2 :
                    req[1] ? 2'd1 :
                    req[0] ? 2'd0 : 2'd0;
    end
endmodule
