// probe_generate_case_wire.sv — generate-case 单块内 wire 声明 (iter_107 #24 验证)
// SEL=2 → gen_use2 激活 (wire prod2 = a - b); gen_use1/gen_default 未实例化
module probe_gen_case_wire #(parameter SEL = 2) (input wire [3:0] a, b, output wire [3:0] y);
  generate
    case (SEL)
      1: begin : g_use1
        wire prod1 = a & b;
      end
      2: begin : g_use2
        wire prod2 = a - b;
      end
      default: begin : g_def
        wire prod_d = a | b;
      end
    endcase
  endgenerate
  assign y = (SEL == 2) ? g_use2.prod2 : a;
endmodule
