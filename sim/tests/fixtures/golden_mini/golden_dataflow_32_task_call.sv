// golden_dataflow_32_task_call.sv — task 调用站点形参映射 (iter_076 修复锁定)
// 1:1 预期 (iter_092 实测):
//   - 节点: top.din, top.dout (module 信号, task 内部 formal 不泄漏)
//   - 边:   top.din -> top.dout DRIVER (input 实参 din 经 task 内部 b = a
//           驱动 output 实参 dout — 完整形参映射, 无 EmptyArgument 占位边)
module top(input [7:0] din, output logic [7:0] dout);
    task my_task(input [7:0] a, output logic [7:0] b);
        b = a;
    endtask

    initial begin
        my_task(din, dout);
    end
endmodule
