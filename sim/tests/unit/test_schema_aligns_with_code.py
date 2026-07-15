# test_schema_aligns_with_code.py - [V1 architecture review 2026-07-15]
#
# 守卫: tools/llm_schema.json 的 enum 必须与代码枚举完全对齐.
#
# Background: 旧 schema 把 NodeKind 和 EdgeKind 混在一个 enum, 还包含
#   不存在的值 (CONTROL, UNKNOWN). 这违反铁律4 (模型即契约) + 铁律6 (Schema 宪法).
#
# Per DEVELOPMENT.md:
#   铁律4: 模型即契约
#     ...
#     必须保证 schema 与代码完全对齐.
#
# Per docs/ARCHITECTURE_REVIEW_2026-07-15.md (V1).

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

# Add src/ to path for imports
from trace.core.graph.models import NodeKind as CodeNodeKind, EdgeKind as CodeEdgeKind


REPO_ROOT = os.path.join(os.path.dirname(__file__), '..', '..', '..')
SCHEMA_PATH = os.path.join(REPO_ROOT, 'tools', 'llm_schema.json')


def _load_schema():
    with open(SCHEMA_PATH) as f:
        return json.load(f)


class TestSchemaAlignsWithCode(unittest.TestCase):
    """V1: schema enum 必须与代码 enum 对齐"""

    def test_edgekind_enum_matches_code(self):
        """[V1] EdgeKind enum in schema == EdgeKind values in code"""
        schema = _load_schema()
        if 'EdgeKind' not in schema.get('definitions', {}):
            self.fail("Schema missing EdgeKind definition")
        schema_enum = set(schema['definitions']['EdgeKind']['enum'])
        code_enum = set(k.name for k in CodeEdgeKind)
        self.assertEqual(
            schema_enum, code_enum,
            f"[V1 violation] Schema EdgeKind enum 不匹配代码:\n"
            f"  Schema only: {schema_enum - code_enum}\n"
            f"  Code only:   {code_enum - schema_enum}"
        )

    def test_nodekind_enum_matches_code(self):
        """[V1] NodeKind enum in schema == NodeKind values in code"""
        schema = _load_schema()
        if 'NodeKind' not in schema.get('definitions', {}):
            self.fail("Schema missing NodeKind definition "
                      "(V1 fix should add it)")
        schema_enum = set(schema['definitions']['NodeKind']['enum'])
        code_enum = set(k.name for k in CodeNodeKind)
        self.assertEqual(
            schema_enum, code_enum,
            f"[V1 violation] Schema NodeKind enum 不匹配代码:\n"
            f"  Schema only: {schema_enum - code_enum}\n"
            f"  Code only:   {code_enum - schema_enum}"
        )

    def test_no_unknown_or_control_in_schema(self):
        """[V1] 旧 schema 的伪 enum 值 (CONTROL, UNKNOWN) 必须被清除"""
        schema = _load_schema()
        for def_name, defn in schema.get('definitions', {}).items():
            if defn.get('type') == 'string' and 'enum' in defn:
                enum_values = set(defn['enum'])
                forbidden = {'CONTROL', 'UNKNOWN'}
                present = enum_values & forbidden
                self.assertEqual(
                    present, set(),
                    f"[V1 violation] Schema definition '{def_name}' 仍含"
                    f"已删除的 enum 值: {present}. 应移除 (V1 fix)."
                )

    def test_edgekind_only_references_in_edges_context(self):
        """[V1] trace_fanin/fanout 不应再用 EdgeKind 当 kind 标签

        drivers[]/loads[] 引用 TraceNode (NodeKind), 不是 TraceEdge (EdgeKind).
        所以 schema 中 drivers[].kind 应该是 NodeKind 引用, 不是 EdgeKind.
        """
        schema = _load_schema()
        # Check commands.trace_fanin
        fanin_kind = (
            schema.get('commands', {})
            .get('trace_fanin', {})
            .get('result_schema', {})
            .get('properties', {})
            .get('signals', {})
            .get('items', {})
            .get('properties', {})
            .get('drivers', {})
            .get('items', {})
            .get('properties', {})
            .get('kind', {})
        )
        ref = fanin_kind.get('$ref', '')
        self.assertIn(
            ref, ('#/definitions/NodeKind', '#/definitions/SignalId'),
            f"[V1 violation] trace_fanin.drivers[].kind 应引用 NodeKind, "
            f"但引用 {ref!r}. Drivers/loads 是 TraceNode, 不是 TraceEdge."
        )


if __name__ == '__main__':
    unittest.main()
