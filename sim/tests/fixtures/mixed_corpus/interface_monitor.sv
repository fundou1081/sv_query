// mixed_corpus/05: interface 成员 + module cg + 子模块层次 (iter_167 C1)
module sub(input bit clk, input logic [7:0] vin, output logic [7:0] vout);
  logic [7:0] mid;
  assign mid = vin + 1;
  assign vout = mid;
  covergroup cg_sub @(posedge clk);
    cp: coverpoint mid;
  endgroup
endmodule

module top(input bit clk, input logic [7:0] din);
  logic [7:0] out;
  sub u_sub(.clk(clk), .vin(din), .vout(out));
endmodule
