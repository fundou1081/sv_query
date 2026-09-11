# _wrappers.py — instance 包装类 (原 semantic_adapter.py 模块级类, iter_176 移出)
#
# 供 modules 域 mixin 使用; semantic_adapter.py 保留同名再导出 (兼容)。
import logging

from ..._safe import safe_attr, safe_str, safe_str  # [iter_182]

logger = logging.getLogger(__name__)


class SemanticInstanceWrapper:
    """
    Semantic AST 实例包装器

    将 Semantic AST InstanceSymbol 适配为 GraphBuilder 期望的接口格式。
    这样可以在不修改 GraphBuilder 的情况下使用 Semantic AST。
    """

    def __init__(self, instance_symbol, parent_module=None):
        self._symbol = instance_symbol
        # [FIX] 对于数组实例元素 (如 u_duts[0]), name='' 但有 arrayName
        # 使用 arrayName + arrayPath 构建完整实例名
        try:
            inst_name = instance_symbol.name
        except (UnicodeDecodeError, TypeError):
            inst_name = None
        if not inst_name:
            try:
                array_name = instance_symbol.arrayName
            except (UnicodeDecodeError, TypeError):
                array_name = None
            if array_name:
                try:
                    arr_path = instance_symbol.arrayPath
                except (UnicodeDecodeError, TypeError):
                    arr_path = None
                if arr_path and hasattr(arr_path, "__iter__") and not isinstance(arr_path, str):
                    inst_name = f"{array_name}[{arr_path[0]}]"
                else:
                    inst_name = array_name
        self.name = inst_name
        self.type = type("TypeToken", (), {"value": self._get_module_type()})()
        self.parent_module = parent_module  # 父模块名

        # 构造 .instances[0].safe_str(safe_attr(decl, "name", "")) 结构供 GraphBuilder 使用
        self.instances = [SemanticInstanceDeclWrapper(instance_symbol)]

    def __str__(self):
        return str(self.name)

    def __repr__(self):
        return f"SemanticInstanceWrapper({self.name})"

    def _get_module_type(self) -> str:
        """获取模块类型名"""
        if hasattr(self._symbol, "definition"):
            defn = self._symbol.definition
            try:
                name_str = str(safe_str(safe_attr(defn, "name", "")))
            except (UnicodeDecodeError, TypeError):
                name_str = None
            if name_str:
                return name_str
        try:
            return str(self.name)
        except (UnicodeDecodeError, TypeError):
            return "<id:non-utf8>"

    def get_parent_module(self) -> str:
        """获取父模块名,供 GraphBuilder._get_parent_module_name 使用"""
        return self.parent_module or "top"

    def _get_parent_module_safe(self) -> str:
        """安全获取父模块名,用于 GraphBuilder 的 _get_parent_module_name 兼容

        这个方法模拟 GraphBuilder._get_parent_module_name 的行为,
        但在 parent 为 None 时返回 type.value(模块类型名)而非 'unknown'。
        """
        if self.parent_module:
            return self.parent_module
        # 对于顶级模块,parent 为 None,此时返回 type.value(即模块类型名)
        # 这样 inst_module_name 就能正确设为 'top'
        return self.type.value if self.type.value else str(self.name)

    @property
    def parent(self) -> object:
        """兼容属性:返回类似 SyntaxTree 的 parent 节点结构

        对于顶级模块(parent_module is None),返回 None
        这样 _get_parent_module_name 会使用 fallback 逻辑。
        """
        if self.parent_module:

            class ParentModule:
                def __init__(self, name: str) -> None:
                    self.name = name
                    self.header = type("Header", (), {"name": type("Name", (), {"rawText": name})()})()

            return ParentModule(self.parent_module)
        return None


class SemanticInstanceDeclWrapper:
    """包装 InstanceSymbol 的 declaration 部分"""

    def __init__(self, instance_symbol):
        self._symbol = instance_symbol

    @property
    def name(self) -> object:
        """返回实例名称作为 TokenValue"""

        class TokenValue:
            def __init__(self, val: str) -> None:
                self.value = val

        return TokenValue(self._symbol.name)
