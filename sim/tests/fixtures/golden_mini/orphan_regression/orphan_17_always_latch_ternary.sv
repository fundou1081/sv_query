// orphan_17: ternary in always with latch-style assignment
module orphan_17(
    input en, sel,
    input [7:0] a, b,
    output reg [7:0] y
);
    always @(*) begin
        if (en)
            y = sel ? a : b;
    end
endmodule