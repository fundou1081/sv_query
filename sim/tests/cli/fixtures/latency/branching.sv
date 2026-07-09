//=============================================================================
// branching.sv - Golden fixture 4: fanout from 1 register to 2 destinations
// Expected: trace fanout shows 1 source REG driving 2 loads
//=============================================================================
module top(
    input  wire       clk,
    input  wire       d,
    output reg        q1,
    output reg        q2
);
    reg a;
    // 1 reg: a -> q1, a -> q2 (both fed from same source register)
    always_ff @(posedge clk) begin
        a <= d;
        q1 <= a;
        q2 <= a;
    end
endmodule
