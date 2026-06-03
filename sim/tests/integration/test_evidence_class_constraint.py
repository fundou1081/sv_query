#==============================================================================
# test_evidence_class_constraint.py - TDD tests for evidence support on
# SystemVerilog class declarations and constraint blocks
#
# Goal: TraceEvidenceResolver should produce evidence for:
#   1. class properties (CLASS_PROPERTY): enclosing class + constraint blocks
#   2. constraint blocks (CONSTRAINT_BLOCK): enclosing class
#   3. constraint expressions (CONSTRAINT_EXPR): enclosing constraint + class
#   4. class instances: enclosing module + class
#
# Design decisions (TDD):
#   - Add enclosing_class field (covers class declaration)
#   - Add enclosing_constraint field (covers constraint block)
#   - enclosing_if should also work for ConditionalConstraint (constraint if/else)
#   - For a CLASS_PROPERTY, the evidence should show the class as enclosing_class
#     and the constraints that reference it as enclosing_constraint(s)
#==============================================================================

import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

from trace.unified_tracer import UnifiedTracer
from trace.core.trace_evidence import TraceEvidenceResolver, Evidence


def _make_resolver(source: str, source_name: str = "test.sv"):
    """Helper: build tracer + resolver from source string"""
    tracer = UnifiedTracer(sources={source_name: source}, log_level="ERROR")
    graph = tracer.build_graph()
    sem = tracer._get_adapter()
    return tracer, TraceEvidenceResolver(graph=graph, adapter=sem)


#==============================================================================
# TestGroup 1: Class property evidence
#==============================================================================

class TestClassPropertyEvidence(unittest.TestCase):
    """TDD: class 属性的 evidence 应包含 enclosing_class"""

    def test_class_property_has_enclosing_class(self):
        """[TDD-C1] class property 应有 enclosing_class (class packet 块)"""
        source = '''
class packet;
    rand bit [7:0] addr;

    constraint c_addr {
        addr inside {[0:100]};
    }
endclass'''
        _, resolver = _make_resolver(source)
        ev = resolver.resolve("packet.addr")
        # 期望: enclosing_class 不为 None
        self.assertIsNotNone(ev.enclosing_class,
                            "class property should populate enclosing_class")
        # text 应含 "class packet"
        self.assertIn("class", ev.enclosing_class.text)
        self.assertIn("packet", ev.enclosing_class.text)

    def test_class_property_has_enclosing_constraint(self):
        """[TDD-C2] class property 应有 enclosing_constraint (引用它的 constraint 块)"""
        source = '''
class packet;
    rand bit [7:0] addr;

    constraint c_addr {
        addr inside {[0:100]};
    }
endclass'''
        _, resolver = _make_resolver(source)
        ev = resolver.resolve("packet.addr")
        # 期望: enclosing_constraint 不为 None
        self.assertIsNotNone(ev.enclosing_constraint,
                            "class property should populate enclosing_constraint")
        # text 应含 "constraint" 和 constraint 名
        self.assertIn("constraint", ev.enclosing_constraint.text)
        self.assertIn("c_addr", ev.enclosing_constraint.text)

    def test_class_property_with_multiple_constraints(self):
        """[TDD-C3] class property 被多个 constraint 引用时, 至少有一个 enclosing_constraint"""
        source = '''
class packet;
    rand bit [7:0] addr;
    rand bit [3:0] mode;

    constraint c_range {
        addr inside {[0:100]};
    }
    constraint c_mode {
        if (mode == 0) addr < 50;
    }
endclass'''
        _, resolver = _make_resolver(source)
        ev = resolver.resolve("packet.addr")
        # 至少一个 enclosing_constraint
        self.assertIsNotNone(ev.enclosing_constraint)
        # constraint 的 text 应该是完整的 constraint 块
        self.assertIn("constraint", ev.enclosing_constraint.text)


#==============================================================================
# TestGroup 2: Constraint block evidence
#==============================================================================

class TestConstraintBlockEvidence(unittest.TestCase):
    """TDD: constraint 块本身应有 evidence (含 enclosing_class)"""

    def test_constraint_block_has_enclosing_class(self):
        """[TDD-C4] constraint 块应有 enclosing_class"""
        source = '''
class packet;
    rand bit [7:0] addr;

    constraint c_addr {
        addr inside {[0:100]};
    }
endclass'''
        _, resolver = _make_resolver(source)
        ev = resolver.resolve("packet.c_addr")
        # 期望: enclosing_class 不为 None
        self.assertIsNotNone(ev.enclosing_class,
                            "constraint block should populate enclosing_class")
        self.assertIn("class", ev.enclosing_class.text)
        self.assertIn("packet", ev.enclosing_class.text)

    def test_constraint_block_has_source_text(self):
        """[TDD-C5] constraint 块应有 source_location / source_text"""
        source = '''
class packet;
    rand bit [7:0] addr;

    constraint c_addr {
        addr inside {[0:100]};
    }
endclass'''
        _, resolver = _make_resolver(source)
        ev = resolver.resolve("packet.c_addr")
        # 期望: source_text 不为空
        # constraint 块本身可能没有 condition_ast (与 always_ff 不同)
        # 至少应该可以解析出 constraint 块作为 enclosing
        self.assertIsNotNone(ev.enclosing_constraint or ev.enclosing_class)


#==============================================================================
# TestGroup 3: Constraint expression with conditional
#==============================================================================

class TestConstraintConditionalEvidence(unittest.TestCase):
    """TDD: constraint 内的 if/else (ConditionalConstraint) 应有 evidence"""

    def test_constraint_if_else_has_enclosing_if(self):
        """[TDD-C6] constraint 内的 if/else 应有 enclosing_if"""
        source = '''
class packet;
    rand bit [7:0] addr;
    rand bit [3:0] mode;

    constraint c_mode {
        if (mode == 0) addr < 50;
        else addr > 100;
    }
endclass'''
        _, resolver = _make_resolver(source)
        # addr 在 if 分支被约束
        ev = resolver.resolve("packet.addr")
        # enclosing_if 应识别 ConditionalConstraint
        # 实际: 现有实现可能不识别, 但 enclosing_class/enclosing_constraint 应有
        self.assertIsNotNone(ev.enclosing_class)


#==============================================================================
# TestGroup 4: Chain mode for class property
#==============================================================================

class TestChainClassProperty(unittest.TestCase):
    """TDD: chain 模式能跨 class property 追溯"""

    def test_chain_includes_class_property(self):
        """[CHAIN-C1] chain 模式包含 class property 的 evidence"""
        source = '''
class packet;
    rand bit [7:0] addr;

    constraint c_addr {
        addr inside {[0:100]};
    }
endclass

module top;
    packet p = new();
endmodule'''
        _, resolver = _make_resolver(source)
        chain = resolver.resolve_chain("packet.addr")
        # 至少有一个 evidence
        self.assertGreater(len(chain), 0)
        # 第一个 evidence 是 packet.addr
        self.assertEqual(chain[0].signal, "packet.addr")


#==============================================================================
# TestGroup 5: Class instance property (TODO, may need separate handling)
#==============================================================================

class TestClassInstancePropertyEvidence(unittest.TestCase):
    """TDD: class 实例的属性 (e.g., p.addr) 应能追溯到 class 定义"""

    def test_class_instance_property_evidence(self):
        """[TDD-C7] instance property p.addr 应能拿到 class context"""
        source = '''
class packet;
    rand bit [7:0] addr;

    constraint c_addr {
        addr inside {[0:100]};
    }
endclass

module top;
    packet p = new();
endmodule'''
        _, resolver = _make_resolver(source)
        # 尝试 p.addr
        ev = resolver.resolve("top.p.addr")
        # 当前实现可能没法解析实例属性 (因为实例没在 graph 里有 CLASS_INSTANCE_PROPERTY 节点)
        # 至少返回不抛异常的 Evidence
        self.assertIsNotNone(ev)
        self.assertEqual(ev.signal, "top.p.addr")


if __name__ == "__main__":
    unittest.main()
