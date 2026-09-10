# test_expr_signal_helpers.py - 表达式信号抽取 helpers (iter_174 Step 3)
# 方豆 "拆 semantic" — 原 `_extract_signals_from_expr` 474 行 → 分派器 + 16 个
# 分支处理器 + `_fold_select_index`.
#
# 本文件两件事:
#  1. 锁定 hoisted helper `_fold_select_index` 的行为 — 它原本是**死分支内的
#     嵌套 def** 却被活分支 (ElementSelect/RangeSelect 的非字面量 selector 路径)
#     调用: 由于 Python 帧局部作用域, 该路径原本会 UnboundLocalError
#     (latent bug)。Step 3 提到模块级后行为可测 — 此处补测试。
#  2. 通过一个轻量 fake AST 锁定分派器对每类 kind 的**信号抽取结果**
#     (搬迁后行为不变的回归网; 真实语义用例见 truth/driver 套件)。
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

from trace.core.semantic_adapter import (  # noqa: E402
    SemanticAdapter,
    _fold_select_index,
)


class FakeNode:
    """最小语义/语法节点替身: 只需 kind + 属性 (helper 全走 getattr)."""

    def __init__(self, kind, **attrs):
        self.kind = kind
        for k, v in attrs.items():
            setattr(self, k, v)


class FakeValue:
    """constant/value 包装 (ConstantValue.integer 语义)."""

    def __init__(self, integer):
        self.integer = integer


class FakeSymbol:
    def __init__(self, name):
        self.name = name


class TestFoldSelectIndex(unittest.TestCase):
    """[Step 3] genvar ctx 索引折叠 (原为死分支内嵌套 def → 不可达)"""

    def test_literal(self):
        n = FakeNode("Literal", constant=FakeValue(3))
        self.assertEqual(_fold_select_index(n, {}), 3)

    def test_named_value_from_ctx(self):
        n = FakeNode("NamedValue", symbol=FakeSymbol("i"))
        self.assertEqual(_fold_select_index(n, {"i": 2}), 2)

    def test_named_value_not_in_ctx(self):
        n = FakeNode("NamedValue", symbol=FakeSymbol("j"))
        self.assertIsNone(_fold_select_index(n, {"i": 2}))

    def test_binary_add_sub_mul(self):
        def mk(op, l, r):
            # 真实语义 op 是枚举 (有 .name, 如 'Add'/'Subtract')
            return FakeNode("BinaryOp", op=FakeNode("Token", name=op), left=l, right=r)
        one = FakeNode("Literal", constant=FakeValue(1))
        i = FakeNode("NamedValue", symbol=FakeSymbol("i"))
        self.assertEqual(_fold_select_index(mk("Add", i, one), {"i": 2}), 3)
        self.assertEqual(_fold_select_index(mk("Subtract", i, one), {"i": 2}), 1)
        self.assertEqual(_fold_select_index(mk("Multiply", i, one), {"i": 2}), 2)

    def test_conversion_unwrap(self):
        inner = FakeNode("Literal", constant=FakeValue(5))
        n = FakeNode("Conversion", operand=inner)
        self.assertEqual(_fold_select_index(n, {}), 5)

    def test_none_and_unknown(self):
        self.assertIsNone(_fold_select_index(None, {}))
        self.assertIsNone(_fold_select_index(FakeNode("SomethingElse"), {}))


class TestDispatcherResultShape(unittest.TestCase):
    """[Step 3] 分派器: 每类 kind 的抽取结果 (搬迁后不变)"""

    @classmethod
    def setUpClass(cls):
        # adapter 只需要能承载 getattr 递归 (不触碰编译器状态)
        cls.ad = SemanticAdapter.__new__(SemanticAdapter)

    def _extract(self, expr, ctx=None):
        return self.ad._extract_signals_from_expr(expr, ctx)

    def test_unknown_kind_returns_empty_list_not_none(self):
        """未覆盖 kind → [] (原实现在末尾 return signals; 拆分时曾漏掉)"""
        r = self._extract(FakeNode("SomeUnknownKind"))
        self.assertEqual(r, [])
        self.assertIsInstance(r, list)

    def test_none_and_no_kind(self):
        self.assertEqual(self._extract(None), [])
        self.assertEqual(self._extract(FakeNode("")), [])

    def test_named_value(self):
        n = FakeNode("NamedValue", symbol=FakeSymbol("data"))
        self.assertEqual(self._extract(n), ["data"])

    def test_identifier_name_syntax(self):
        n = FakeNode("IdentifierName", identifier=FakeNode("Token", value="sig"))
        self.assertEqual(self._extract(n), ["sig"])

    def test_integer_literal_not_signal(self):
        self.assertEqual(self._extract(FakeNode("IntegerLiteral")), [])

    def test_binary_recurses_both_sides(self):
        a = FakeNode("NamedValue", symbol=FakeSymbol("a"))
        b = FakeNode("NamedValue", symbol=FakeSymbol("b"))
        n = FakeNode("BinaryOp", left=a, right=b)
        self.assertEqual(sorted(self._extract(n)), ["a", "b"])

    def test_unary_recurses(self):
        a = FakeNode("NamedValue", symbol=FakeSymbol("a"))
        n = FakeNode("UnaryOp", operand=a)
        self.assertEqual(self._extract(n), ["a"])

    def test_conversion_unwraps_operand(self):
        a = FakeNode("NamedValue", symbol=FakeSymbol("a"))
        n = FakeNode("Conversion", operand=a)
        self.assertEqual(self._extract(n), ["a"])

    def test_conversion_skips_literal(self):
        lit = FakeNode("IntegerLiteral")
        n = FakeNode("Conversion", operand=lit)
        self.assertEqual(self._extract(n), [])


if __name__ == '__main__':
    unittest.main()
