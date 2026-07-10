`timescale 1ns/1ps
// [Golden Testcase 4] ORPHAN — wires with no in AND no out
// Note: truly unused wires are optimized away by pyslang.
// We force retention via $unused system task hint.
module orphan (
    input  wire clk_i,
    input  wire rst_ni,
    input  wire [7:0] data_i,
    output wire [7:0] data_o
);
    reg [7:0] data_reg;
    always @(posedge clk_i or negedge rst_ni) begin
        if (!rst_ni) data_reg <= 8'h0;
        else         data_reg <= data_i;
    end

    // Use these wires in expressions to prevent pyslang optimization
    // but contribute to no functional logic:
    wire [7:0] isolated_a;
    wire [7:0] isolated_b;
    wire [7:0] chain_wire;
    assign chain_wire = isolated_a | isolated_b;  // both feeds into chain_wire
    // chain_wire is also ORPHAN (no consumer) — should have in=1 (from | op), out=0

    assign data_o = data_reg;
endmodule
