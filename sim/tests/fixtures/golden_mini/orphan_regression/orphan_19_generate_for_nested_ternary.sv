// orphan_19: nested ternary inside generate_for
module orphan_19 #(parameter N = 2) (
    input [N-1:0] req0, req1,
    output [N-1:0] grant0, grant1
);
    genvar i;
    generate
        for (i = 0; i < N; i = i + 1) begin : gen_arb
            assign grant0[i] = (req0[i] && !req1[i]) ? 1'b1 : 1'b0;
            assign grant1[i] = (req1[i] && !req0[i]) ? 1'b1 : 1'b0;
        end
    endgenerate
endmodule
