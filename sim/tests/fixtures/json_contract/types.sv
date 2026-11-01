typedef enum logic [1:0] {IDLE=0, RUN=1, DONE=2} state_t;
typedef struct packed { logic [3:0] a; logic [3:0] b; } pair_t;
module top(input logic clk, input state_t st, input pair_t p, input logic [7:0] arr [0:3], output logic [7:0] y);
  assign y = {p.a, p.b};
endmodule
