// inheritance.sv — base class 有 rand vars, derived class 继承
class base_packet;
    rand bit [7:0] base_addr;
    rand bit [3:0] base_mode;
endclass

class extended_packet extends base_packet;
    rand bit [15:0] ext_data;
endclass

class inheritance_driver;
    extended_packet req;
    bit [7:0] out_base_addr;
    bit [3:0] out_base_mode;
    bit [15:0] out_ext_data;

    task run();
        // driver 应该读 base + extended 的所有 fields
        out_base_addr = req.base_addr;
        out_base_mode = req.base_mode;
        out_ext_data = req.ext_data;
    endtask
endclass

module top; endmodule
