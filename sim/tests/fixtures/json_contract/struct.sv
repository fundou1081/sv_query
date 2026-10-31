module child #(parameter int W = 8) (
  input  logic [W-1:0] a,
  output logic [W-1:0] y
);
  assign y = a;
endmodule

module top;
  child #(.W(4)) u (.a(4'd0), .y());
endmodule
