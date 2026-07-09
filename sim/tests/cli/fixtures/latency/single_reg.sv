//=============================================================================
// single_reg.sv - Golden fixture 1: single register pipeline
// Expected: chain shows 1 REG node, Total cycles: 1
//=============================================================================
module top(
    input  wire       clk,
    input  wire       d,
    output reg        q
);
    // 1 reg in pipeline: q <- a (registered)
    always_ff @(posedge clk) begin
        q <= d;
    end
endmodule
