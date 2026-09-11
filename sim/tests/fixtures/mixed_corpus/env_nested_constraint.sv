// mixed_corpus/02: env{packet p (带约束); cg} — Q3 嵌套实例约束解析 (iter_168 M8B)
class packet;
  rand bit [7:0] addr;
  constraint c_addr { addr inside {[16:32]}; }
  function void set(input bit [7:0] d);
    addr = d;
  endfunction
endclass

class tb_env;
  packet p;
  covergroup cg_env;
    cp_p: coverpoint p.addr;
  endgroup
  function new();
    p = new();
    cg_env = new();
  endfunction
  function void drive(input bit [7:0] d);
    p.set(d);
  endfunction
endclass

module top(input bit clk, input bit [7:0] din);
  tb_env e = new();
  always_ff @(posedge clk) begin
    e.drive(din);
  end
endmodule
