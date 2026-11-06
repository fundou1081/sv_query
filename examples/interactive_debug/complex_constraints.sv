// Complex random constraint neighborhood: inheritance, multi-var blocks, conditional constraint.
class base_item;
  rand int addr;
  rand int len;
  constraint c_addr { addr inside {[32:128]}; }
  constraint c_len  { len inside {[1:64]}; }
endclass

class packet extends base_item;
  rand bit [7:0] mode;
  rand bit [7:0] payload;
  constraint c_order { addr < len; }
  constraint c_mode  {
    if (mode == 0) { len < 32; }
    else           { len >= 32; }
  }
  constraint c_payload { payload > 0; }
endclass

class env;
  packet p;
  function new();
    p = new();
  endfunction
endclass

module top;
  env e = new();
endmodule
