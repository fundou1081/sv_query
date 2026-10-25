// generate_forms: for / if / case generate + 块内局部信号 (iter_274 修复点)
module leaf (input a, output y);
  assign y = a;
endmodule

module top #(parameter N = 4) (input [N-1:0] din, output [N-1:0] dout);
  genvar i;
  generate
    for (i = 0; i < N; i = i + 1) begin : G
      wire local_wire;
      assign local_wire = din[i];
      leaf u_leaf (.a(local_wire), .y(dout[i]));
    end
    if (N > 2) begin : GEN_IF
      wire if_local;
      assign if_local = din[0];
    end
    case (N)
      4: begin : GEN_CASE
        wire case_local;
        assign case_local = din[1];
      end
      default: begin : GEN_DEF
        wire default_local;
        assign default_local = din[2];
      end
    endcase
  endgenerate
endmodule
