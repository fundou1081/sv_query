"""
test_mig_validator.py — Test MIG validator (Phase 2.1).

[Phase 2 2026-06-25] Original: 比 instance count, 易误报.
[Phase 2.1 2026-06-25] Redesign:
  - compare_with_extract_module: MIG vs extract (informational only)
  - verify_specific_port: native API 验证 specific port

测试策略:
- simple SV: compare_with_extract_module 应该 work
- verify_specific_port 跑 actual SV 找 specific port
"""

import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'tools'))

from trace.core.compiler import SVCompiler
from trace.core.semantic_adapter import SemanticAdapter
from trace.core.mig_validator import (
    compare_with_extract_module,
    verify_specific_port,
    ExtractComparison,
    PortVerification,
)


SIMPLE_SV = '''
module top();
    wire clk;
    sub_a u_a(.clk(clk));
    sub_b u_b(.clk(clk));
endmodule

module sub_a(input clk);
    sub_inner u_inner(.clk(clk));
endmodule

module sub_b(input clk);
endmodule

module sub_inner(input clk);
endmodule
'''


def _build_adapter_and_mig(simple_sv):
    """[Helper] Build a simple MIG from SV source for testing."""
    comp = SVCompiler({'test.sv': simple_sv})
    adapter = SemanticAdapter(comp.get_root())

    from trace.core.module_instance_graph import ModuleInstanceGraph
    mig = ModuleInstanceGraph(adapter=adapter)
    instances = adapter.get_module_instances()
    for inst in instances:
        symbol = getattr(inst, '_symbol', None) or getattr(inst, 'symbol', None)
        if symbol is None:
            continue
        try:
            inst_id = str(symbol.hierarchicalPath)
        except Exception:
            continue
        defn = getattr(symbol, 'definition', None)
        inst_type = defn.name if defn else 'unknown'
        port_name = 'clk'
        port_path = f"{inst_id}.{port_name}"
        parent = getattr(inst, 'parent_module', None)
        if parent:
            internal = f"{parent}.{port_name}"
        else:
            internal = f"<root>.{port_name}"
        mig.port_to_internal[port_path] = internal
        mig.internal_to_port[internal] = port_path
    return comp, adapter, mig


class TestCompareWithExtract(unittest.TestCase):
    """compare_with_extract_module: MIG vs extract (informational)."""

    def test_simple_compare_runs(self):
        comp, adapter, mig = _build_adapter_and_mig(SIMPLE_SV)
        info = compare_with_extract_module(mig, adapter, target_module='top')
        self.assertIsInstance(info, ExtractComparison)
        self.assertEqual(info.target_module, 'top')
        # Simple: 3 instances in MIG (u_a, u_inner, u_b)
        # Extract should also find 3
        print(f"\n{info.summary()}")

    def test_simple_no_utility_cells(self):
        """Simple SV has no utility cells - diff should be 0."""
        comp, adapter, mig = _build_adapter_and_mig(SIMPLE_SV)
        info = compare_with_extract_module(mig, adapter, target_module='top')
        # Simple SV: MIG should find same as extract
        self.assertEqual(info.utility_instance_count, 0)


class TestVerifySpecificPort(unittest.TestCase):
    """verify_specific_port: native API cross-check."""

    def test_simple_verify_existing_port(self):
        """Verify a port that exists — should find it."""
        comp = SVCompiler({'test.sv': SIMPLE_SV})
        root = comp.get_root()
        result = verify_specific_port(
            root, target_module='top',
            inst_path='top.u_a', port_name='clk',
        )
        self.assertIsInstance(result, PortVerification)
        self.assertTrue(result.found_in_native)
        # In simple SV, top.u_a.clk connects to top.clk
        self.assertEqual(result.native_value, 'clk')

    def test_simple_verify_nonexistent_port(self):
        """Verify a port that doesn't exist — should not find it."""
        comp = SVCompiler({'test.sv': SIMPLE_SV})
        root = comp.get_root()
        result = verify_specific_port(
            root, target_module='top',
            inst_path='top.u_a', port_name='nonexistent_port',
        )
        self.assertFalse(result.found_in_native)


if __name__ == '__main__':
    unittest.main(verbosity=2)
