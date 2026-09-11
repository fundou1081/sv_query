// mixed_corpus/01: env{packet p; cg on p.addr} + module 驱动链 (iter_168 M8)
// 验收: packet 的 cg auto 落到活对象 top.e.p.addr; Q1 fanin 贯通 din
class packet;
  rand bit [7:0] addr;
  covergroup cg_p;
    cp: coverpoint addr;
  endgroup
  function new(); cg_p = new(); endfunction
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
