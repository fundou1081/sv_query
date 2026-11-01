interface bus_if(input logic clk);
  logic [7:0] data;
  logic valid;
  modport master(output data, output valid, input clk);
  modport slave(input data, input valid, input clk);
endinterface

module producer(bus_if.master m);
  assign m.data = 8'd1;
  assign m.valid = 1'b1;
endmodule

module top(input logic clk);
  bus_if u_if(.clk(clk));
  producer u_prod(.m(u_if.master));
endmodule
