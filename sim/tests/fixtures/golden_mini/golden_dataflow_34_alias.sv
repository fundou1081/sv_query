// golden_dataflow_34_alias.sv — alias 方向语义 1:1 truth
// 1:1 预期 (iter_094 实测):
//   - 节点: alias_demo.a / b / t / x / y / z (6)
//   - 边: a→x, b→y, b→t, t→z (4 DRIVER) — SV 规范方向: alias LHS=target, RHS=source
//   - 链: b → t → z (alias 传递)
module alias_demo(input a, b, output x, y, z);
    alias x = a;
    alias y = b;
    wire t;
    alias t = b;
    alias z = t;
endmodule
