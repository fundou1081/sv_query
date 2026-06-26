"""[ADD 2026-06-27 A-PR6] Declaration visitor mixin for SignalExpressionVisitor.

[REFACTOR A-PR6 2026-06-27] 抽 45 @on handler 涵盖 declaration/port/typedef/interface
到独立 mixin.

主 class SignalExpressionVisitor 多继承此 mixin, 改 1 行平均 5 min → 30s.

Handler 类别:
- Module/Interface/Program: ModuleDeclaration/InterfaceDeclaration/ProgramDeclaration
- Class: ConstraintDeclaration/CovergroupDeclaration/CheckerDeclaration
- Port: PortDeclaration/NetPortHeader/InterfacePortHeader/VariablePortHeader/AnsiPortList/NonAnsiPortList/...
- Function/Task: FunctionDeclaration/TaskDeclaration/FunctionPortList
- Declaration: DataDeclaration/NetDeclaration/TypedefDeclaration/LetDeclaration/...
- Net: GenvarDeclaration/NetTypeDeclaration/UserDefinedNetDeclaration
- Modport: ModportDeclaration/ModportSimplePortList/ModportSubroutinePortList
- UDP: UdpDeclaration/AnsiUdpPortList/NonAnsiUdpPortList/WildcardUdpPortList
- Misc: ClockingDeclaration/DefaultDisableDeclaration/SequenceDeclaration/TimeUnitsDeclaration/...

Total: 45 @on handler (~388 行, 9-15 行 boilerplate each)
"""
from typing import TYPE_CHECKING

from ._decorators import on
from .signal_result import SignalResult

if TYPE_CHECKING:
    from .signal_expression_visitor import SignalExpressionVisitor


class DeclarationVisitor:
    """[ADD 2026-06-27 A-PR6] 抽所有 declaration/port/typedef @on handler 到独立 mixin.

    主 class SignalExpressionVisitor 多继承此 mixin, 行为不变.
    """

    @on("LetDeclaration")
    def extract_let_declaration(self, node) -> SignalResult:
        """[NOT TESTED] LetDeclaration: let declaration"""
        result = SignalResult()
        args = getattr(node, "arguments", None)
        if args and hasattr(args, "__iter__"):
            for arg in args:
                if arg:
                    result = result.merge(self.extract(arg))
        body = getattr(node, "body", None) or getattr(node, "expr", None)
        if body:
            result = result.merge(self.extract(body))
        return result

    @on("ConstraintDeclaration")
    def extract_constraint_declaration(self, node) -> SignalResult:
        """[NOT TESTED] ConstraintDeclaration: constraint declaration"""
        result = SignalResult()
        items = getattr(node, "items", None) or getattr(node, "constraints", None)
        if items and hasattr(items, "__iter__"):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result

    @on("CheckerDeclaration")
    def extract_checker_declaration(self, node) -> SignalResult:
        """[NOT TESTED] CheckerDeclaration: checker declaration"""
        result = SignalResult()
        body = getattr(node, "body", None) or getattr(node, "statements", None)
        if body and hasattr(body, "__iter__"):
            for stmt in body:
                if stmt:
                    result = result.merge(self.extract(stmt))
        return result

    @on("CheckerDataDeclaration")
    def extract_checker_data_declaration(self, node) -> SignalResult:
        """[NOT TESTED] CheckerDataDeclaration: checker data declaration"""
        return SignalResult()

    # Coverage-related
    @on("AssertionItemPortList")
    def extract_assertion_item_port_list(self, node) -> SignalResult:
        """[NOT TESTED] AssertionItemPortList: assertion item port list"""
        return SignalResult()

    @on("CovergroupDeclaration")
    def extract_covergroup_declaration(self, node) -> SignalResult:
        """[NOT TESTED] CovergroupDeclaration: covergroup declaration"""
        result = SignalResult()
        items = getattr(node, "items", None) or getattr(node, "coverpoints", None)
        if items and hasattr(items, "__iter__"):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result

    @on("DefaultDisableDeclaration")
    def extract_default_disable_declaration(self, node) -> SignalResult:
        """[NOT TESTED] DefaultDisableDeclaration: default disable declaration"""
        expr = getattr(node, "expr", None) or getattr(node, "disable", None)
        if expr:
            return self.extract(expr)
        return SignalResult()

    # Conditional pattern
    @on("ModportDeclaration")
    def extract_modport_declaration(self, node) -> SignalResult:
        """[NOT TESTED] ModportDeclaration: modport declaration"""
        return SignalResult()

    @on("FunctionDeclaration")
    def extract_function_declaration(self, node) -> SignalResult:
        """[NOT TESTED] FunctionDeclaration: function declaration"""
        result = SignalResult()
        body = getattr(node, "body", None) or getattr(node, "statements", None)
        if body and hasattr(body, "__iter__"):
            for stmt in body:
                if stmt:
                    result = result.merge(self.extract(stmt))
        return result

    @on("TaskDeclaration")
    def extract_task_declaration(self, node) -> SignalResult:
        """[NOT TESTED] TaskDeclaration: task declaration"""
        result = SignalResult()
        body = getattr(node, "body", None) or getattr(node, "statements", None)
        if body and hasattr(body, "__iter__"):
            for stmt in body:
                if stmt:
                    result = result.merge(self.extract(stmt))
        return result

    @on("ModuleDeclaration")
    def extract_module_declaration(self, node) -> SignalResult:
        """[NOT TESTED] ModuleDeclaration: module declaration"""
        return SignalResult()

    @on("InterfaceDeclaration")
    def extract_interface_declaration(self, node) -> SignalResult:
        """[NOT TESTED] InterfaceDeclaration: interface declaration"""
        return SignalResult()

    @on("ProgramDeclaration")
    def extract_program_declaration_stmt(self, node) -> SignalResult:
        """[NOT TESTED] ProgramDeclaration: program declaration"""
        return SignalResult()

    # Generate constructs
    @on("PortDeclaration")
    def extract_port_declaration(self, node) -> SignalResult:
        """[NOT TESTED] PortDeclaration: port declaration"""
        result = SignalResult()
        init = getattr(node, "init", None) or getattr(node, "value", None)
        if init:
            result = result.merge(self.extract(init))
        return result

    @on("ForVariableDeclaration")
    def extract_for_variable_declaration(self, node) -> SignalResult:
        """[NOT TESTED] ForVariableDeclaration: for loop variable declaration"""
        result = SignalResult()
        var = getattr(node, "variable", None) or getattr(node, "var", None)
        if var:
            result = result.merge(self.extract(var))
        init = getattr(node, "init", None) or getattr(node, "expr", None)
        if init:
            result = result.merge(self.extract(init))
        return result

    @on("SequenceDeclaration")
    def extract_sequence_declaration_stmt(self, node) -> SignalResult:
        """[NOT TESTED] SequenceDeclaration: sequence declaration"""
        result = SignalResult()
        items = getattr(node, "items", None) or getattr(node, "body", None)
        if items and hasattr(items, "__iter__"):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result

    @on("DataDeclaration")
    def extract_data_declaration(self, node) -> SignalResult:
        """[NOT TESTED] DataDeclaration: data declaration (variables, nets)"""
        result = SignalResult()
        items = getattr(node, "declarators", None) or getattr(node, "items", None)
        if items and hasattr(items, "__iter__"):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result

    @on("NetDeclaration")
    def extract_net_declaration(self, node) -> SignalResult:
        """[NOT TESTED] NetDeclaration: net declaration"""
        result = SignalResult()
        items = getattr(node, "declarators", None) or getattr(node, "items", None)
        if items and hasattr(items, "__iter__"):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result

    @on("TypedefDeclaration")
    def extract_typedef_declaration_stmt(self, node) -> SignalResult:
        """[NOT TESTED] TypedefDeclaration: typedef declaration"""
        return SignalResult()

    @on("ForwardTypedefDeclaration")
    def extract_forward_typedef_declaration(self, node) -> SignalResult:
        """[NOT TESTED] ForwardTypedefDeclaration: forward typedef declaration"""
        return SignalResult()

    @on("FunctionPortList")
    def extract_function_port_list(self, node) -> SignalResult:
        """[NOT TESTED] FunctionPortList: function port list"""
        result = SignalResult()
        ports = getattr(node, "ports", None)
        if ports and hasattr(ports, "__iter__"):
            for port in ports:
                if port:
                    result = result.merge(self.extract(port))
        return result

    @on("LocalVariableDeclaration")
    def extract_local_variable_declaration(self, node) -> SignalResult:
        """[NOT TESTED] LocalVariableDeclaration: local variable declaration"""
        result = SignalResult()
        var = getattr(node, "variable", None) or getattr(node, "var", None)
        if var:
            result = result.merge(self.extract(var))
        return result

    @on("GenvarDeclaration")
    def extract_genvar_declaration(self, node) -> SignalResult:
        """[NOT TESTED] GenvarDeclaration: genvar declaration"""
        return SignalResult()

    @on("NetTypeDeclaration")
    def extract_net_type_declaration(self, node) -> SignalResult:
        """[NOT TESTED] NetTypeDeclaration: net type declaration"""
        return SignalResult()

    @on("ClockingDeclaration")
    def extract_clocking_declaration(self, node) -> SignalResult:
        """[NOT TESTED] ClockingDeclaration: clocking block declaration"""
        result = SignalResult()
        items = getattr(node, "items", None)
        if items and hasattr(items, "__iter__"):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result

    @on("TimeUnitsDeclaration")
    def extract_time_units_declaration(self, node) -> SignalResult:
        """[NOT TESTED] TimeUnitsDeclaration: time units declaration"""
        return SignalResult()

    # Modport declarations
    @on("ModportSimplePortList")
    def extract_modport_simple_port_list(self, node) -> SignalResult:
        """[NOT TESTED] ModportSimplePortList: modport simple port list"""
        result = SignalResult()
        ports = getattr(node, "ports", None)
        if ports and hasattr(ports, "__iter__"):
            for port in ports:
                if port:
                    result = result.merge(self.extract(port))
        return result

    @on("ModportSubroutinePortList")
    def extract_modport_subroutine_port_list(self, node) -> SignalResult:
        """[NOT TESTED] ModportSubroutinePortList: modport subroutine port list"""
        result = SignalResult()
        ports = getattr(node, "ports", None)
        if ports and hasattr(ports, "__iter__"):
            for port in ports:
                if port:
                    result = result.merge(self.extract(port))
        return result

    @on("InterfacePortHeader")
    def extract_interface_port_header(self, node) -> SignalResult:
        """[NOT TESTED] InterfacePortHeader: interface port header"""
        return SignalResult()

    @on("IfNonePathDeclaration")
    def extract_if_none_path_declaration(self, node) -> SignalResult:
        """[NOT TESTED] IfNonePathDeclaration: ifnone path declaration"""
        return SignalResult()

    @on("PathDeclaration")
    def extract_path_declaration(self, node) -> SignalResult:
        """[NOT TESTED] PathDeclaration: path declaration"""
        return SignalResult()

    @on("PulseStyleDeclaration")
    def extract_pulse_style_declaration(self, node) -> SignalResult:
        """[NOT TESTED] PulseStyleDeclaration: pulse style declaration"""
        return SignalResult()

    @on("ConfigDeclaration")
    def extract_config_declaration(self, node) -> SignalResult:
        """[NOT TESTED] ConfigDeclaration: config declaration"""
        return SignalResult()

    @on("LibraryDeclaration")
    def extract_library_declaration(self, node) -> SignalResult:
        """[NOT TESTED] LibraryDeclaration: library declaration"""
        return SignalResult()

    @on("SpecparamDeclaration")
    def extract_specparam_declaration(self, node) -> SignalResult:
        """[NOT TESTED] SpecparamDeclaration: specparam declaration"""
        result = SignalResult()
        expr = getattr(node, "expr", None) or getattr(node, "value", None)
        if expr:
            result = result.merge(self.extract(expr))
        return result

    @on("UdpDeclaration")
    def extract_udp_declaration(self, node) -> SignalResult:
        """[NOT TESTED] UdpDeclaration: UDP declaration (Verilog primitive)"""
        return SignalResult()

    @on("UserDefinedNetDeclaration")
    def extract_user_defined_net_declaration(self, node) -> SignalResult:
        """[NOT TESTED] UserDefinedNetDeclaration: user defined net declaration"""
        return SignalResult()

    @on("VariablePortHeader")
    def extract_variableportheader(self, node) -> SignalResult:
        """[NOT TESTED] VariablePortHeader: Variableportheader"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("WildcardPortList")
    def extract_wildcardportlist(self, node) -> SignalResult:
        """[NOT TESTED] WildcardPortList: Wildcardportlist"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("WildcardUdpPortList")
    def extract_wildcardudpportlist(self, node) -> SignalResult:
        """[NOT TESTED] WildcardUdpPortList: Wildcardudpportlist"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("NetPortHeader")
    def extract_netportheader(self, node) -> SignalResult:
        """[NOT TESTED] NetPortHeader: Netportheader"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("NonAnsiPortList")
    def extract_nonansiportlist(self, node) -> SignalResult:
        """[NOT TESTED] NonAnsiPortList: Nonansiportlist"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("NonAnsiUdpPortList")
    def extract_nonansiudpportlist(self, node) -> SignalResult:
        """[NOT TESTED] NonAnsiUdpPortList: Nonansiudpportlist"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("AnsiPortList")
    def extract_ansiportlist(self, node) -> SignalResult:
        """[NOT TESTED] AnsiPortList: Ansiportlist"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("AnsiUdpPortList")
    def extract_ansiudpportlist(self, node) -> SignalResult:
        """[NOT TESTED] AnsiUdpPortList: Ansiudpportlist"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result
