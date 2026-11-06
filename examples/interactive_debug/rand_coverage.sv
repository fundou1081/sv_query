// Interactive debug scenarios 2/3: rand variables, inherited constraints, coverage mapping.
class base;
  rand int addr;
  constraint c_base { addr inside {[16:32]}; }
endclass

class packet extends base;
  rand bit [7:0] len;
  constraint c_packet { len < 64; addr != 0; }
endclass

class tb_env;
  packet p;
  covergroup cg;
    cp_addr: coverpoint p.addr {
      bins low[]  = {[16:24]};
      bins high[] = {[25:32]};
    }
    cp_len: coverpoint p.len {
      bins len_small[] = {[0:31]};
      bins len_large[] = {[32:63]};
    }
    cross cp_addr, cp_len;
  endgroup
  function new();
    p = new();
    cg = new();
  endfunction
endclass

module top;
  tb_env e = new();
endmodule
