module top;
  genvar i;
  for (i = 0; i < 2; i = i + 1) begin
    logic x;
    assign x = 1'b0;
  end

  if (1) begin
    logic y;
    assign y = 1'b1;
  end
endmodule
