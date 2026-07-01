// OpenTitan prim_arbiter_tree.sv — Phase 2 Golden Test Filelist (2026-07-01)
// 
// Scope: 1 个 sub-project (prim_arbiter_tree, 291 行, ~32 个 internal 变量)
// 3 个 Golden case:
//   - data_o (32-bit DATA): cross-module output port of arbiter
//   - idx_o  (3-bit CONTROL): winner index of arbitration
//   - clk_i  (1-bit CONTROL): standard clock input
//
// 这个 filelist 只指向 `prim_arbiter_tree.sv` 主模块. 
// 它 `include <prim_util_pkg.svh>` 等 core helper SV.
// (sv_query 会自动 -I include dirs.)

/Users/fundou/my_dv_proj/opentitan/hw/ip/prim/rtl/prim_arbiter_tree.sv
