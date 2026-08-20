// orphan_07: ternary inside generate_for (prim_arbiter pattern)
module orphan_07 #(parameter N = 4) (
    input [N-1:0] req,
    output [N-1:0] mask
);
    genvar i;
    generate
        for (i = 0; i < N; i = i + 1) begin : gen_mask
            assign mask[i] = req[i] ? 1'b1 : 1'b0;
        end
    endgenerate
endmodule
