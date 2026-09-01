// golden_dataflow_35_class_oop.sv — class OOP 1:1 truth
// 1:1 预期 (iter_095 实测):
//   - 节点: packet (CLASS) / packet.addr, packet.data (CLASS_PROPERTY)
//           / top.pkt (CLASS_INSTANCE) / top.din
//   - 边: packet→packet.addr CONSTRAINS / packet→packet.data CONSTRAINS
//         top.pkt→packet IS_INSTANCE_OF (new())
//         packet.addr→packet.data DRIVER (方法体 data = addr, iter_075 修复)
class packet;
    rand bit [7:0] addr;
    rand bit [7:0] data;
    task set_addr(input bit [7:0] a);
        addr = a;
        data = addr;
    endtask
endclass

module top;
    packet pkt = new();
    logic [7:0] din;
    initial begin
        pkt.set_addr(din);
    end
endmodule
