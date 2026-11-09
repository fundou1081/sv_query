class rnd_item;
  rand int a, b, c, d, e;
  constraint c_ab { a < b; solve a before b; }
  constraint c_bc { b == c + 1; }
  constraint c_cd { if (c > 0) d inside {[1:10]}; }
  constraint c_de { e dist {0 := 1, 1 := 3}; }
endclass
