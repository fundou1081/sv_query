"""
金标准测试: _get_signal 对 IdentifierName 的处理

【测试设计】
RTL 源码:
  module mult_pipe2(input clk);
    always @(posedge clk)
    begin
    // registering input of the multiplier
      a_int <= a;
    end
  endmodule

【金标准】
- a_int 节点的名称应该是 "a_int"，不含注释或换行
- 节点名不应该包含 "// registering input of the multiplier"

【验证方式】
1. 解析 RTL，构建图
2. 查找名为 "a_int" 的节点
3. 验证节点名不含注释

【预期结果】
- 节点名: "a_int" (不包含注释)
"""

import pytest
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

from trace.unified_tracer import UnifiedTracer
import pyslang


class TestGetSignalIdentifierName:
    """测试 _get_signal 对 IdentifierName 的处理"""

    @pytest.fixture
    def mult_pipe2_source(self):
        """mult_pipe2.v 的关键源码片段"""
        return '''
module mult_pipe2(
    input clk,
    input [15:0] a,
    input [15:0] b,
    output [31:0] pdt
);
    reg [15:0] a_int;
    reg [15:0] b_int;
    reg [31:0] pdt_int [1:0];

    always @(posedge clk)
    begin
    // registering input of the multiplier
        a_int <= a;
        b_int <= b;
        for(integer i=1; i<2; i=i+1)
            pdt_int[i] <= pdt_int[i-1];
        pdt_int[0] <= a_int * b_int;
    end

    assign pdt = pdt_int[1];
endmodule
'''

    def test_identifier_name_without_leading_comment(self, mult_pipe2_source):
        """
        【金标准】IdentifierName 不应包含 leading trivia (注释、换行)

        预期:
        - 存在名为 "mult_pipe2.a_int" 的节点
        - 该节点名不包含 "// registering input of the multiplier"
        - 该节点名不包含换行符 \n 或制表符 \t
        """
        # 构建图
        tree = pyslang.SyntaxTree.fromText(mult_pipe2_source)
        tracer = UnifiedTracer(sources={'mult_pipe2.sv': mult_pipe2_source}, log_level='ERROR')
        tracer.build_graph()
        graph = tracer.get_graph()

        # 查找 a_int 相关节点
        a_int_nodes = []
        for node_id in graph.nodes():
            node = graph.get_node(node_id)
            if node and hasattr(node, 'name'):
                if 'a_int' in node.name:
                    a_int_nodes.append(node)

        # 验证
        assert len(a_int_nodes) >= 1, "应存在 mult_pipe2.a_int 节点"

        a_int_node = a_int_nodes[0]
        assert '//' not in a_int_node.name, \
            f"节点名不应包含注释，实际: {repr(a_int_node.name)}"
        assert '\n' not in a_int_node.name, \
            f"节点名不应包含换行符，实际: {repr(a_int_node.name)}"
        assert '\t' not in a_int_node.name, \
            f"节点名不应包含制表符，实际: {repr(a_int_node.name)}"
        assert a_int_node.name.strip() == 'a_int', \
            f"节点名应为 'mult_pipe2.a_int'，实际: {repr(a_int_node.name)}"

    def test_all_signal_nodes_clean(self, mult_pipe2_source):
        """
        【金标准】所有信号节点名不应包含注释或换行

        预期:
        - 所有节点名都是干净的标识符
        - 不存在名为 "// comment..." 的节点
        """
        tree = pyslang.SyntaxTree.fromText(mult_pipe2_source)
        tracer = UnifiedTracer(sources={'mult_pipe2.sv': mult_pipe2_source}, log_level='ERROR')
        tracer.build_graph()
        graph = tracer.get_graph()

        # 检查所有节点
        for node_id in graph.nodes():
            node = graph.get_node(node_id)
            if node and hasattr(node, 'name'):
                # 节点名不应以 // 或 /* 开头
                assert not node.name.strip().startswith('//'), \
                    f"节点名不应以注释开头: {repr(node.name)}"
                assert not node.name.strip().startswith('/*'), \
                    f"节点名不应以注释开头: {repr(node.name)}"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
