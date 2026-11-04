`define uvm_object_utils(T)
`define uvm_component_utils(T)
`define uvm_do(T)
`define uvm_declare_p_sequencer(S)

class uvm_object;
  function new(string name = ""); endfunction
endclass
class uvm_component extends uvm_object;
  function new(string name = "", uvm_component parent = null); super.new(name); endfunction
endclass
class uvm_sequence_item extends uvm_object;
  function new(string name = ""); super.new(name); endfunction
endclass
class uvm_sequence #(type REQ = uvm_sequence_item) extends uvm_object;
  function new(string name = ""); super.new(name); endfunction
endclass
class uvm_driver #(type REQ = uvm_sequence_item) extends uvm_component;
  function new(string name = "", uvm_component parent = null); super.new(name, parent); endfunction
endclass

class my_item_type_id;
  static function int create(string name); return 1; endfunction
endclass
class my_item extends uvm_sequence_item;
  `uvm_object_utils(my_item)
  typedef my_item_type_id type_id;
  rand int addr;
  function new(string name = "my_item"); super.new(name); endfunction
endclass

class my_seq extends uvm_sequence #(my_item);
  `uvm_object_utils(my_seq)
  `uvm_declare_p_sequencer(my_sequencer)
  function new(string name = "my_seq"); super.new(name); endfunction
  task body();
    my_item req;
    `uvm_do(req)
  endtask
endclass

class my_driver extends uvm_driver #(my_item);
  `uvm_component_utils(my_driver)
  function new(string name = "my_driver", uvm_component parent = null);
    super.new(name, parent);
  endfunction
endclass

class my_builder;
  function void build();
    my_item::type_id::create("req");
  endfunction
endclass

module top; endmodule
