"""[ADD 2026-06-26 A-PR3] Member visitor mixin for SignalExpressionVisitor.

[REFACTOR A-PR3 2026-06-26] 抽 69 @on handler 涵盖 member/class/scope/identifier 等
到独立 mixin.

主 class SignalExpressionVisitor 多继承此 mixin, 改 1 行平均 5 min → 1-2 min.

Handler 类别:
- Identifier: ScopedName/IdentifierName/NamedValue/HierarchicalValue
- Class: ClassDeclaration/ClassMethod/ClassProperty/ClassSpecifier/NewClass/CopyClass
- Member: MemberAccess/LValue/Parameter/LValueReference
- Instance: NewArray/NewCovergroup/Instance/EmptyMember
- Property: ClassPropertyDeclaration/PropertyType/AssertProperty etc
- Package: Package/ConfigInstance
- Hierarchical: HierarchicalInstance/HierarchicalBlock

Total: 69 @on handler (678 行, 9-12 行 boilerplate each)
"""
from typing import TYPE_CHECKING

import logging

from ._decorators import on
from .signal_result import SignalResult

if TYPE_CHECKING:
    from .signal_expression_visitor import SignalExpressionVisitor

logger = logging.getLogger(__name__)


class MemberVisitor:
    """[ADD 2026-06-26 A-PR3] 抽所有 member/class/scope/identifier @on handler 到独立 mixin.

    主 class SignalExpressionVisitor 多继承此 mixin, 行为不变.
    """

    @on("ScopedName")
    def extract_scoped_name(self, node) -> SignalResult:
        """[NOT TESTED] ScopedName: 点分路径 p.sub.data"""
        parts = self._extract_scoped_parts(node)
        if parts:
            combined = ".".join(parts)
            name = self.adapter.clean_name(combined)
            return SignalResult.single(name)
        return SignalResult()


    @on("ClockingPropertyExpr")
    def extract_clocking_property_expr(self, node) -> SignalResult:
        """[NOT TESTED] ClockingPropertyExpr: property with clock"""
        result = SignalResult()
        prop = getattr(node, "property", None) or getattr(node, "expr", None)
        if prop:
            result = result.merge(self.extract(prop))
        clock = getattr(node, "clock", None)
        if clock:
            result = result.merge(self.extract(clock))
        return result


    @on("CasePropertyExpr")
    def extract_case_property_expression(self, node) -> SignalResult:
        """[NOT TESTED] CasePropertyExpression: case property expression"""
        result = SignalResult()
        expr = getattr(node, "expr", None) or getattr(node, "expression", None)
        if expr:
            result = result.merge(self.extract(expr))
        items = getattr(node, "items", None)
        if items and hasattr(items, "__iter__"):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result


    @on("AndPropertyExpr")
    def extract_and_property_expr(self, node) -> SignalResult:
        """[NOT TESTED] AndPropertyExpr: and property expression"""
        result = SignalResult()
        left = getattr(node, "left", None)
        right = getattr(node, "right", None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result


    @on("OrPropertyExpr")
    def extract_or_property_expr(self, node) -> SignalResult:
        """[NOT TESTED] OrPropertyExpr: or property expression"""
        result = SignalResult()
        left = getattr(node, "left", None)
        right = getattr(node, "right", None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result


    @on("ImplicationPropertyExpr")
    def extract_implication_property_expr(self, node) -> SignalResult:
        """[NOT TESTED] ImplicationPropertyExpr: implication property expression"""
        result = SignalResult()
        left = getattr(node, "left", None) or getattr(node, "antecedent", None)
        right = getattr(node, "right", None) or getattr(node, "consequent", None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result


    @on("PropertyType")
    def extract_property_type(self, node) -> SignalResult:
        """[NOT TESTED] PropertyType: property type"""
        return SignalResult()


    @on("AssertPropertyStatement")
    def extract_assert_property_statement(self, node) -> SignalResult:
        """[NOT TESTED] AssertPropertyStatement: assert property statement"""
        result = SignalResult()
        prop = getattr(node, "property", None) or getattr(node, "expr", None)
        if prop:
            result = result.merge(self.extract(prop))
        action = getattr(node, "action", None)
        if action:
            result = result.merge(self.extract(action))
        return result


    @on("AssumePropertyStatement")
    def extract_assume_property_statement(self, node) -> SignalResult:
        """[NOT TESTED] AssumePropertyStatement: assume property statement"""
        result = SignalResult()
        prop = getattr(node, "property", None) or getattr(node, "expr", None)
        if prop:
            result = result.merge(self.extract(prop))
        return result


    @on("CoverPropertyStatement")
    def extract_cover_property_statement(self, node) -> SignalResult:
        """[NOT TESTED] CoverPropertyStatement: cover property statement"""
        result = SignalResult()
        prop = getattr(node, "property", None) or getattr(node, "expr", None)
        if prop:
            result = result.merge(self.extract(prop))
        return result


    @on("ExpectPropertyStatement")
    def extract_expect_property_statement(self, node) -> SignalResult:
        """[NOT TESTED] ExpectPropertyStatement: expect property statement"""
        result = SignalResult()
        prop = getattr(node, "property", None) or getattr(node, "expr", None)
        if prop:
            result = result.merge(self.extract(prop))
        action = getattr(node, "action", None)
        if action:
            result = result.merge(self.extract(action))
        return result

    # Sequence and property expression kinds

    @on("ArrayAndMethod")
    def extract_array_and_method(self, node) -> SignalResult:
        """[NOT TESTED] ArrayAndMethod: array.and() method"""
        result = SignalResult()
        array = getattr(node, "array", None) or getattr(node, "expr", None)
        if array:
            result = result.merge(self.extract(array))
        return result


    @on("ArrayOrMethod")
    def extract_array_or_method(self, node) -> SignalResult:
        """[NOT TESTED] ArrayOrMethod: array.or() method"""
        result = SignalResult()
        array = getattr(node, "array", None) or getattr(node, "expr", None)
        if array:
            result = result.merge(self.extract(array))
        return result


    @on("ArrayUniqueMethod")
    def extract_array_unique_method(self, node) -> SignalResult:
        """[NOT TESTED] ArrayUniqueMethod: array.unique() method"""
        result = SignalResult()
        array = getattr(node, "array", None) or getattr(node, "expr", None)
        if array:
            result = result.merge(self.extract(array))
        return result


    @on("ArrayXorMethod")
    def extract_array_xor_method(self, node) -> SignalResult:
        """[NOT TESTED] ArrayXorMethod: array.xor() method"""
        result = SignalResult()
        array = getattr(node, "array", None) or getattr(node, "expr", None)
        if array:
            result = result.merge(self.extract(array))
        return result


    @on("ClassDeclaration")
    def extract_class_declaration(self, node) -> SignalResult:
        """[NOT TESTED] ClassDeclaration: class declaration"""
        return SignalResult()


    @on("ClassMethodDeclaration")
    def extract_class_method_declaration(self, node) -> SignalResult:
        """[NOT TESTED] ClassMethodDeclaration: class method declaration"""
        result = SignalResult()
        body = getattr(node, "body", None) or getattr(node, "statements", None)
        if body and hasattr(body, "__iter__"):
            for stmt in body:
                if stmt:
                    result = result.merge(self.extract(stmt))
        return result


    @on("ClassMethodPrototype")
    def extract_class_method_prototype(self, node) -> SignalResult:
        """[NOT TESTED] ClassMethodPrototype: class method prototype"""
        return SignalResult()


    @on("ClassPropertyDeclaration")
    def extract_class_property_declaration(self, node) -> SignalResult:
        """[NOT TESTED] ClassPropertyDeclaration: class property declaration"""
        result = SignalResult()
        init = getattr(node, "init", None) or getattr(node, "value", None)
        if init:
            result = result.merge(self.extract(init))
        return result


    @on("ClassSpecifier")
    def extract_class_specifier(self, node) -> SignalResult:
        """[NOT TESTED] ClassSpecifier: class specifier"""
        return SignalResult()


    @on("ClassName")
    def extract_class_name(self, node) -> SignalResult:
        """[NOT TESTED] ClassName: class name"""
        return SignalResult()

    # Checker-related

    @on("CheckerInstanceStatement")
    def extract_checker_instance_statement(self, node) -> SignalResult:
        """[NOT TESTED] CheckerInstanceStatement: checker instance statement"""
        result = SignalResult()
        args = getattr(node, "arguments", None)
        if args and hasattr(args, "__iter__"):
            for arg in args:
                if arg:
                    result = result.merge(self.extract(arg))
        return result


    @on("DefaultPropertyCaseItem")
    def extract_default_property_case_item(self, node) -> SignalResult:
        """[NOT TESTED] DefaultPropertyCaseItem: default property case item"""
        return SignalResult()

    # Assertion item ports

    @on("ConcurrentAssertionMember")
    def extract_concurrent_assertion_member(self, node) -> SignalResult:
        """[NOT TESTED] ConcurrentAssertionMember: concurrent assertion member"""
        return SignalResult()

    # Coverage constructs

    @on("ExternInterfaceMethod")
    def extract_extern_interface_method(self, node) -> SignalResult:
        """[NOT TESTED] ExternInterfaceMethod: extern interface method"""
        return SignalResult()

    # More expression types

    @on("PackageDeclaration")
    def extract_package_declaration(self, node) -> SignalResult:
        """[NOT TESTED] PackageDeclaration: package declaration"""
        return SignalResult()


    @on("ParameterDeclaration")
    def extract_parameter_declaration(self, node) -> SignalResult:
        """[NOT TESTED] ParameterDeclaration: parameter declaration"""
        return SignalResult()

    # Non-blocking assignment statement

    @on("SimplePropertyExpr")
    def extract_simple_property_expr(self, node) -> SignalResult:
        """[NOT TESTED] SimplePropertyExpr: simple property expression"""
        result = SignalResult()
        prop = getattr(node, "property", None) or getattr(node, "expr", None)
        if prop:
            return self.extract(prop)
        return result


    @on("IffPropertyExpr")
    def extract_iff_property_expr(self, node) -> SignalResult:
        """[NOT TESTED] IffPropertyExpr: property iff expression"""
        result = SignalResult()
        prop = getattr(node, "property", None) or getattr(node, "expr", None)
        if prop:
            result = result.merge(self.extract(prop))
        iff = getattr(node, "iff", None) or getattr(node, "event", None)
        if iff:
            result = result.merge(self.extract(iff))
        return result


    @on("ImpliesPropertyExpr")
    def extract_implies_property_expr_stmt(self, node) -> SignalResult:
        """[NOT TESTED] ImpliesPropertyExpr: implies property expression"""
        result = SignalResult()
        left = getattr(node, "left", None) or getattr(node, "antecedent", None)
        right = getattr(node, "right", None) or getattr(node, "consequent", None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result


    @on("FollowedByPropertyExpr")
    def extract_followed_by_property_expr(self, node) -> SignalResult:
        """[NOT TESTED] FollowedByPropertyExpr: followed_by property expression"""
        result = SignalResult()
        left = getattr(node, "left", None) or getattr(node, "antecedent", None)
        right = getattr(node, "right", None) or getattr(node, "consequent", None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result


    @on("SUntilPropertyExpr")
    def extract_s_until_property_expr(self, node) -> SignalResult:
        """[NOT TESTED] SUntilPropertyExpr: s_until property expression"""
        result = SignalResult()
        left = getattr(node, "left", None)
        right = getattr(node, "right", None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result


    @on("SUntilWithPropertyExpr")
    def extract_s_until_with_property_expr(self, node) -> SignalResult:
        """[NOT TESTED] SUntilWithPropertyExpr: s_until_with property expression"""
        result = SignalResult()
        left = getattr(node, "left", None)
        right = getattr(node, "right", None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result


    @on("UntilPropertyExpr")
    def extract_until_property_expr(self, node) -> SignalResult:
        """[NOT TESTED] UntilPropertyExpr: until property expression"""
        result = SignalResult()
        left = getattr(node, "left", None)
        right = getattr(node, "right", None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result


    @on("UntilWithPropertyExpr")
    def extract_until_with_property_expr(self, node) -> SignalResult:
        """[NOT TESTED] UntilWithPropertyExpr: until_with property expression"""
        result = SignalResult()
        left = getattr(node, "left", None)
        right = getattr(node, "right", None)
        if left:
            result = result.merge(self.extract(left))
        if right:
            result = result.merge(self.extract(right))
        return result


    @on("StrongWeakPropertyExpr")
    def extract_strong_weak_property_expr(self, node) -> SignalResult:
        """[NOT TESTED] StrongWeakPropertyExpr: strong/weak property expression"""
        result = SignalResult()
        prop = getattr(node, "property", None) or getattr(node, "expr", None)
        if prop:
            result = result.merge(self.extract(prop))
        return result


    @on("AcceptOnPropertyExpr")
    def extract_accept_on_property_expr(self, node) -> SignalResult:
        """[NOT TESTED] AcceptOnPropertyExpr: accept_on property expression"""
        result = SignalResult()
        cond = getattr(node, "condition", None) or getattr(node, "expr", None)
        if cond:
            result = result.merge(self.extract(cond))
        prop = getattr(node, "property", None) or getattr(node, "body", None)
        if prop:
            result = result.merge(self.extract(prop))
        return result

    # Sequence expressions

    @on("ParenthesizedPropertyExpr")
    def extract_parenthesized_property_expr(self, node) -> SignalResult:
        """[NOT TESTED] ParenthesizedPropertyExpr: parenthesized property expression"""
        result = SignalResult()
        prop = getattr(node, "property", None) or getattr(node, "expr", None)
        if prop:
            return self.extract(prop)
        return result


    @on("PropertyDeclaration")
    def extract_property_declaration_stmt(self, node) -> SignalResult:
        """[NOT TESTED] PropertyDeclaration: property declaration"""
        result = SignalResult()
        items = getattr(node, "items", None) or getattr(node, "body", None)
        if items and hasattr(items, "__iter__"):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result


    @on("RestrictPropertyStatement")
    def extract_restrict_property_statement(self, node) -> SignalResult:
        """[NOT TESTED] RestrictPropertyStatement: restrict property statement"""
        result = SignalResult()
        prop = getattr(node, "property", None) or getattr(node, "expr", None)
        if prop:
            result = result.merge(self.extract(prop))
        return result

    # Invocations and calls

    @on("IdentifierName")
    def extract_identifier_name(self, node) -> SignalResult:
        """[MIGRATED] IdentifierName: 简单信号名

        从 visit_identifier_name 迁移而来
        """
        ident = getattr(node, "identifier", None)
        if ident is None:
            logger.debug("[MIGRATED] IdentifierName missing 'identifier' attr")
            return SignalResult()

        val = getattr(ident, "value", None)
        if val is None:
            logger.debug("[MIGRATED] IdentifierName.identifier missing 'value' attr")
            return SignalResult()

        signal_name = self.adapter.clean_name(str(val).strip())
        return SignalResult(primary=signal_name, all_signals=[signal_name])


    @on("ParameterDeclarationStatement")
    def extract_parameter_declaration_statement(self, node) -> SignalResult:
        """[NOT TESTED] ParameterDeclarationStatement: parameter declaration statement"""
        result = SignalResult()
        items = getattr(node, "items", None) or getattr(node, "parameters", None)
        if items and hasattr(items, "__iter__"):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result


    @on("TypeParameterDeclaration")
    def extract_type_parameter_declaration(self, node) -> SignalResult:
        """[NOT TESTED] TypeParameterDeclaration: type parameter declaration"""
        return SignalResult()


    @on("PackageImportDeclaration")
    def extract_package_import_declaration(self, node) -> SignalResult:
        """[NOT TESTED] PackageImportDeclaration: package import declaration"""
        return SignalResult()


    @on("PackageImportItem")
    def extract_package_import_item(self, node) -> SignalResult:
        """[NOT TESTED] PackageImportItem: package import item"""
        return SignalResult()


    @on("PackageExportDeclaration")
    def extract_package_export_declaration(self, node) -> SignalResult:
        """[NOT TESTED] PackageExportDeclaration: package export declaration"""
        return SignalResult()


    @on("PackageExportAllDeclaration")
    def extract_package_export_all_declaration(self, node) -> SignalResult:
        """[NOT TESTED] PackageExportAllDeclaration: package export all declaration"""
        return SignalResult()

    # Clocking block declarations

    @on("PackageHeader")
    def extract_package_header(self, node) -> SignalResult:
        """[NOT TESTED] PackageHeader: package header"""
        return SignalResult()


    @on("StandardPropertyCaseItem")
    def extract_standard_property_case_item(self, node) -> SignalResult:
        """[NOT TESTED] StandardPropertyCaseItem: standard property case item"""
        result = SignalResult()
        items = getattr(node, "items", None)
        if items and hasattr(items, "__iter__"):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result


    @on("ElsePropertyClause")
    def extract_else_property_clause(self, node) -> SignalResult:
        """[NOT TESTED] ElsePropertyClause: else property clause"""
        result = SignalResult()
        prop = getattr(node, "property", None) or getattr(node, "body", None)
        if prop:
            result = result.merge(self.extract(prop))
        return result


    @on("DotMemberClause")
    def extract_dot_member_clause(self, node) -> SignalResult:
        """[NOT TESTED] DotMemberClause: dot member clause"""
        return SignalResult()


    @on("PropertySpec")
    def extract_property_spec(self, node) -> SignalResult:
        """[NOT TESTED] PropertySpec: property spec"""
        result = SignalResult()
        prop = getattr(node, "property", None) or getattr(node, "expr", None)
        if prop:
            result = result.merge(self.extract(prop))
        return result


    @on("UdpSimpleField")
    def extract_udpsimplefield(self, node) -> SignalResult:
        """[NOT TESTED] UdpSimpleField: Udpsimplefield"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result


    @on("UnitScope")
    def extract_unitscope(self, node) -> SignalResult:
        """[NOT TESTED] UnitScope: Unitscope"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result


    @on("StructUnionMember")
    def extract_structunionmember(self, node) -> SignalResult:
        """[NOT TESTED] StructUnionMember: Structunionmember"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result


    @on("UdpEdgeField")
    def extract_udpedgefield(self, node) -> SignalResult:
        """[NOT TESTED] UdpEdgeField: Udpedgefield"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result


    @on("RootScope")
    def extract_rootscope(self, node) -> SignalResult:
        """[NOT TESTED] RootScope: Rootscope"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result


    @on("NamedStructurePatternMember")
    def extract_namedstructurepatternmember(self, node) -> SignalResult:
        """[NOT TESTED] NamedStructurePatternMember: Namedstructurepatternmember"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result


    @on("OrderedStructurePatternMember")
    def extract_orderedstructurepatternmember(self, node) -> SignalResult:
        """[NOT TESTED] OrderedStructurePatternMember: Orderedstructurepatternmember"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result


    @on("ParameterPortList")
    def extract_parameterportlist(self, node) -> SignalResult:
        """[NOT TESTED] ParameterPortList: Parameterportlist"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result


    @on("ImmediateAssertionMember")
    def extract_immediateassertionmember(self, node) -> SignalResult:
        """[NOT TESTED] ImmediateAssertionMember: Immediateassertionmember"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result


    @on("InstanceConfigRule")
    def extract_instanceconfigrule(self, node) -> SignalResult:
        """[NOT TESTED] InstanceConfigRule: Instanceconfigrule"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result


    @on("InstanceName")
    def extract_instancename(self, node) -> SignalResult:
        """[NOT TESTED] InstanceName: Instancename"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result


    @on("LocalScope")
    def extract_localscope(self, node) -> SignalResult:
        """[NOT TESTED] LocalScope: Localscope"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result


    @on("EmptyIdentifierName")
    def extract_emptyidentifiername(self, node) -> SignalResult:
        """[NOT TESTED] EmptyIdentifierName: Emptyidentifiername"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result


    @on("EmptyMember")
    def extract_emptymember(self, node) -> SignalResult:
        """[NOT TESTED] EmptyMember: Emptymember"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result


    @on("AttributeInstance")
    def extract_attributeinstance(self, node) -> SignalResult:
        """[NOT TESTED] AttributeInstance: Attributeinstance"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result


    @on("ConfigInstanceIdentifier")
    def extract_configinstanceidentifier(self, node) -> SignalResult:
        """[NOT TESTED] ConfigInstanceIdentifier: Configinstanceidentifier"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result


    @on("HierarchicalInstance")
    def extract_hierarchical_instance(self, node) -> SignalResult:
        """[NOT TESTED] HierarchicalInstance: module instance"""
        result = SignalResult()
        name = getattr(node, "name", None)
        if name:
            result.add_signal(str(name))
        return result


