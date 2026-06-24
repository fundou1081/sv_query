// multi_pkg_a.sv - 测试 pkg::type_t + 跨包 typedef
package types_a_pkg;
    typedef logic [31:0] word_t;
    typedef logic [15:0] halfword_t;
endpackage

package types_b_pkg;
    // typedef → typedef 跨包
    typedef types_a_pkg::word_t b_word_t;
    typedef types_a_pkg::halfword_t b_halfword_t;
endpackage

// 3rd package 通过 typedef → typedef chain
package types_c_pkg;
    typedef types_b_pkg::b_word_t c_word_t;
    typedef types_b_pkg::b_halfword_t c_halfword_t;
endpackage

// 模拟 ascon 的 `import pkg::*;` 模式 (符号注入 namespace)
module top_import_pattern
  import types_a_pkg::*;
  import types_b_pkg::*;
  import types_c_pkg::*;
#(
    parameter int WIDTH = 32
)(
    input                clk,
    input  word_t        in_a,           // 裸用 types_a_pkg::word_t
    input  b_word_t      in_b,           // 裸用 types_b_pkg::b_word_t
    input  c_word_t      in_c,           // 裸用 types_c_pkg::c_word_t (3 层链)
    output word_t        out_a,
    output b_word_t      out_b,
    output c_word_t      out_c,
    input  [WIDTH-1:0]  data_in
);
    always_ff @(posedge clk) begin
        out_a <= in_a;
        out_b <= in_b;
        out_c <= in_c;
    end
endmodule
