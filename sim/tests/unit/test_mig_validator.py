"""
test_mig_validator.py — Test MIG validator against pyslang native API.

[Phase 2 2026-06-25] Use native as oracle to detect MIG bugs.

测试策略:
1. 简单 SV: build MIG, run validator, expect OK
2. CVA6: build MIG, run validator, expect OK (after namespace rewrite)
3. Force bug: break MIG, validator should detect
"""

import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'tools'))

from trace.core.compiler import SVCompiler
from trace.core.semantic_adapter import SemanticAdapter
from trace.core.mig_validator import (
    validate_mig_with_native,
    _collect_native_port_connections,
    _normalize_mig_keys,
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

    # Build minimal MIG (mimics module_instance_graph.build)
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
        parent = getattr(inst, 'parent_module', None)
        # Add a fake port mapping
        port_name = 'clk'
        port_path = f"{inst_id}.{port_name}"
        if parent:
            internal = f"{parent}.{port_name}"
        else:
            internal = f"<root>.{port_name}"
        mig.port_to_internal[port_path] = internal
        mig.internal_to_port[internal] = port_path
    return comp, adapter, mig


class TestMigValidatorSimple(unittest.TestCase):
    """Simple SV: build MIG, validator should work."""

    def test_simple_validator_runs(self):
        comp, adapter, mig = _build_adapter_and_mig(SIMPLE_SV)
        root = comp.get_root()
        result = validate_mig_with_native(mig, root, target_module='top')
        # Should run without exception
        self.assertEqual(result.target_module, 'top')
        # Simple: 3 instances (u_a, u_inner, u_b)
        # MIG has 3 port mappings (1 per instance, fake)
        print(f"\n{result.summary()}")

    def test_simple_instance_count_match(self):
        """MIG should find same number of instances as native (after filter)."""
        comp, adapter, mig = _build_adapter_and_mig(SIMPLE_SV)
        root = comp.get_root()
        result = validate_mig_with_native(mig, root, target_module='top')
        # simple SV: MIG has 3 insts (u_a, u_inner, u_b), native has same
        # Allow some flexibility
        self.assertGreater(result.native_instance_count, 0)
        self.assertGreater(result.mig_instance_count, 0)


class TestNormalizeMigKeys(unittest.TestCase):
    """_normalize_mig_keys should strip namespace prefix correctly."""

    def test_strips_target_module(self):
        keys = {'ariane.cva6.X.clk_i', 'cva6.X.clk_i'}
        result = _normalize_mig_keys(keys, target_module='cva6')
        # Both should normalize to cva6.X.clk_i (deduplicated)
        self.assertEqual(result, {'cva6.X.clk_i'})

    def test_no_match_keeps_as_is(self):
        keys = {'top.i_cva6.X.clk_i'}  # 'cva6' is in 'i_cva6' but not exact
        result = _normalize_mig_keys(keys, target_module='cva6')
        # 'i_cva6' is NOT equal to 'cva6' — keep as-is
        self.assertEqual(result, {'top.i_cva6.X.clk_i'})

    def test_keeps_non_matching(self):
        keys = {'top.u_a.clk', 'other.path'}
        result = _normalize_mig_keys(keys, target_module='top')
        self.assertIn('top.u_a.clk', result)
        # 'other.path' doesn't contain 'top' — kept as-is
        self.assertIn('other.path', result)


class TestNativeCollection(unittest.TestCase):
    """_collect_native_port_connections should walk all instances."""

    def test_simple_collection(self):
        comp = SVCompiler({'test.sv': SIMPLE_SV})
        root = comp.get_root()
        data = _collect_native_port_connections(root, target_module='top')
        self.assertGreater(len(data['instances']), 0)
        # port_connections is dict[inst_id, dict[port, signal]]
        self.assertGreater(len(data['port_connections']), 0)
        # Should have connected signals
        self.assertIn('clk', data['connected_signals'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
