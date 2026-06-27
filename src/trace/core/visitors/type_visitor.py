"""[ADD 2026-06-27 A-PR8] Type visitor mixin for SignalExpressionVisitor.

[REFACTOR A-PR8 2026-06-27] 抽 29 @on handler 涵盖 type/literal/dimension
到独立 mixin.

主 class SignalExpressionVisitor 多继承此 mixin, 改 1 行平均 5 min → 30s.

Handler 类别:
- Numeric: BitType/ByteType/LogicType/IntType/LongIntType/ShortIntType/IntegerType/RegType
- Float: RealType/ShortRealType/RealTimeType/TimeType
- String/Char: StringType/CHandleType/VoidType
- Composite: StructType/UnionType/EnumType/SequenceType/VirtualInterfaceType
- Reference: TypeReference/EmptyArgument/NamedType/ImplicitType/EqualsTypeClause
- Dimension: WildcardDimensionSpecifier
- Directive: DefaultNetTypeDirective/ForwardTypeRestriction
- Misc: AnonymousProgram/Untyped

Total: 29 @on handler (~232 行, 5-11 行 boilerplate each)
"""
from typing import TYPE_CHECKING

from ._decorators import on
from .signal_result import SignalResult

if TYPE_CHECKING:
    from .signal_expression_visitor import SignalExpressionVisitor


class TypeVisitor:
    """[ADD 2026-06-27 A-PR8] 抽所有 type/literal/dimension @on handler 到独立 mixin.

    主 class SignalExpressionVisitor 多继承此 mixin, 行为不变.
    """

    @on("EmptyArgument")
    def extract_empty_argument(self, node) -> SignalResult:
        """[NOT TESTED] EmptyArgument: 函数参数占位"""
        return SignalResult()

    @on("TypeReference")
    def extract_type_reference(self, node) -> SignalResult:
        """[NOT TESTED] TypeReference: 类型引用"""
        return SignalResult()

    @on("BitType")
    def extract_bit_type(self, node) -> SignalResult:
        """[NOT TESTED] BitType: bit type"""
        return SignalResult()

    @on("ByteType")
    def extract_byte_type(self, node) -> SignalResult:
        """[NOT TESTED] ByteType: byte type"""
        return SignalResult()

    @on("CHandleType")
    def extract_chandle_type(self, node) -> SignalResult:
        """[NOT TESTED] CHandleType: chandle type"""
        return SignalResult()

    @on("IntType")
    def extract_int_type(self, node) -> SignalResult:
        """[NOT TESTED] IntType: int type"""
        return SignalResult()

    @on("LongIntType")
    def extract_long_int_type(self, node) -> SignalResult:
        """[NOT TESTED] LongIntType: longint type"""
        return SignalResult()

    @on("ShortIntType")
    def extract_short_int_type(self, node) -> SignalResult:
        """[NOT TESTED] ShortIntType: shortint type"""
        return SignalResult()

    @on("IntegerType")
    def extract_integer_type(self, node) -> SignalResult:
        """[NOT TESTED] IntegerType: integer type"""
        return SignalResult()

    @on("LogicType")
    def extract_logic_type(self, node) -> SignalResult:
        """[NOT TESTED] LogicType: logic type"""
        return SignalResult()

    @on("RegType")
    def extract_reg_type(self, node) -> SignalResult:
        """[NOT TESTED] RegType: reg type"""
        return SignalResult()

    @on("StringType")
    def extract_string_type(self, node) -> SignalResult:
        """[NOT TESTED] StringType: string type"""
        return SignalResult()

    @on("VoidType")
    def extract_void_type(self, node) -> SignalResult:
        """[NOT TESTED] VoidType: void type"""
        return SignalResult()

    @on("RealType")
    def extract_real_type(self, node) -> SignalResult:
        """[NOT TESTED] RealType: real type"""
        return SignalResult()

    @on("ShortRealType")
    def extract_short_real_type(self, node) -> SignalResult:
        """[NOT TESTED] ShortRealType: shortreal type"""
        return SignalResult()

    @on("SequenceType")
    def extract_sequence_type(self, node) -> SignalResult:
        """[NOT TESTED] SequenceType: sequence type"""
        return SignalResult()

    # Statement-related
    @on("AnonymousProgram")
    def extract_anonymous_program(self, node) -> SignalResult:
        """[NOT TESTED] AnonymousProgram: anonymous program"""
        return SignalResult()

    # Extern interface method
    @on("EqualsTypeClause")
    def extract_equals_type_clause(self, node) -> SignalResult:
        """[NOT TESTED] EqualsTypeClause: equals type clause"""
        result = SignalResult()
        items = getattr(node, "items", None) or getattr(node, "type", None)
        if items and hasattr(items, "__iter__"):
            for item in items:
                if item:
                    result = result.merge(self.extract(item))
        return result

    @on("VirtualInterfaceType")
    def extract_virtual_interface_type(self, node) -> SignalResult:
        """[NOT TESTED] VirtualInterfaceType: virtual interface type"""
        return SignalResult()

    @on("UnionType")
    def extract_uniontype(self, node) -> SignalResult:
        """[NOT TESTED] UnionType: Uniontype"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("WildcardDimensionSpecifier")
    def extract_wildcarddimensionspecifier(self, node) -> SignalResult:
        """[NOT TESTED] WildcardDimensionSpecifier: Wildcarddimensionspecifier"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("StructType")
    def extract_structtype(self, node) -> SignalResult:
        """[NOT TESTED] StructType: Structtype"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("TimeType")
    def extract_timetype(self, node) -> SignalResult:
        """[NOT TESTED] TimeType: Timetype"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("RealTimeType")
    def extract_realtimetype(self, node) -> SignalResult:
        """[NOT TESTED] RealTimeType: Realtimetype"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("ImplicitType")
    def extract_implicittype(self, node) -> SignalResult:
        """[NOT TESTED] ImplicitType: Implicittype"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("EnumType")
    def extract_enumtype(self, node) -> SignalResult:
        """[NOT TESTED] EnumType: Enumtype"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("ForwardTypeRestriction")
    def extract_forwardtyperestriction(self, node) -> SignalResult:
        """[NOT TESTED] ForwardTypeRestriction: Forwardtyperestriction"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("DefaultNetTypeDirective")
    def extract_defaultnettypedirective(self, node) -> SignalResult:
        """[NOT TESTED] DefaultNetTypeDirective: Defaultnettypedirective"""
        result = SignalResult()
        # Extract signals from children
        children = getattr(node, "items", None) or getattr(node, "elements", None) or getattr(node, "members", None)
        if children:
            for child in children:
                if child:
                    result = result.merge(self.extract(child))
        return result

    @on("NamedType")
    def extract_named_type(self, node) -> SignalResult:
        """[NOT TESTED] NamedType: named type"""
        result = SignalResult()
        name = getattr(node, "name", None)
        if name:
            result.add_signal(str(name))
        return result
