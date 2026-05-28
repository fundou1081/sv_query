# covergroup_extractor.py - Covergroup 结构化提取器
#
# 使用 Semantic AST (SVCompiler) 提取 covergroup 信息。
#
# [铁律1] 必须使用编译后 Semantic AST
# [铁律3] 不可信则不输出

import logging
from typing import List, Dict, Optional

from .compiler import SVCompiler
from .graph.covergroup_models import (
    CovergroupInfo, CoverpointInfo, CoverCrossInfo, BinsInfo
)

logger = logging.getLogger(__name__)


class CovergroupExtractor:
    """Covergroup 结构化提取器

    使用 Semantic AST 提取 covergroup/coverpoint/bins/cross 信息。
    [铁律1] 通过 SVCompiler 获取编译后 AST，不使用 SyntaxTree.fromText。
    """

    def __init__(self, sources: Dict[str, str]):
        self._sources = sources

    def extract(self) -> List[CovergroupInfo]:
        """提取所有 covergroup"""
        results = []
        try:
            compiler = SVCompiler(sources=self._sources)
            root = compiler.get_root()
            self._find_covergroups(root, results)
        except Exception as e:
            logger.warning(f"编译失败: {e}")
        return results

    # =========================================================================
    # 遍历
    # =========================================================================

    def _find_covergroups(self, node, results: List[CovergroupInfo]):
        """递归查找 CovergroupType"""
        kind = str(getattr(node, 'kind', ''))

        if 'CovergroupType' in kind:
            cg = self._parse_covergroup(node)
            if cg:
                results.append(cg)
            # 继续遍历 body (可能有嵌套)

        # 遍历 Instance body 或 CompilationUnit
        if hasattr(node, 'body'):
            try:
                for child in node.body:
                    self._find_covergroups(child, results)
            except TypeError:  # pyslang Token 对象不可迭代，跳过
                pass

        # 遍历 root 的子节点
        try:
            for child in node:
                self._find_covergroups(child, results)
        except TypeError:  # pyslang Token 对象不可迭代，跳过
            pass

    # =========================================================================
    # Covergroup 解析
    # =========================================================================

    def _parse_covergroup(self, node) -> Optional[CovergroupInfo]:
        """解析 CovergroupType"""
        name = str(getattr(node, 'name', '')).strip()
        # class 内的 covergroup name 可能为空，从 syntax 获取
        if not name:
            syntax = getattr(node, 'syntax', None)
            if syntax:
                syntax_name = getattr(syntax, 'name', None)
                if syntax_name:
                    name = str(syntax_name).strip()

        # 提取采样时钟
        clock = ''
        syntax = getattr(node, 'syntax', None)
        if syntax:
            # CovergroupDeclarationSyntax 有 event 属性
            event = getattr(syntax, 'event', None)
            if event:
                clock = str(event).strip()
        if not clock:
            coverage_event = getattr(node, 'coverageEvent', None)
            if coverage_event:
                clock = str(coverage_event).strip()

        # 获取 body
        body = getattr(node, 'body', None)
        if body is None:
            return CovergroupInfo(name=name, clock=clock)

        coverpoints = []
        crosses = []

        for child in body:
            ck = str(getattr(child, 'kind', ''))
            if 'Token' in ck:
                continue
            if 'Coverpoint' in ck and 'Cross' not in ck:
                cp = self._parse_coverpoint(child)
                if cp:
                    coverpoints.append(cp)
            elif 'CoverCross' in ck:
                cross = self._parse_cover_cross(child)
                if cross:
                    crosses.append(cross)

        return CovergroupInfo(
            name=name,
            clock=clock,
            coverpoints=coverpoints,
            crosses=crosses,
        )

    # =========================================================================
    # Coverpoint 解析
    # =========================================================================

    def _parse_coverpoint(self, node) -> Optional[CoverpointInfo]:
        """解析 CoverpointSymbol"""
        name = str(getattr(node, 'name', '')).strip()

        # 提取采样信号（从 syntax 获取）
        signal = name  # 默认用 coverpoint 名作为信号名
        syntax = getattr(node, 'syntax', None)
        if syntax:
            expr = getattr(syntax, 'expr', None)
            if expr:
                signal = str(expr).strip()

        bins_list = []
        for child in node:
            ck = str(getattr(child, 'kind', ''))
            if 'Token' in ck:
                continue
            if 'CoverageBin' in ck or 'Bins' in ck:
                b = self._parse_bins(child)
                if b:
                    bins_list.append(b)

        return CoverpointInfo(
            name=name,
            signal=signal,
            bins=bins_list,
        )

    # =========================================================================
    # Bins 解析
    # =========================================================================

    def _parse_bins(self, node) -> Optional[BinsInfo]:
        """解析 CoverageBin"""
        name = str(getattr(node, 'name', '')).strip()

        # 判断 bins 类型（从 syntax 获取 keyword）
        kind = 'bins'
        syntax = getattr(node, 'syntax', None)
        if syntax:
            keyword = getattr(syntax, 'keyword', None)
            if keyword:
                keyword_str = str(keyword).strip()
                if 'illegal' in keyword_str:
                    kind = 'illegal_bins'
                elif 'ignore' in keyword_str:
                    kind = 'ignore_bins'

        # 提取值
        values = ''
        if syntax:
            initializer = getattr(syntax, 'initializer', None)
            if initializer:
                values = str(initializer).strip()
            else:
                for child in syntax:
                    ck = str(getattr(child, 'kind', ''))
                    if 'Initializer' in ck or 'Range' in ck:
                        values = str(child).strip()
                        break

        if not values:
            values = str(node).strip()

        return BinsInfo(
            name=name,
            kind=kind,
            values=values,
        )

    # =========================================================================
    # Cross 解析
    # =========================================================================

    def _parse_cover_cross(self, node) -> Optional[CoverCrossInfo]:
        """解析 CoverCross"""
        name = str(getattr(node, 'name', '')).strip()

        items = []
        targets = getattr(node, 'targets', None)
        if targets:
            for t in targets:
                t_name = str(getattr(t, 'name', '')).strip()
                if t_name:
                    items.append(t_name)

        return CoverCrossInfo(
            name=name,
            items=items,
        )
