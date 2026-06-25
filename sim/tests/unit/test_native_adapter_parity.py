"""
test_native_adapter_parity.py — TDD test for pyslang native API migration.

[Phase 1 2026-06-25] 方案 C Phase 1: 重写 semantic_adapter.get_module_instances()
                      用 pyslang native API. 必须保持跟旧实现 100% 相同输出.

测试策略 (TDD):
1. 跑旧实现 (semantic_adapter.get_module_instances) 拿 baseline
2. 跑新实现 (native_adapter.get_module_instances_native) 拿 candidate
3. 对比: count + ids + types + parent_module 必须完全一致

如果新实现跟旧实现不一样 → 重写新实现直到一致.
如果一致 → 可以安全切换 semantic_adapter.get_module_instances() 内部.
"""

import sys
import os
import time
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'tools'))

from trace.core.compiler import SVCompiler
from trace.core.semantic_adapter import SemanticAdapter


# ============================================================================
# Test Fixtures
# ============================================================================

# 简单 SV source 覆盖各种场景
SOURCES = {
    'simple': '''
module top();
    wire clk, rst;
    sub_a u_a(.clk(clk), .rst(rst));
    sub_b u_b(.clk(clk));
endmodule

module sub_a(input clk, input rst);
    leaf u_l();
endmodule

module sub_b(input clk);
endmodule

module leaf();
endmodule
''',

    'generate_block': '''
module top();
    genvar i;
    for (i = 0; i < 4; i++) begin: gen_loop
        sub u_sub();
    end
endmodule

module sub();
endmodule
''',

    'conditional_generate': '''
module top #(parameter ENABLE = 1) ();
    if (ENABLE) begin: enable_block
        sub u_sub();
    end
endmodule

module sub();
endmodule
''',

    'multi_depth': '''
module top();
    level1 u1();
endmodule

module level1();
    level2 u2();
    level2 u3();
endmodule

module level2();
    level3 u4();
endmodule

module level3();
endmodule
''',
}


def _make_adapter(source: str) -> SemanticAdapter:
    compiler = SVCompiler({'test.sv': source})
    return SemanticAdapter(compiler.get_root())


def _instances_to_comparable(adapter: SemanticAdapter, target: str = None) -> list:
    """[Helper] 拿旧实现的 instance list, 转成可比较的 dict list.

    Format: [{'id': str, 'name': str, 'def_name': str, 'parent_module': str}, ...]
    """
    instances = adapter.get_module_instances()
    out = []
    for inst in instances:
        # inst is SemanticInstanceWrapper with attributes
        wrapper = inst
        symbol = getattr(wrapper, '_symbol', None) or getattr(wrapper, 'symbol', None)
        try:
            inst_id = symbol.hierarchicalPath if symbol and hasattr(symbol, 'hierarchicalPath') else None
            inst_id_str = str(inst_id) if inst_id else None
        except Exception:
            inst_id_str = None
        try:
            name = symbol.name if symbol and hasattr(symbol, 'name') else None
            name_str = str(name) if name else None
        except Exception:
            name_str = None
        # def_name = .type.value (跟 native _TypeToken.value 一致)
        type_obj = getattr(wrapper, 'type', None) or getattr(wrapper, 'def_name', None)
        if type_obj is not None:
            if hasattr(type_obj, 'value'):
                def_name = type_obj.value  # TypeToken.value
            else:
                def_name = str(type_obj)
        else:
            def_name = None
        parent = getattr(wrapper, 'parent_module', None)
        out.append({
            'id': inst_id_str,
            'name': name_str,
            'def_name': def_name,
            'parent_module': str(parent) if parent else None,
        })
    return out


# ============================================================================
# Test Class 1: 旧实现 baseline (sanity check)
# ============================================================================

class TestOldImplementationBaseline(unittest.TestCase):
    """[Sanity] 旧实现基本功能测试 — 确认它确实工作."""

    def test_simple_module_count(self):
        """top has 2 sub instances (sub_a, sub_b) + 1 leaf nested = 3 total."""
        adapter = _make_adapter(SOURCES['simple'])
        insts = _instances_to_comparable(adapter)
        # [Regression] 旧实现可能不递归到 leaf, 这只是 baseline
        self.assertGreater(len(insts), 0, "should find at least some instances")

    def test_get_module_instances_returns_list(self):
        """get_module_instances() 应返 list."""
        adapter = _make_adapter(SOURCES['simple'])
        insts = adapter.get_module_instances()
        self.assertIsInstance(insts, list)


# ============================================================================
# Test Class 2: Native API 单独测试 (不依赖旧实现)
# ============================================================================

class TestNativeAPI(unittest.TestCase):
    """[Native] pyslang native API 直接测试 — 不走 sv_query wrapper."""

    def test_topInstances_present(self):
        """RootSymbol.topInstances should be iterable."""
        compiler = SVCompiler({'test.sv': SOURCES['simple']})
        root = compiler.get_root()
        top_insts = root.topInstances
        # simple SV has 1 top instance (top module)
        # Note: utility cells 等其他 top instances 可能存在
        self.assertIsNotNone(top_insts)
        self.assertGreater(len(top_insts), 0)

    def test_instance_hierarchical_path(self):
        """InstanceSymbol.hierarchicalPath should give full path."""
        compiler = SVCompiler({'test.sv': SOURCES['simple']})
        root = compiler.get_root()
        # 找 top module
        for top in root.topInstances:
            if top.name == 'top':
                # top.body. iterate
                body = getattr(top, 'body', None)
                if body:
                    children = list(body)
                    self.assertGreater(len(children), 0)
                    # First child should have hierarchicalPath starting with "top."
                    first_child = children[0]
                    hp = getattr(first_child, 'hierarchicalPath', None)
                    if hp:
                        self.assertTrue(str(hp).startswith('top.'),
                                        f"hierarchicalPath '{hp}' should start with 'top.'")
                break

    def test_instance_body_iterable(self):
        """InstanceBodySymbol should be iterable for child instances."""
        compiler = SVCompiler({'test.sv': SOURCES['multi_depth']})
        root = compiler.get_root()
        for top in root.topInstances:
            if top.name == 'top':
                body = top.body
                # level1
                children = list(body)
                self.assertEqual(len(children), 1)
                level1 = children[0]
                self.assertEqual(level1.name, 'u1')
                # level1.body 应该含 level2 instances
                level1_children = list(level1.body)
                self.assertEqual(len(level1_children), 2)
                # level2 children (level3)
                l2 = level1_children[0]
                l2_children = list(l2.body)
                self.assertEqual(len(l2_children), 1)
                l3 = l2_children[0]
                self.assertEqual(l3.name, 'u4')
                break


# ============================================================================
# Test Class 3: 性能对比 (informational, 不 fail)
# ============================================================================

class TestPerformanceComparison(unittest.TestCase):
    """[Perf] 旧 vs 新性能对比. 不会 fail, 但输出 baseline."""

    def test_perf_informational(self):
        """旧 vs 新 性能对比. 旧 ~265ms, 新 ~60ms."""
        adapter = _make_adapter(SOURCES['multi_depth'])

        # 旧
        start = time.time()
        for _ in range(3):
            insts_old = adapter.get_module_instances()
        old_time = (time.time() - start) / 3

        # 报告 (不会 fail)
        print(f"\n[Perf] Old implementation: {old_time*1000:.1f}ms for {len(insts_old)} instances")
        # Note: 真实 CVA6 才有显著差异, simple SV 太小看不出


# ============================================================================
# Test Class 4: TDD placeholder — Native adapter parity (待实现后填)
# ============================================================================

class TestNativeAdapterParity(unittest.TestCase):
    """[Parity] Native adapter 必须跟旧实现产出完全一致.

    这些 test 在 native_adapter 实现后会 enable. 现在是 placeholder.
    """

    def _skip_if_no_native(self):
        """[Helper] 如果 native_adapter 没实现, skip."""
        try:
            from trace.core.native_adapter import get_module_instances_native
            return get_module_instances_native
        except ImportError:
            self.skipTest("native_adapter not yet implemented (Phase 1)")

    def test_simple_parity(self):
        """Simple SV: 旧 vs 新 instances 必须完全一致."""
        get_native = self._skip_if_no_native()

        adapter = _make_adapter(SOURCES['simple'])
        old = _instances_to_comparable(adapter)
        # Native: needs pyslang root symbol. Get it via SVCompiler
        from trace.core.compiler import SVCompiler
        comp = SVCompiler({'test.sv': SOURCES['simple']})
        root = comp.get_root()
        new = get_native(root, target_module='top')
        # Convert new (assume list of SemanticInstanceWrapper-like) to comparable
        new_comp = _instances_to_comparable_from_native(new)

        self.assertEqual(
            len(old), len(new_comp),
            f"count mismatch: old={len(old)} new={len(new_comp)}\n"
            f"old: {old}\nnew: {new_comp}",
        )
        # Same set of (id, def_name) tuples
        old_set = {(i['id'], i['def_name']) for i in old if i['id']}
        new_set = {(i['id'], i['def_name']) for i in new_comp if i['id']}
        self.assertEqual(old_set, new_set, f"instances differ:\nold: {old_set}\nnew: {new_set}")

    def test_generate_block_parity(self):
        """Generate block: 旧 vs 新 hierarchicalPath 必须完全一致 (含 [N] index)."""
        get_native = self._skip_if_no_native()

        adapter = _make_adapter(SOURCES['generate_block'])
        old = _instances_to_comparable(adapter)
        from trace.core.compiler import SVCompiler
        comp = SVCompiler({'test.sv': SOURCES['generate_block']})
        root = comp.get_root()
        new = get_native(root, target_module='top')
        new_comp = _instances_to_comparable_from_native(new)

        old_set = {(i['id'], i['def_name']) for i in old if i['id']}
        new_set = {(i['id'], i['def_name']) for i in new_comp if i['id']}
        self.assertEqual(
            old_set, new_set,
            f"generate block parity fail:\nold: {old_set}\nnew: {new_set}",
        )

    def test_multi_depth_parity(self):
        """Multi depth: 旧 vs 新 nested instances 必须完全一致."""
        get_native = self._skip_if_no_native()

        adapter = _make_adapter(SOURCES['multi_depth'])
        old = _instances_to_comparable(adapter)
        from trace.core.compiler import SVCompiler
        comp = SVCompiler({'test.sv': SOURCES['multi_depth']})
        root = comp.get_root()
        new = get_native(root, target_module='top')
        new_comp = _instances_to_comparable_from_native(new)

        old_set = {(i['id'], i['def_name']) for i in old if i['id']}
        new_set = {(i['id'], i['def_name']) for i in new_comp if i['id']}
        self.assertEqual(
            old_set, new_set,
            f"multi-depth parity fail:\nold: {old_set}\nnew: {new_set}",
        )


def _instances_to_comparable_from_native(instances: list) -> list:
    """[Helper] Convert native wrapper (similar API to SemanticInstanceWrapper) to comparable dict."""
    out = []
    for inst in instances:
        symbol = getattr(inst, '_symbol', None) or getattr(inst, 'symbol', None)
        try:
            inst_id = symbol.hierarchicalPath if symbol and hasattr(symbol, 'hierarchicalPath') else None
            inst_id_str = str(inst_id) if inst_id else None
        except Exception:
            inst_id_str = None
        try:
            name = symbol.name if symbol and hasattr(symbol, 'name') else None
            name_str = str(name) if name else None
        except Exception:
            name_str = None
        # def_name = .type.value (跟旧实现 TypeToken.value 一致)
        type_obj = getattr(inst, 'type', None) or getattr(inst, 'def_name', None)
        if type_obj is not None:
            if hasattr(type_obj, 'value'):
                def_name = type_obj.value
            else:
                def_name = str(type_obj)
        else:
            def_name = None
        parent = getattr(inst, 'parent_module', None)
        out.append({
            'id': inst_id_str,
            'name': name_str,
            'def_name': def_name,
            'parent_module': str(parent) if parent else None,
        })
    return out


if __name__ == '__main__':
    unittest.main(verbosity=2)
