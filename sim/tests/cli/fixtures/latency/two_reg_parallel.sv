//=============================================================================
// two_reg_parallel.sv - Golden fixture 3: 2 parallel branches with reg at end
// Expected: chain shows 2 REG nodes (a, b) feeding combinational logic into q
//=============================================================================
module top(
    input  wire        clk,
    input  wire [7:0]  d1,
    input  wire [7:0]  d2,
    output reg  [7:0]  q
);
    reg [7:0] a, b;
    always_ff @(posedge clk) begin
        a <= d1;
        b <= d2;
    end
    // Combinational merge: q = a + b (registered)
    always_ff @(posedge clk) begin
        q <= a + b;
    end
endmodule
