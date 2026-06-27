"""[ADD 2026-06-27 A-PR9] Directive visitor mixin for SignalExpressionVisitor.

[REFACTOR A-PR9 2026-06-27] 抽 29 @on handler 涵盖 compile-time directive
到独立 mixin.

主 class SignalExpressionVisitor 多继承此 mixin, 改 1 行平均 5 min → 30s.

Handler 类别:
- Conditional: IfDefDirective/IfNDefDirective/ElsIfDirective/ElseDirective/EndIfDirective
- Keyword/Block: BeginKeywordsDirective/EndKeywordsDirective/CellDefineDirective/EndCellDefineDirective
- Include/Source: IncludeDirective/LineDirective
- Define/Macro: DefineDirective/UndefDirective/UndefineAllDirective
- TimeScale: TimeScaleDirective
- Protection: ProtectDirective/ProtectedDirective/EndProtectDirective/EndProtectedDirective
- Drive: NoUnconnectedDriveDirective/UnconnectedDriveDirective
- Delay: DefaultDecayTimeDirective/DefaultTriregStrengthDirective/DelayModePathDirective/DelayModeUnitDirective/DelayModeZeroDirective
- Bind/Reset: BindDirective/ResetAllDirective
- Pragma: PragmaDirective

Total: 29 @on handler (~287 行, 7-10 行 boilerplate each)
"""
from typing import TYPE_CHECKING

from ._decorators import on
from .signal_result import SignalResult

if TYPE_CHECKING:
    from .signal_expression_visitor import SignalExpressionVisitor


class DirectiveVisitor:
    """[ADD 2026-06-27 A-PR9] 抽所有 compile-time directive @on handler
    到独立 mixin.

    主 class SignalExpressionVisitor 多继承此 mixin, 行为不变.
    """

    @on("BindDirective")
    def extract_bind_directive(self, node) -> SignalResult:
        """[NOT TESTED] BindDirective: bind directive"""
        result = SignalResult()
        target = getattr(node, "target", None) or getattr(node, "expr", None)
        if target:
            result = result.merge(self.extract(target))
        return result

    @on("UnconnectedDriveDirective")
    def extract_unconnecteddrivedirective(self, node) -> SignalResult:
        """[NOT TESTED] UnconnectedDriveDirective: Unconnecteddrivedirective"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("UndefDirective")
    def extract_undefdirective(self, node) -> SignalResult:
        """[NOT TESTED] UndefDirective: Undefdirective"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("UndefineAllDirective")
    def extract_undefinealldirective(self, node) -> SignalResult:
        """[NOT TESTED] UndefineAllDirective: Undefinealldirective"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("TimeScaleDirective")
    def extract_timescaledirective(self, node) -> SignalResult:
        """[NOT TESTED] TimeScaleDirective: Timescaledirective"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("PragmaDirective")
    def extract_pragmadirective(self, node) -> SignalResult:
        """[NOT TESTED] PragmaDirective: Pragmadirective"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("ProtectDirective")
    def extract_protectdirective(self, node) -> SignalResult:
        """[NOT TESTED] ProtectDirective: Protectdirective"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("ProtectedDirective")
    def extract_protecteddirective(self, node) -> SignalResult:
        """[NOT TESTED] ProtectedDirective: Protecteddirective"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("ResetAllDirective")
    def extract_resetalldirective(self, node) -> SignalResult:
        """[NOT TESTED] ResetAllDirective: Resetalldirective"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("NoUnconnectedDriveDirective")
    def extract_nounconnecteddrivedirective(self, node) -> SignalResult:
        """[NOT TESTED] NoUnconnectedDriveDirective: Nounconnecteddrivedirective"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("IfDefDirective")
    def extract_ifdefdirective(self, node) -> SignalResult:
        """[NOT TESTED] IfDefDirective: Ifdefdirective"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("IfNDefDirective")
    def extract_ifndefdirective(self, node) -> SignalResult:
        """[NOT TESTED] IfNDefDirective: Ifndefdirective"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("IncludeDirective")
    def extract_includedirective(self, node) -> SignalResult:
        """[NOT TESTED] IncludeDirective: Includedirective"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("LineDirective")
    def extract_linedirective(self, node) -> SignalResult:
        """[NOT TESTED] LineDirective: Linedirective"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("ElsIfDirective")
    def extract_elsifdirective(self, node) -> SignalResult:
        """[NOT TESTED] ElsIfDirective: Elsifdirective"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("ElseDirective")
    def extract_elsedirective(self, node) -> SignalResult:
        """[NOT TESTED] ElseDirective: Elsedirective"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("EndCellDefineDirective")
    def extract_endcelldefinedirective(self, node) -> SignalResult:
        """[NOT TESTED] EndCellDefineDirective: Endcelldefinedirective"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("EndIfDirective")
    def extract_endifdirective(self, node) -> SignalResult:
        """[NOT TESTED] EndIfDirective: Endifdirective"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("EndKeywordsDirective")
    def extract_endkeywordsdirective(self, node) -> SignalResult:
        """[NOT TESTED] EndKeywordsDirective: Endkeywordsdirective"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("EndProtectDirective")
    def extract_endprotectdirective(self, node) -> SignalResult:
        """[NOT TESTED] EndProtectDirective: Endprotectdirective"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("EndProtectedDirective")
    def extract_endprotecteddirective(self, node) -> SignalResult:
        """[NOT TESTED] EndProtectedDirective: Endprotecteddirective"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("DefaultDecayTimeDirective")
    def extract_defaultdecaytimedirective(self, node) -> SignalResult:
        """[NOT TESTED] DefaultDecayTimeDirective: Defaultdecaytimedirective"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("DefaultTriregStrengthDirective")
    def extract_defaulttriregstrengthdirective(self, node) -> SignalResult:
        """[NOT TESTED] DefaultTriregStrengthDirective: Defaulttriregstrengthdirective"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("DefineDirective")
    def extract_definedirective(self, node) -> SignalResult:
        """[NOT TESTED] DefineDirective: Definedirective"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("DelayModePathDirective")
    def extract_delaymodepathdirective(self, node) -> SignalResult:
        """[NOT TESTED] DelayModePathDirective: Delaymodepathdirective"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("DelayModeUnitDirective")
    def extract_delaymodeunitdirective(self, node) -> SignalResult:
        """[NOT TESTED] DelayModeUnitDirective: Delaymodeunitdirective"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("DelayModeZeroDirective")
    def extract_delaymodezerodirective(self, node) -> SignalResult:
        """[NOT TESTED] DelayModeZeroDirective: Delaymodezerodirective"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("BeginKeywordsDirective")
    def extract_beginkeywordsdirective(self, node) -> SignalResult:
        """[NOT TESTED] BeginKeywordsDirective: Beginkeywordsdirective"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("CellDefineDirective")
    def extract_celldefinedirective(self, node) -> SignalResult:
        """[NOT TESTED] CellDefineDirective: Celldefinedirective"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

