module combined(input [7:0] a, b, c, output [15:0] y);
    wire [15:0] sum = a + b;
    wire [15:0] prod = sum * c;
    assign y = prod[15:8] + 8'd128;
endmodule