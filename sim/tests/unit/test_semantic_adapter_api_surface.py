# test_semantic_adapter_api_surface.py - adapter API 面冻结 (iter_174 Step 0)
# 方豆 "拆 semantic" (方案: docs/architecture/semantic_adapter_split_plan.md)
#
# 作用: 本文件是 adapter 重构的**安全网** — 冻结 `SemanticAdapter` 的公开面
# (方法名 + inspect.signature + property), 任何搬迁/拆分导致的名字/签名变化
# 都会在这里红灯。重构期间的策略是 **零改名/零改签名** (只搬函数体), 因此
# 本测试在整个 Step 2~9 期间必须始终绿。
#
# 若确实需要改 API (Step 10 死 API 清理): 同步更新本文件的冻结表, 并在
# commit message 说明 "API 变更: X → Y, 调用方 Z 处已更新"。
import inspect
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

from trace.core.semantic_adapter import SemanticAdapter  # noqa: E402

# ── 冻结表 (2026-09-08 分域拆分后实测) ───────────────────────────────────
# 演进:
#   iter_174 建表 (65 方法, 拆分前基线)
#   iter_176 采集口径改 MRO-wide (方法定义在 mixin 类中; 有效 API 面等价)
#   iter_177 Step 10 移出 5 个零调用方法 → legacy/dead_semantic_adapter_methods.py
#     (get_generate_instances / iter_modules / visit_module / get_class_name /
#      get_definition) — **API 收缩**: 全仓 (src+tests) 零调用, AST+grep 双证
FROZEN_METHODS = {
    '__init__': '(self, root, compiler=None, target_module=None)',
    '_collect_drivers_from_stmt': '(self, stmt, func_name, drivers)',
    '_conn_expr_to_signal': '(self, expr, instance) -> str | None',
    '_eval_select_index': '(self, sel, gidx: int | None) -> int | None',
    '_extract_assignment_drivers': '(self, expr, func_name, drivers)',
    '_extract_signals_from_expr': '(self, expr, genvar_ctx: dict | None = None) -> list[str]',
    '_find_target_top': '(self, target_module: str)',
    '_fix_unicode_class_names': '(self, classes: list)',
    '_genvar_index_from_hp': '(self, instance) -> int | None',
    '_iter_children': '(self, node) -> list',
    '_iter_generate_children': '(self, module, kind_marker: str)',
    '_safe_str': '(obj) -> str',
    '_scan_class_specializations': '(self) -> dict[str, list]',
    'analyze_task_internal_drivers': '(self, task_or_func) -> dict',
    'clean_name': '(self, name) -> str',
    'extract_data_width': '(self, data_decl) -> tuple',
    'extract_port_width': '(self, port_decl, scope=None) -> tuple',
    'get_always_blocks': '(self, module) -> list',
    'get_assignments': '(self, module) -> list',
    'get_class_members': '(self, cls) -> list',
    'get_classes': '(self) -> list',
    'get_data_declarations': '(self, module) -> list',
    'get_drivers': '(self, signal_name: str) -> list',
    'get_function_declarations': '(self, module) -> list',
    'get_function_name': '(self, func) -> str',
    'get_function_params': '(self, func) -> list',
    'get_function_width': '(self, func) -> tuple[int, int] | None',
    'get_generate_always_blocks': '(self, module) -> list[dict]',
    'get_generate_net_declarations': '(self, module) -> list[dict]',
    'get_genvar_context': '(self, assign) -> dict',
    'get_instance_connection': '(self, instance) -> list',
    'get_interface_members': '(self, interface_port_symbol) -> list[str]',
    'get_interface_modport_signals': '(self, interface_name: str, modport_name: str) -> dict[str, str]',
    'get_interfaces': '(self) -> list',
    'get_loads': '(self, signal_name: str) -> list',
    'get_modport_declarations': '(self, interface) -> list',
    'get_modport_info': '(self, modport) -> dict',
    'get_module_instances': '(self) -> list',
    'get_module_instances_recursive': '(self) -> list',
    'get_module_name': '(self, module) -> str',
    'get_module_parameters': '(self, module) -> list',
    'get_modules': '(self) -> list',
    'get_net_aliases': '(self, module) -> list',
    'get_net_declarations': '(self, module) -> list',
    'get_port_declarations': '(self, module) -> list',
    'get_port_name': '(self, port_decl) -> str',
    'get_port_name_and_direction': '(self, port_decl) -> tuple',
    'get_port_names': '(self, module) -> list[str]',
    'get_primitive_genvar_context': '(self, primitive) -> dict',
    'get_primitive_instances': '(self, module) -> list',
    'get_signal_name': '(self, signal) -> str',
    'get_source_location': '(self, node) -> tuple',
    'get_source_text': '(self, node) -> str',
    'get_task_declarations': '(self, module) -> list',
    'get_task_name': '(self, task) -> str',
    'get_task_params': '(self, task) -> list',
    'get_top_level_subroutines': '(self) -> list',
    'get_variable_declarations': '(self, module) -> list',
    'items': '(self) -> object',
    'visit': '(self, callback: Callable) -> None',
}

FROZEN_PROPERTIES = ['parser', 'root', 'trees']


class TestSemanticAdapterApiSurface(unittest.TestCase):
    """adapter 公开面冻结 — 重构期间只允许"函数体搬家", 不允许改名/改签名"""

    def _live_methods(self):
        """沿 MRO 采集 (iter_176 分域 mixin 后方法定义在 mixin 类中).

        有效 API 面 = 实例可调用的全部方法 — 与拆分前等价; 口径改为 MRO-wide。
        """
        out = {}
        for klass in SemanticAdapter.__mro__:
            if klass is object:
                continue
            for name, obj in vars(klass).items():
                if callable(obj) and not isinstance(obj, property):
                    try:
                        sig = str(inspect.signature(obj))
                    except (TypeError, ValueError):
                        sig = "<no-sig>"
                    out.setdefault(name, sig)
        return out

    def test_method_set_unchanged(self):
        live = set(self._live_methods())
        frozen = set(FROZEN_METHODS)
        self.assertEqual(live - frozen, set(), "新增方法 → 如需保留请更新冻结表")
        self.assertEqual(frozen - live, set(), "方法丢失 → 重构破坏了 API 面")

    def test_signatures_unchanged(self):
        live = self._live_methods()
        diffs = {n: (FROZEN_METHODS[n], live[n])
                 for n in FROZEN_METHODS if n in live and live[n] != FROZEN_METHODS[n]}
        self.assertEqual(diffs, {}, "签名变化 → 调用方 (42 方法/150 处) 可能静默出错")

    def test_properties_unchanged(self):
        live = set()
        for klass in SemanticAdapter.__mro__:
            if klass is object:
                continue
            live |= {n for n, o in vars(klass).items() if isinstance(o, property)}
        self.assertEqual(sorted(live), FROZEN_PROPERTIES)

    def test_facade_contract_smoke(self):
        """构造 + 关键属性 + 一个真实查询 (搬迁后行为不变的最小证据)"""
        from trace.core.compiler import SVCompiler
        src = "module m(input logic a, output logic b); assign b = a; endmodule"
        comp = SVCompiler(sources={"t.sv": src})
        ad = SemanticAdapter(comp.get_root())
        self.assertIs(ad.root, comp.get_root())
        self.assertIsNotNone(ad.trees)
        self.assertTrue(any("m" in str(getattr(x, "name", "")) for x in ad.get_modules()))


if __name__ == '__main__':
    unittest.main()
