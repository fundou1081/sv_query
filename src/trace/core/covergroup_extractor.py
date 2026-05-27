# covergroup_extractor.py - Covergroup 结构化提取器
#
# 直接遍历 pyslang 语法树，提取 covergroup 信息。
# 不修改 SignalGraph，独立输出。
#
# [铁律15] Visitor 模式
# [铁律4] 模型即契约

import logging
from typing import List, Dict, Optional

import pyslang

from .graph.covergroup_models import (
    CovergroupInfo, CoverpointInfo, CoverCrossInfo, BinsInfo
)

logger = logging.getLogger(__name__)


class CovergroupExtractor:
    """Covergroup 结构化提取器

    直接遍历 pyslang 语法树，提取 covergroup/coverpoint/bins/cross 信息。
    不经过 GraphBuilder，独立输出 CovergroupInfo 列表。

    支持:
    - module 内的 covergroup
    - class 内的 covergroup
    - bins / illegal_bins / ignore_bins
    - cross coverage
    - 采样时钟提取
    """

    def __init__(self, sources: Dict[str, str]):
        """
        Args:
            sources: {filename: source_code} 字典
        """
        self._sources = sources

    def extract(self) -> List[CovergroupInfo]:
        """提取所有 covergroup"""
        results = []
        for fname, source in self._sources.items():
            try:
                tree = pyslang.SyntaxTree.fromText(source)
                self._walk(tree.root, fname, results)
            except Exception as e:
                logger.warning(f"解析 {fname} 失败: {e}")
        return results

    # =========================================================================
    # 递归遍历
    # =========================================================================

    def _walk(self, node, fname: str, results: List[CovergroupInfo]):
        """递归查找 CovergroupDeclaration"""
        kind = str(getattr(node, 'kind', ''))

        if 'CovergroupDeclaration' in kind:
            cg = self._parse_covergroup(node, fname)
            if cg:
                results.append(cg)
            return  # 不递归进入 covergroup 内部

        # 递归子节点（跳过 Token）
        if hasattr(node, '__iter__'):
            try:
                for child in node:
                    ck = str(getattr(child, 'kind', ''))
                    if 'Token' in ck:
                        continue
                    self._walk(child, fname, results)
            except TypeError:
                pass

    # =========================================================================
    # Covergroup 解析
    # =========================================================================

    def _parse_covergroup(self, node, fname: str) -> Optional[CovergroupInfo]:
        """解析单个 CovergroupDeclaration"""
        name = str(getattr(node, 'name', '')).strip()

        # 找成员列表 (SyntaxList)
        members_list = self._find_members_list(node)
        if members_list is None:
            return None

        # 提取采样时钟
        clock = self._extract_clock(node)

        # 解析成员
        coverpoints = []
        crosses = []

        for member in members_list:
            mk = str(getattr(member, 'kind', ''))
            if 'Token' in mk:
                continue
            if 'CoverCross' in mk:
                cross = self._parse_cover_cross(member)
                if cross:
                    crosses.append(cross)
            elif 'Coverpoint' in mk:
                cp = self._parse_coverpoint(member)
                if cp:
                    coverpoints.append(cp)

        # 提取源码位置
        source_line = 0
        source_range = getattr(node, 'sourceRange', None)
        if source_range:
            try:
                source_line = source_range.start.line
            except Exception:
                pass

        return CovergroupInfo(
            name=name,
            clock=clock,
            coverpoints=coverpoints,
            crosses=crosses,
            source_file=fname,
            source_line=source_line,
        )

    def _find_members_list(self, node):
        """找到 CovergroupDeclaration 的成员 SyntaxList

        结构: [attributes, keyword, name, clock, semicolon, MEMBERS, endgroup]
        members 在 SyntaxList 中，跳过前几个 token 找到包含 Coverpoint/CoverCross 的列表。
        """
        children = list(node)
        # 从后往前找第一个包含 Coverpoint/CoverCross 的 SyntaxList
        for child in reversed(children):
            ck = str(getattr(child, 'kind', ''))
            if 'SyntaxList' not in ck:
                continue
            # 检查是否包含 Coverpoint 或 CoverCross
            for sub in child:
                sk = str(getattr(sub, 'kind', ''))
                if 'Coverpoint' in sk or 'CoverCross' in sk or 'Bins' in sk:
                    return child
        return None

    def _extract_clock(self, node) -> str:
        """提取采样时钟 @(posedge clk)"""
        for child in node:
            ck = str(getattr(child, 'kind', ''))
            if 'EventControl' in ck:
                return str(child).strip()
        return ''

    # =========================================================================
    # Coverpoint 解析
    # =========================================================================

    def _parse_coverpoint(self, node) -> Optional[CoverpointInfo]:
        """解析单个 Coverpoint"""
        signal = ''
        bins_list = []

        for child in node:
            ck = str(getattr(child, 'kind', ''))
            if 'Token' in ck:
                continue

            # 信号名: IdentifierName
            if 'IdentifierName' in ck:
                ident = getattr(child, 'identifier', None)
                if ident and hasattr(ident, 'value'):
                    signal = str(ident.value).strip()
                else:
                    signal = str(child).strip()

            # bins 列表: SyntaxList 包含 CoverageBins
            if 'SyntaxList' in ck:
                for sub in child:
                    sk = str(getattr(sub, 'kind', ''))
                    if 'CoverageBins' in sk or 'Bins' in sk:
                        b = self._parse_bins(sub)
                        if b:
                            bins_list.append(b)

        return CoverpointInfo(
            name=signal,  # 使用信号名作为 coverpoint 名称
            signal=signal,
            bins=bins_list,
        )

    # =========================================================================
    # Bins 解析
    # =========================================================================

    def _parse_bins(self, node) -> Optional[BinsInfo]:
        """解析单个 CoverageBins"""
        name = str(getattr(node, 'name', '')).strip()

        # 判断 bins 类型
        keyword = getattr(node, 'keyword', None)
        keyword_str = str(keyword).strip() if keyword else 'bins'
        if 'illegal' in keyword_str:
            kind = 'illegal_bins'
        elif 'ignore' in keyword_str:
            kind = 'ignore_bins'
        else:
            kind = 'bins'

        # 提取值
        values = self._extract_bins_values(node)

        return BinsInfo(
            name=name,
            kind=kind,
            values=values,
        )

    def _extract_bins_values(self, node) -> str:
        """提取 bins 的值描述"""
        # 查找 Initializer 或 Expression 子节点
        for child in node:
            ck = str(getattr(child, 'kind', ''))
            if 'Token' in ck:
                continue
            if 'Initializer' in ck or 'Expression' in ck or 'Range' in ck:
                return str(child).strip()

        # fallback: 整个节点的字符串表示
        return str(node).strip()

    # =========================================================================
    # Cross 解析
    # =========================================================================

    def _parse_cover_cross(self, node) -> Optional[CoverCrossInfo]:
        """解析 CoverCross"""
        name = str(getattr(node, 'name', '')).strip()
        items = []

        for child in node:
            ck = str(getattr(child, 'kind', ''))
            if 'Token' in ck:
                continue
            # SeparatedList 包含 cross 的 coverpoint 列表
            if 'SeparatedList' in ck:
                for item in child:
                    ik = str(getattr(item, 'kind', ''))
                    if 'Token' in ik:
                        continue
                    items.append(str(item).strip())
            # IdentifierName (单个 cross 项)
            elif 'IdentifierName' in ck:
                items.append(str(child).strip())

        return CoverCrossInfo(
            name=name,
            items=items,
        )
