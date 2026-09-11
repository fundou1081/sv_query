# ruff: noqa: E402
# ==============================================================================
# semantic_adapter.py - Semantic AST 适配器
#
# 将 Semantic AST (RootSymbol) 适配为 GraphBuilder 期望的接口
# 遵循铁律1: 必须使用 Semantic AST (Compilation + getRoot())
# ==============================================================================

import logging
import os
import sys
from typing import Callable, Iterator

logger = logging.getLogger(__name__)

from .semantic import (  # noqa: E402  [iter_176 分域 mixin]
    ClassesMixin,
    ConnectionsMixin,
    ExprsDriversMixin,
    ModulesMixin,
    PortsIfacesMixin,
    SourceCoreMixin,
)
from .semantic._wrappers import (  # noqa: E402,F401  向后兼容再导出
    SemanticInstanceDeclWrapper,
    SemanticInstanceWrapper,
)
from .semantic._expr_helpers import (  # noqa: E402,F401  向后兼容再导出
    _expr_assignment,
    _expr_binary,
    _expr_call,
    _expr_concatenation,
    _expr_conditional,
    _expr_conversion,
    _expr_dist,
    _expr_element_select,
    _expr_identifier_name,
    _expr_inside,
    _expr_integer_literal,
    _expr_member_access,
    _expr_named_value,
    _expr_range_select,
    _expr_scoped_name,
    _expr_unary,
    _fold_select_index,
)

from .._safe import _safe_attr, _safe_str, safe_attr, safe_str
from .._safe import clean_name as _clean_name_fn

# 确保 pyslang bindings 在 path 中 (仅当存在; 见 compiler.py 同名单 [iter_186])
PYSLLANG_BINDINGS_PATH = os.path.expanduser("~/my_dv_proj/slang/build/bindings")
if os.path.isdir(PYSLLANG_BINDINGS_PATH) and PYSLLANG_BINDINGS_PATH not in sys.path:
    sys.path.insert(0, PYSLLANG_BINDINGS_PATH)

import pyslang

from trace.core.ast_utils import is_syntax_list, iter_syntax_list


class SemanticAdapter(
    SourceCoreMixin,
    ModulesMixin,
    PortsIfacesMixin,
    ConnectionsMixin,
    ExprsDriversMixin,
    ClassesMixin,
):
    """
    Semantic AST 适配器

    将 Semantic AST (RootSymbol) 适配为统一接口,供 GraphBuilder 使用。

    主要差异 (Semantic AST vs SyntaxTree):
    - RootSymbol 包含 InstanceSymbol 列表,而非 ModuleDeclaration 列表
    - InstanceSymbol.body 包含模块成员
    - 使用 root.visit(callback) 遍历
    - 节点是语义符号 (Symbol),不是语法节点 (SyntaxNode)
    """

    def __init__(self, root, compiler=None, target_module=None):
        """
        Args:
            root: Semantic AST root (RootSymbol from comp.getRoot())
            compiler: Optional SVCompiler for accessing getDefinitions()
            target_module: [NEW 2026-07-11 Phase 2] 如果指定, get_module_instances()
                           只返该 user-specified module 的 hierarchy 子树.
                           None (默认) = 返所有 (兼容旧行为).
        """
        self._root = root
        self._compiler = compiler
        self._target_module = target_module  # [NEW 2026-07-11]
        self._fixed_names = {}  # id(cls) -> name (pyslang Unicode bug workaround)
        # [iter_170 参数化 class] GenericClassDef 无成员面 → 特化符号成员缓存
        # {class_name: [成员符号]} (从 class 类型变量/成员属性的特化 ClassType 扫)
        self._spec_members: dict[str, list] | None = None
        # [Plan F1 2026-08-12] genvar context: assign id → {genvar_name: int}
        # pyslang symbol 不允许 setattr, 不能直接挂 .genvar_ctx
        self._genvar_context = {}  # id(assign) → dict
        # [iter_112] id(primitive) → genvar ctx (generate-for 内的门, 同 assign 模式)
        self._primitive_genvar_context = {}

    @property
    def root(self) -> object:
        """返回 Semantic AST root"""
        return self._root

    @property
    def parser(self) -> object:
        """兼容属性: 返回 self 用于模拟 parser.trees"""
        return self

    @property
    def trees(self) -> dict:
        """兼容属性: 返回空字典 (Semantic AST 不需要 trees)"""
        return {}

    def items(self) -> object:
        """兼容方法: 返回空迭代器 (Semantic AST 不使用 SyntaxTree)"""
        return iter([])

    def visit(self, callback: Callable) -> None:
        """遍历 Semantic AST 所有节点"""
        self._root.visit(callback)
