"""[ADD 2026-06-27 A-PR10] Port visitor mixin for SignalExpressionVisitor.

[REFACTOR A-PR10 2026-06-27] 抽 19 @on handler 涵盖 port/modport/port-connection/UDP-port
到独立 mixin.

主 class SignalExpressionVisitor 多继承此 mixin, 改 1 行平均 5 min → 30s.

Handler 类别:
- Function Port: DefaultFunctionPort/FunctionPort
- Modport: ModportItem/ModportClockingPort/ModportExplicitPort/ModportNamedPort/ModportSubroutinePort
- Port Connection: WildcardPortConnection/NamedPortConnection/OrderedPortConnection/PortReference
- UDP Port: UdpInputPortDecl/UdpOutputPortDecl
- Ansi Port: EmptyNonAnsiPort/ExplicitAnsiPort/ExplicitNonAnsiPort/ImplicitAnsiPort/ImplicitNonAnsiPort
- Empty: EmptyPortConnection

Total: 19 @on handler (~213 行, 5-12 行 boilerplate each)
"""
from typing import TYPE_CHECKING

from ._decorators import on
from .signal_result import SignalResult

if TYPE_CHECKING:
    from .signal_expression_visitor import SignalExpressionVisitor


class PortVisitor:
    """[ADD 2026-06-27 A-PR10] 抽所有 port/modport/port-connection/UDP-port
    @on handler 到独立 mixin.

    主 class SignalExpressionVisitor 多继承此 mixin, 行为不变.
    """

    @on("DefaultFunctionPort")
    def extract_default_function_port(self, node) -> SignalResult:
        """[NOT TESTED] DefaultFunctionPort: default function port"""
        return SignalResult()

    @on("ModportItem")
    def extract_modport_item(self, node) -> SignalResult:
        """[NOT TESTED] ModportItem: modport item"""
        result = SignalResult()
        signal = getattr(node, "signal", None) or getattr(node, "expr", None)
        if signal:
            result = result.merge(self.extract(signal))
        return result

    @on("FunctionPort")
    def extract_function_port(self, node) -> SignalResult:
        """[NOT TESTED] FunctionPort: function port"""
        result = SignalResult()
        var = getattr(node, "variable", None) or getattr(node, "var", None)
        if var:
            result = result.merge(self.extract(var))
        return result

    @on("ModportClockingPort")
    def extract_modport_clocking_port(self, node) -> SignalResult:
        """[NOT TESTED] ModportClockingPort: modport clocking port"""
        return SignalResult()

    @on("ModportExplicitPort")
    def extract_modport_explicit_port(self, node) -> SignalResult:
        """[NOT TESTED] ModportExplicitPort: modport explicit port"""
        result = SignalResult()
        expr = getattr(node, "expr", None) or getattr(node, "signal", None)
        if expr:
            result = result.merge(self.extract(expr))
        return result

    @on("ModportNamedPort")
    def extract_modport_named_port(self, node) -> SignalResult:
        """[NOT TESTED] ModportNamedPort: modport named port"""
        result = SignalResult()
        expr = getattr(node, "expr", None) or getattr(node, "signal", None)
        if expr:
            result = result.merge(self.extract(expr))
        return result

    @on("ModportSubroutinePort")
    def extract_modport_subroutine_port(self, node) -> SignalResult:
        """[NOT TESTED] ModportSubroutinePort: modport subroutine port"""
        return SignalResult()

    @on("WildcardPortConnection")
    def extract_wildcardportconnection(self, node) -> SignalResult:
        """[NOT TESTED] WildcardPortConnection: Wildcardportconnection"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("UdpInputPortDecl")
    def extract_udpinputportdecl(self, node) -> SignalResult:
        """[NOT TESTED] UdpInputPortDecl: Udpinputportdecl"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("UdpOutputPortDecl")
    def extract_udpoutputportdecl(self, node) -> SignalResult:
        """[NOT TESTED] UdpOutputPortDecl: Udpoutputportdecl"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("NamedPortConnection")
    def extract_namedportconnection(self, node) -> SignalResult:
        """[NOT TESTED] NamedPortConnection: Namedportconnection"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("OrderedPortConnection")
    def extract_orderedportconnection(self, node) -> SignalResult:
        """[NOT TESTED] OrderedPortConnection: Orderedportconnection"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("PortReference")
    def extract_portreference(self, node) -> SignalResult:
        """[NOT TESTED] PortReference: Portreference"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("EmptyNonAnsiPort")
    def extract_emptynonansiport(self, node) -> SignalResult:
        """[NOT TESTED] EmptyNonAnsiPort: Emptynonansiport"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("EmptyPortConnection")
    def extract_emptyportconnection(self, node) -> SignalResult:
        """[NOT TESTED] EmptyPortConnection: Emptyportconnection"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("ExplicitAnsiPort")
    def extract_explicitansiport(self, node) -> SignalResult:
        """[NOT TESTED] ExplicitAnsiPort: Explicitansiport"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("ExplicitNonAnsiPort")
    def extract_explicitnonansiport(self, node) -> SignalResult:
        """[NOT TESTED] ExplicitNonAnsiPort: Explicitnonansiport"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("ImplicitAnsiPort")
    def extract_implicit_ansi_port(self, node) -> SignalResult:
        """[NOT TESTED] ImplicitAnsiPort: implicit ansi port"""
        result = SignalResult()
        name = getattr(node, "name", None)
        if name:
            result.add_signal(str(name))
        return result

    @on("ImplicitNonAnsiPort")
    def extract_implicit_non_ansi_port(self, node) -> SignalResult:
        """[NOT TESTED] ImplicitNonAnsiPort: implicit non-ansi port"""
        result = SignalResult()
        name = getattr(node, "name", None)
        if name:
            result.add_signal(str(name))
        return result

