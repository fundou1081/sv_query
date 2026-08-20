// orphan_18: ternary using parameters in condition (picorv32 pattern)
module orphan_18 #(parameter ENABLE = 1, parameter WIDTH = 8) (
    input [WIDTH-1:0] a, b,
    input sel,
    output [WIDTH-1:0] y
);
    assign y = (ENABLE == 1) ? (sel ? a : b) : 8'd0;
endmodule
