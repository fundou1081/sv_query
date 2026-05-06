#==============================================================================
# test_graph_models.py - 数据模型单元测试
# [铁律4] 模型即契约
#==============================================================================

import unittest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

from trace.core.graph_models import (
    SignalGraph, TraceNode, TraceEdge, NodeKind, EdgeKind
)

class TestGraphModels(unittest.TestCase):
    """数据模型测试"""
    
    def test_node_creation(self):
        """TraceNode 创建"""
        node = TraceNode(
            id='top.din',
            name='din',
            module='top',
            kind=NodeKind.SIGNAL,
            width=(1, 0)
        )
        self.assertEqual(node.id, 'top.din')
        self.assertEqual(node.name, 'din')
        self.assertEqual(node.kind, NodeKind.SIGNAL)
    
    def test_edge_creation(self):
        """TraceEdge 创建"""
        edge = TraceEdge(
            src='top.din',
            dst='top.data',
            kind=EdgeKind.DRIVER,
            assign_type='continuous'
        )
        self.assertEqual(edge.src, 'top.din')
        self.assertEqual(edge.dst, 'top.data')
        self.assertEqual(edge.kind, EdgeKind.DRIVER)
    
    def test_graph_add_node(self):
        """Graph 添加节点"""
        graph = SignalGraph()
        node = TraceNode(
            id='top.din',
            name='din',
            module='top',
            kind=NodeKind.SIGNAL,
            width=(1, 0)
        )
        graph.add_trace_node(node)
        
        self.assertTrue(graph.has_node('top.din'))
        self.assertEqual(graph.number_of_nodes(), 1)
    
    def test_graph_add_edge(self):
        """Graph 添加边"""
        graph = SignalGraph()
        
        # 先添加节点
        src_node = TraceNode(id='top.din', name='din', module='top', kind=NodeKind.SIGNAL, width=(1,0))
        dst_node = TraceNode(id='top.data', name='data', module='top', kind=NodeKind.SIGNAL, width=(1,0))
        graph.add_trace_node(src_node)
        graph.add_trace_node(dst_node)
        
        # 添加边
        edge = TraceEdge(
            src='top.din',
            dst='top.data',
            kind=EdgeKind.DRIVER,
            assign_type='continuous'
        )
        graph.add_trace_edge(edge)
        
        self.assertEqual(graph.number_of_edges(), 1)
        self.assertTrue(graph.has_edge('top.din', 'top.data'))
    
    def test_graph_get_node(self):
        """获取节点数据"""
        graph = SignalGraph()
        node = TraceNode(
            id='top.din',
            name='din',
            module='top',
            kind=NodeKind.SIGNAL,
            width=(1, 0)
        )
        graph.add_trace_node(node)
        
        retrieved = graph.get_node('top.din')
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.name, 'din')
    
    def test_graph_get_edge(self):
        """获取边数据"""
        graph = SignalGraph()
        src = TraceNode(id='top.din', name='din', module='top', kind=NodeKind.SIGNAL, width=(1,0))
        dst = TraceNode(id='top.data', name='data', module='top', kind=NodeKind.SIGNAL, width=(1,0))
        graph.add_trace_node(src)
        graph.add_trace_node(dst)
        
        edge = TraceEdge(src='top.din', dst='top.data', kind=EdgeKind.DRIVER)
        graph.add_trace_edge(edge)
        
        retrieved = graph.get_edge('top.din', 'top.data')
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.kind, EdgeKind.DRIVER)
    
    def test_node_kind_enum(self):
        """NodeKind 枚举"""
        self.assertEqual(NodeKind.SIGNAL.value, 1)
        self.assertIn(NodeKind.REG.value, [1,2,3])
        self.assertEqual(NodeKind.PORT_IN.value, 4)
    
    def test_edge_kind_enum(self):
        """EdgeKind 枚举"""
        self.assertEqual(EdgeKind.DRIVER.value, 1)
        self.assertEqual(EdgeKind.DATA.value, 2)


if __name__ == '__main__':
    unittest.main()
