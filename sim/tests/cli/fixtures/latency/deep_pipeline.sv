//=============================================================================
// deep_pipeline.sv - Golden fixture 5: 5-stage deep pipeline
// Expected: chain shows 5 REG nodes (a, b, c, d, q), Total cycles: 5
//=============================================================================
module top(
    input  wire        clk,
    input  wire        d,
    output reg         q
);
    reg a, b, c, d_pipe, e;
    // 5-stage pipeline: d -> a -> b -> c -> d_pipe -> e -> q (5 registers)
    always_ff @(posedge clk) begin
        a <= d;
        b <= a;
        c <= b;
        d_pipe <= c;
        e <= d_pipe;
        q <= e;
    end
endmodule
