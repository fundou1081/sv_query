class base;
  int x;
  function void foo();
    x = 1;
  endfunction
endclass

class child extends base;
  int y;
  function void bar();
    foo();
  endfunction
endclass

module top;
endmodule
