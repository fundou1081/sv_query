// orphan_29: priority encoder inside generate_for
module orphan_29 #(parameter N = 4) (
    input [N-1:0] req,
    output reg [1:0] grant_idx [0:N-1]
);
    genvar i;
    generate
        for (i = 0; i < N; i = i + 1) begin : gen_pri
            always @(*) begin
                grant_idx[i] = req[i] ? 2'(i) : 2'd0;
            end
        end
    endgenerate
endmodule
