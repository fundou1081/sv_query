// driver.sv — packet rand vars 真被 driver 消费
class packet;
    rand bit [7:0] addr;
    rand bit [7:0] data;
    rand bit [3:0] mode;
    randc bit [1:0] prio;

    constraint c_addr {
        addr inside {[0:63]};
    }
endclass

class driver;
    packet req;
    bit [7:0] out_addr;
    bit [7:0] out_data;
    bit [3:0] out_mode;
    bit [1:0] out_prio;
    bit unused;

    task run();
        // 模拟 driver 读 packet fields 然后 emit
        out_addr = req.addr;
        out_data = req.data;
        out_mode = req.mode;
        out_prio = req.prio;
        $display("addr=%0h data=%0h mode=%0h prio=%0h", out_addr, out_data, out_mode, out_prio);
    endtask
endclass

module top;
endmodule
