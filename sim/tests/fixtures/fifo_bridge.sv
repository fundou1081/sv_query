module fifo_sync (
  input  logic [7:0] wdata_i,
  output logic [7:0] rdata_o
);
endmodule

module top(input logic [7:0] din, output logic [7:0] dout);
  logic [7:0] w, r;
  assign w = din;
  fifo_sync u_fifo(.wdata_i(w), .rdata_o(r));
  assign dout = r;
endmodule
