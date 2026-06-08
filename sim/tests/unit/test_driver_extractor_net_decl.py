"""
TDD: driver_extractor must extract driver edges for 'wire X = expr' syntax.

Bug: get_variable_declarations() in semantic_adapter.py only matches
'DataDeclaration' in the kind string, which filters out 'NetDeclaration'.
The verilog-axi axi_interconnect.v uses 'wire current_m_axi_wready =
m_axi_wready[m_select_reg];' (NetDeclarationSyntax) for inline assigns.

Result: 7+ signals like current_m_axi_wready, current_s_axi_rready
appear as 'UNUSED' in handshake scan because no driver edge is created.
"""
import sys, warnings
warnings.filterwarnings('ignore')
sys.path.insert(0, 'src')

from trace.unified_tracer import UnifiedTracer


def test_wire_with_init_has_driver():
    """A wire declared with 'wire X = expr' must have a DRIVER edge from expr to X."""
    code = '''
module test(
    input wire a,
    output wire y
);
    wire x = a;
    assign y = x;
endmodule
'''
    import tempfile, os
    with tempfile.NamedTemporaryFile(suffix='.sv', delete=False, mode='w') as f:
        f.write(code)
        path = f.name
    try:
        tracer = UnifiedTracer(files=[path])
        graph = tracer.build_graph()
        from trace.core.query.signal import SignalTracer
        st = SignalTracer(graph)
        # The wire 'x' should have a driver
        dis = st.trace_fanin_detailed('test.x')
        assert len(dis) > 0, f"Expected drivers for test.x, got 0"
        # The driver should reference 'a'
        assert any('a' in (d.expression or '') for d in dis), \
            f"Expected driver expr to contain 'a', got: {[d.expression for d in dis]}"
        print(f"test.x drivers: {len(dis)}")
        for d in dis[:3]:
            print(f"  cond={d.condition[:40]!r} expr={d.expression[:30]!r}")
    finally:
        os.unlink(path)


def test_net_decl_with_bit_select():
    """verilog-axi specific: wire X = array[index]; must work too."""
    code = '''
module test(
    input wire [3:0] arr,
    input wire [1:0] idx,
    output wire y_out
);
    wire sel = arr[idx];
    assign y_out = sel;
endmodule
'''
    import tempfile, os
    with tempfile.NamedTemporaryFile(suffix='.sv', delete=False, mode='w') as f:
        f.write(code)
        path = f.name
    try:
        tracer = UnifiedTracer(files=[path])
        graph = tracer.build_graph()
        from trace.core.query.signal import SignalTracer
        st = SignalTracer(graph)
        dis = st.trace_fanin_detailed('test.sel')
        assert len(dis) > 0, f"Expected drivers for test.sel, got 0"
        print(f"test.sel drivers: {len(dis)}")
        for d in dis[:3]:
            print(f"  cond={d.condition[:40]!r} expr={d.expression[:30]!r}")
    finally:
        os.unlink(path)


if __name__ == '__main__':
    test_wire_with_init_has_driver()
    test_net_decl_with_bit_select()
    print('All tests passed')
