# source_core.py — SemanticAdapter 的 source_core 域 mixin (iter_176 分域搬迁)
#
# 方法名/签名与原 SemanticAdapter 完全一致 (API 面冻结测试锁定);
# `self` 即 SemanticAdapter 实例, 无独立状态。
"""source_core 域: 源位置/文本/子节点/名字清洗"""
import logging
from typing import Callable, Iterator

from ..._safe import _safe_attr, _safe_str, clean_name, safe_attr, safe_str
from ..._safe import clean_name as _clean_name_fn
from ..ast_utils import is_syntax_list, iter_syntax_list

logger = logging.getLogger(__name__)


class SourceCoreMixin:
    """source_core 域方法集 (mixin — 由 SemanticAdapter 组合)"""

    def get_source_location(self, node) -> tuple:
        """获取节点的源码位置

        [Stage 1] 从 semantic_node.syntax.sourceRange + SourceManager 拿真实位置
        之前返回空值 (注释说"需要从 SyntaxTree 获取"), 现已修复.

        Returns:
            tuple: (filename, line, column, offset)
            - filename: str, 源文件路径 (如 "test.sv")
            - line: int, 1-indexed 起始行
            - column: int, 0-indexed 起始列
            - offset: int, 结束 offset (备用)

        如果节点无 syntax 信息 (e.g., 虚拟节点), 返回空位置
        """
        if node is None:
            return ("", 0, 0, 0)
        # 拿 syntax 节点
        # 兼容两种情况: 1) node 是 semantic node (有 .syntax 属性)
        #               2) node 本身是 syntax node (直接有 .sourceRange)
        syn = getattr(node, "syntax", None)
        if syn is None:
            # 可能是 syntax node 直接 (如 IntegerVectorExpressionSyntax)
            syn = node if getattr(node, "sourceRange", None) is not None else None
        if syn is None:
            return ("", 0, 0, 0)
        sr = getattr(syn, "sourceRange", None)
        if sr is None:
            return ("", 0, 0, 0)

        # 拿 SourceManager
        # 兼容传 SVCompiler 或 Compilation 两种情况
        try:
            compiler_or_comp = self._compiler
            if hasattr(compiler_or_comp, "get_compilation"):
                sm = compiler_or_comp.get_compilation().sourceManager
            else:
                sm = compiler_or_comp.sourceManager
        except AttributeError:
            return ("", 0, 0, 0)

        # 拿文件路径
        try:
            filename = sm.getFileName(sr.start)
        except Exception:
            filename = ""

        # 拿 line/column
        try:
            line = sm.getLineNumber(sr.start)
            col = sm.getColumnNumber(sr.start)
        except Exception:
            line, col = 0, 0

        return (filename, line, col, sr.end.offset)


    def get_source_text(self, node) -> str:
        """[iter_101] 获取节点 sourceRange 对应的源码片段 (非整份文件)

        Args:
            node: semantic AST node (或 syntax node, 有 .sourceRange 即可)

        Returns:
            str: 节点源码片段 (start.offset → end.offset 切片), 失败返回空字符串

        [缺陷 A 修复 2026-09-02] 原实现 `sm.getSourceText(buf)` 返回整个 buffer
        的完整源码 (含末尾 \x00), 导致所有 assign/always 边的 expression 字段
        变成整份文件+空字节 (下游 handshake/dataflow/viz 消费受影响)。
        修复: 按 sr.start.offset / sr.end.offset 切片取节点源码片段。
        """
        if node is None:
            return ""
        syn = getattr(node, "syntax", None) or node
        sr = getattr(syn, "sourceRange", None)
        if sr is None:
            return ""
        try:
            sm = self._compiler.get_compilation().sourceManager
            buf = sr.start.buffer
            if buf is None:
                return ""
            text = sm.getSourceText(buf)
            start = sr.start.offset
            end = sr.end.offset
            # [iter_101] pyslang offset 是 UTF-8 **字节**偏移 (非字符) —
            # 源含非 ASCII (如注释里的 —) 时字符切片会错位, 必须按字节切片再解码.
            raw = text.encode("utf-8")
            return raw[start:end].decode("utf-8", errors="replace")
        except Exception:
            return ""

    # =========================================================================
    # 模块和实例相关
    # =========================================================================


    def _iter_children(self, node) -> list:
        """安全遍历子节点"""
        if node is None:
            return []

        children = []

        # 处理可迭代对象
        if hasattr(node, "__iter__") and not isinstance(node, (str, bytes)):
            try:
                for child in node:
                    children.append(child)
            except TypeError as e:
                logger.debug("子节点迭代失败: %s", e)
                pass

        # 处理常见属性
        for attr in [
            "members",
            "body",
            "statement",
            "statements",
            "stmt",       # [#8 2026-08-28] TimedStatement (@(posedge clk) ...) 用 .stmt,
                          # 不是 .statement — 缺它导致 generate always 内赋值拿不到 genvar_ctx
            "list",       # [#8 2026-08-28] StatementKind.List 的语句列表 (.list),
                          # 双赋值时 Block → List → ExpressionStatement 链需要它
            "left",
            "right",
            "expr",
            "condition",
            "consequent",
            "alternate",
        ]:
            try:
                child = getattr(node, attr, None)
            except (RuntimeError, Exception) as e:
                # [FIX 2026-06-26] pyslang: 'mutex lock failed: Invalid argument'
                # elaboration 不完整时, InstanceSymbol attribute access 死锁
                # 注: 某些 native segfault 会绕过 RuntimeError 抛 BaseException
                try:
                    if 'mutex' not in str(e).lower():
                        raise
                except Exception as e2:
                    logger.debug("pyslang mutex 防御 (partial AST): %s", e2)
                child = None
            if child:
                if isinstance(child, list):
                    children.extend(child)
                elif hasattr(child, "kind"):
                    children.append(child)

        return children

    # =========================================================================
    # 工具方法
    # =========================================================================


    def clean_name(self, name) -> str:
        """清理信号名称 (移除多余空白等)

        容忍非 utf-8 字节的 identifier (e.g. escape 序列)。
        如果转换失败,返回 hex 形式以保证唯一性。

        [P0-1 2026-06-13] 收口: 委托给 _safe.clean_name (单一规范实现),
        不再重复过滤逻辑。参见 _safe.py 文档。
        """
        return _clean_name_fn(name)

    @staticmethod


    def _safe_str(obj) -> str:
        """DEPRECATED: 委托给 _safe.safe_str (单一规范实现)。"""
        return safe_str(obj)


    def get_definition(self, name: str) -> object:
        """获取模块/类定义"""
        for item in self._root:
            if hasattr(item, "name") and item.name == name:
                return item
        return None
