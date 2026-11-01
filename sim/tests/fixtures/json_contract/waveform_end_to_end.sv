typedef enum logic [1:0] {IDLE=0, RUN=1, DONE=2} state_t;
typedef struct packed { logic [3:0] a; logic [3:0] b; } pair_t;

interface bus_if(input logic clk);
  logic [7:0] data;
  logic valid;
  modport master(output data, output valid, input clk);
endinterface

module producer(bus_if.master m);
  assign m.data = 8'd1;
  assign m.valid = 1'b1;
endmodule

module top(input logic clk, input state_t st, input pair_t p);
  bus_if u_if(.clk(clk));
  producer u_prod(.m(u_if.master));

  logic [7:0] gen_sig;
  logic [7:0] arr [0:3];
  genvar i;
  for (i = 0; i < 2; i = i + 1) begin
    logic x;
    assign x = 1'b0;
  end
  if (1) begin : gen_if
    logic y;
    assign y = 1'b1;
  end
endmodule
