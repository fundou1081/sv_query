// dead.sv — 有 rand vars 但没人消费
class packet;
    rand bit [7:0] used_addr;
    rand bit [7:0] unused_data;
    rand bit [3:0] never_read_mode;
endclass

class consumer;
    packet req;
    bit [7:0] out_addr;

    task run();
        // 只用 req.used_addr
        out_addr = req.used_addr;
    endtask
endclass

module top;
endmodule
