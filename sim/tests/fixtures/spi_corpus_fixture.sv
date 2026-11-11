// P158.4 — fixture for the SPI corpus runner self-tests.
//
// Mirrors the *shape* of the OpenTitan SPI_HOST block that the real corpus
// exercises, at a size that builds in well under a second:
//
//   top.x ──► sub.u0.a ──► sub.u0.b ──► top.w ──► top.q ──► top.z
//                                             (top.z = y ? q : w)
//
// Independent oracle (not "whatever the CLI returns"):
//   * `top.u0.b` has exactly 1 driver (the `sub` instance port `b`) and
//     exactly 3 loads (`top.w`, `top.q`, `top.z`).
//   * the canonical directed path top.x -> top.z is
//     x -> u0.a -> u0.b -> w -> q -> z.ternary_y -> z
//     (7 nodes = 6 hops; the last hop is the ternary select).
//   * `top.z` is driven by `top.q` (assign z = y ? q : w).

module sub(input logic a, output logic b);
  assign b = a;
endmodule

module top(input logic x, input logic y, output logic z);
  logic w;
  sub u0(.a(x), .b(w));

  logic q;
  assign q = w;
  assign z = y ? q : w;
endmodule
