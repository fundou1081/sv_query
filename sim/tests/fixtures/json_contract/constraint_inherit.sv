class base;
  rand int x;
  constraint c_base { x > 0; }
endclass
class child extends base;
  rand int y;
  constraint c_child { y > x; }
endclass
module top; child c = new(); endmodule
