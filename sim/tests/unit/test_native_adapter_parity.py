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

import os
import sys
import time
import unittest

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

    # [GAP-2 2026-08-29] 数组实例化: 递归有 InstanceArray 分支, native 缺
    'instance_array': '''
module top();
    sub u_arr[3]();
endmodule

module sub(input clk = 1'b0);
endmodule
''',

    # [GAP-3 2026-08-29] 嵌套 generate: 递归漏实例, native 找全
    'nested_generate': '''
module top();
    genvar i, j;
    for (i = 0; i < 2; i++) begin: gen_i
        for (j = 0; j < 2; j++) begin: gen_j
            sub u_sub();
        end
    end
endmodule

module sub();
endmodule
''',
}


def _make_adapter(source: str) -> SemanticAdapter:
    compiler = SVCompiler({'test.sv': source})
    return SemanticAdapter(compiler.get_root())


def _instances_to_comparable(
    adapter: SemanticAdapter,
    target: str = None,
    method: str = "get_module_instances_recursive",
) -> list:
    """[Helper] 拿实例 list (默认旧递归实现作参照), 转成可比较的 dict list.

    [G3 阶段 2 2026-08-29] 生产 get_module_instances() 已切 native, parity 对比
    的 "旧" 侧固定用 get_module_instances_recursive() (递归 walk).

    Format: [{'id': str, 'name': str, 'def_name': str, 'parent_module': str}, ...]
    """
    instances = getattr(adapter, method)()
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

    # ========================================================================
    # [iter_053/054 2026-08-29] 已知差异显式爆出来 (AGENTS.md 纪律 2.5 精神).
    # tools/verify_native_parity.py 在 MIG 四表层面发现了 3 个差异,
    # 现有 (id, def_name) 集合对比测不出来。iter_054 修掉 GAP-1/GAP-2 后,
    # 这两个测试从 expectedFailure 转正为普通断言。
    # ========================================================================

    def test_generate_block_parent_parity(self):
        """[GAP-1 已修] generate block 实例的 parent_module 必须一致.

        递归: parent = 'top.gen_loop[0]' (hierarchicalPath 去掉最后一段)
        native (修后): 同一规则 → 一致.
        MIG.build 用 parent_module 填 ModuleInstanceNode.parent.
        """
        get_native = self._skip_if_no_native()
        adapter = _make_adapter(SOURCES['generate_block'])
        old_set = {
            (i['id'], i['parent_module']) for i in _instances_to_comparable(adapter)
        }
        comp = SVCompiler({'test.sv': SOURCES['generate_block']})
        root = comp.get_root()
        new = get_native(root, target_module='top')
        new_set = {
            (i['id'], i['parent_module'])
            for i in _instances_to_comparable_from_native(new)
        }
        self.assertEqual(old_set, new_set, f"GAP-1 parent mismatch:\nold: {old_set}\nnew: {new_set}")

    def test_instance_array_parity(self):
        """[GAP-2 已修] 数组实例化 (InstanceArray) 必须一致.

        递归: 3 个实例 top.u_arr[0..2], 类型 'sub', parent = 元素自身 hp
        native (修后): 显式 InstanceArray 分支 → 一致 (端口表也由 MIG 自动对齐).
        """
        get_native = self._skip_if_no_native()
        adapter = _make_adapter(SOURCES['instance_array'])
        old_set = {
            (i['id'], i['def_name'], i['parent_module'])
            for i in _instances_to_comparable(adapter)
        }
        comp = SVCompiler({'test.sv': SOURCES['instance_array']})
        root = comp.get_root()
        new = get_native(root, target_module='top')
        new_set = {
            (i['id'], i['def_name'], i['parent_module'])
            for i in _instances_to_comparable_from_native(new)
        }
        self.assertEqual(old_set, new_set, f"GAP-2 array mismatch:\nold: {old_set}\nnew: {new_set}")

    def test_conditional_generate_parent_native_scoped(self):
        """[已知差异·已接受] conditional generate (if-generate) 的 parent.

        递归: parent = 'top' (GenerateBlock 透明, 丢失 generate 路径)
        native (修后): parent = 'top.enable_block' (完整作用域路径, 语义更正确)

        与 GAP-3 同一类: native 比递归更正确, 输出会变 — 方豆拍板
        "按 1 做" (接受 native 修复, G3 计划按此写). 此测试固化 native 行为.
        """
        get_native = self._skip_if_no_native()
        comp = SVCompiler({'test.sv': SOURCES['conditional_generate']})
        root = comp.get_root()
        new = get_native(root, target_module='top')
        items = {
            (i['id'], i['parent_module'])
            for i in _instances_to_comparable_from_native(new)
        }
        self.assertEqual(items, {('top.enable_block.u_sub', 'top.enable_block')})

    def test_nested_generate_native_finds_all(self):
        """[GAP-3 已接受为 bugfix] 嵌套 generate (genvar 套 genvar) native 找全 4 个实例.

        递归路径漏掉全部 (GenerateBlockArray 的 entry 内只处理直接 Instance,
        不递归 entry 内层嵌套的 GenerateBlockArray/GenerateBlock)。
        native 找全 → 切 native 会让 MIG 输出增加实例, 方豆拍板按 bugfix 接受
        (iter_054)。此测试锁定 native 能力, 防止回退。
        """
        get_native = self._skip_if_no_native()
        comp = SVCompiler({'test.sv': SOURCES['nested_generate']})
        root = comp.get_root()
        new = get_native(root, target_module='top')
        ids = {i['id'] for i in _instances_to_comparable_from_native(new)}
        self.assertEqual(len(ids), 4, f"native 应找全嵌套 generate 实例: {ids}")
        self.assertTrue(
            all('gen_i[' in x and 'gen_j[' in x for x in ids),
            f"hierarchicalPath 应含两层 generate 段: {ids}",
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
