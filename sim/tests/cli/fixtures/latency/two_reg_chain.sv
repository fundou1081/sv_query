//=============================================================================
// two_reg_chain.sv - Golden fixture 2: 2 registers in serial chain
// Expected: chain shows 2 REG nodes, Total cycles: 2 (d -> a -> b -> q)
//=============================================================================
module top(
    input  wire       clk,
    input  wire       d,
    output reg        q
);
    reg a, b;
    // Pipeline: d -> a -> b -> q (2 registers in series)
    always_ff @(posedge clk) begin
        a <= d;
        b <= a;
        q <= b;
    end
endmodule
