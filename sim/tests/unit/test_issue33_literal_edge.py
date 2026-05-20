"""
金标准测试: Issue 33 - 字面量边问题

【问题描述】
当 assign 语句的 RHS 是字面量（如 1'b0）时：
1. 不应该创建字面量节点（如 serv_top.0）
2. 应该只创建 DRIVER 边（字面量 → 目标）
3. 不应该产生重复边

【RTL 源码】
```systemverilog
module serv_top();
    wire iscomp;
    wire csr_in;
    assign iscomp = 1'b0;   // 字面量赋值
    assign csr_in = {W{1'b0}};  // 拼接字面量
endmodule
```

【金标准】
| 边类型 | src | dst | 预期 |
|--------|-----|-----|------|
| DRIVER | 1'b0 | serv_top.iscomp | 正确（无 module 前缀）|
| DRIVER | 1'b0 | serv_top.csr_in | 正确（无 module 前缀）|

| 节点 | 预期 |
|------|------|
| serv_top.0 | 不应该存在 |
| serv_top.1'b0 | 不应该存在 |

【验证方式】
1. 检查边：字面量边应该是 "1'b0" -> "serv_top.xxx"，不是 "serv_top.1'b0" -> "serv_top.xxx"
2. 检查节点：不应该有以字面量开头的节点 ID

【预期结果】
- 边: 2 条（iscomp 和 csr_in 的驱动边）
- 字面量节点: 0 个
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

from trace.unified_tracer import UnifiedTracer
import pyslang


class TestIssue33LiteralEdge:
    """测试字面量边不应该有 module 前缀"""

    @pytest.fixture
    def serv_top_source(self):
        """serv_top.v 字面量赋值"""
        return '''
module serv_top #(
    parameter W = 8
) (
    input clk
);
    wire iscomp;
    wire csr_in;
    
    // 字面量赋值（问题场景）
    assign iscomp = 1'b0;
    assign csr_in = {W{1'b0}};
endmodule
'''

    def test_literal_edge_no_module_prefix(self, serv_top_source):
        """
        【金标准】字面量边不应该有 module 前缀
        
        预期:
        - 边 src 不应该是 "serv_top.1'b0" 或 "serv_top.0"
        - 边 src 应该是 "1'b0"（字面量直接作为 src）
        """
        tree = pyslang.SyntaxTree.fromText(serv_top_source)
        tracer = UnifiedTracer(sources={'serv_top.sv': serv_top_source}, log_level='ERROR')
        tracer.build_graph()
        graph = tracer.get_graph()

        # 检查所有边
        edges = list(graph.edges())
        
        # 找 iscomp 和 csr_in 相关边
        iscomp_edges = [(src, dst) for src, dst in edges if 'iscomp' in str(dst)]
        csr_in_edges = [(src, dst) for src, dst in edges if 'csr_in' in str(dst)]
        
        print(f"\n=== iscomp 相关边 ===")
        for src, dst in iscomp_edges:
            print(f"  {src} -> {dst}")
        
        print(f"\n=== csr_in 相关边 ===")
        for src, dst in csr_in_edges:
            print(f"  {src} -> {dst}")
        
        # 验证：字面量边不应该有 "serv_top." 前缀
        for src, dst in iscomp_edges + csr_in_edges:
            assert not str(src).startswith('serv_top.'), \
                f"字面量边不应该有 module 前缀，实际: {src}"
        
        # 验证：字面量边应该是 "1'b0" 而不是 "serv_top.0"
        for src, dst in iscomp_edges:
            assert src == "1'b0", f"iscomp 边的 src 应该是 '1'b0'，实际: {src}"
        
        for src, dst in csr_in_edges:
            assert src == "1'b0", f"csr_in 边的 src 应该是 '1'b0'，实际: {src}"

    def test_no_literal_node_created(self, serv_top_source):
        """
        【金标准】不应该创建字面量节点
        
        预期:
        - 不应该有节点 ID 为 "serv_top.0" 或 "serv_top.1'b0"
        - 节点名不应该是 "0" 或 "1'b0"
        """
        tree = pyslang.SyntaxTree.fromText(serv_top_source)
        tracer = UnifiedTracer(sources={'serv_top.sv': serv_top_source}, log_level='ERROR')
        tracer.build_graph()
        graph = tracer.get_graph()

        # 检查所有节点
        all_node_ids = list(graph.nodes())
        print(f"\n=== 所有节点 ===")
        for nid in all_node_ids:
            print(f"  {nid}")
        
        # 验证：不应该有 "serv_top.0" 或 "serv_top.1'b0" 节点
        bad_nodes = [nid for nid in all_node_ids if 'serv_top.0' in nid or 'serv_top.1' in nid]
        assert len(bad_nodes) == 0, \
            f"不应该有字面量节点，实际: {bad_nodes}"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
