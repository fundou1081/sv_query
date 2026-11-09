// test_covergroup_builtin_name_shadow fixture (bin 名冲突变体)
// 同一个 coverpoint 的 bin 名与 CovergroupBody 内建成员 `start` / `stop`
// 冲突 → pyslang 的 binsof 成员查找解析不到该 bin → InvalidBinsTarget。
//
// 对应 OpenTitan hw/ip/i2c/dv/env/i2c_env_cov.sv:255-270:
//   cp_action : coverpoint signal {
//     bins none = {2'b00}; bins stop = {2'b10};
//     bins start = {2'b01}; bins rstart = {2'b11};
//   }
//   cross cp_abyte, cp_action {
//     bins write_address_byte = binsof(cp_action.start);   // ← 冲突
//     bins data_byte = binsof(cp_action.none);             // ← 不冲突 (对照)
//   }
module top(input logic clk, input logic [1:0] sig);

  covergroup cg @(posedge clk);
    cp_action : coverpoint sig {
      bins none   = {2'b00};
      bins start  = {2'b01};
      bins stop   = {2'b10};
      bins rstart = {2'b11};
    }
    cp_other : coverpoint sig;
    cross cp_action, cp_other {
      bins write_address_byte = binsof(cp_action.start);
      bins stop_address_byte   = binsof(cp_action.stop);
      bins data_byte           = binsof(cp_action.none);
      bins rstart_byte         = binsof(cp_action.rstart);
    }
  endgroup

  cg cg_inst = new();
endmodule
