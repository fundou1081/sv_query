// orphan_25: priority encoder inside always_ff
module orphan_25(
    input clk, rst_n,
    input [3:0] req,
    output reg [1:0] grant_idx,
    output reg grant_valid
);
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            grant_idx <= 2'd0;
            grant_valid <= 1'b0;
        end else begin
            grant_valid <= |req;
            grant_idx <= req[3] ? 2'd3 :
                         req[2] ? 2'd2 :
                         req[1] ? 2'd1 :
                         req[0] ? 2'd0 : 2'd0;
        end
    end
endmodule
