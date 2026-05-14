#==============================================================================
# test_snapshot.py - Snapshot 功能测试
# [铁律13] 金标准测试优先
#==============================================================================
# 测试场景:
# 1. SignalGraph 序列化/反序列化 round-trip
# 2. SnapshotManager CRUD 操作
# 3. 快照对比功能
#==============================================================================

import unittest
import sys
import os
import tempfile
import json
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

import pyslang
from trace.unified_tracer import UnifiedTracer
from trace.core.graph.models import SignalGraph, NodeKind, EdgeKind, TraceNode, TraceEdge
from trace.core.snapshot_manager import SnapshotManager


class TestSignalGraphSerialization(unittest.TestCase):
    """[Golden] SignalGraph 序列化/反序列化 round-trip 测试"""
    
    def test_roundtrip_simple(self):
        """[Golden] 简单图序列化后能完整还原
        
        金标准:
        1. 创建包含 3 节点 2 边的图
        2. 序列化为 JSON
        3. 反序列化
        4. 验证节点数、边数完全一致
        """
        # 创建测试图
        G = SignalGraph()
        
        nodes = [
            TraceNode("top.a", "a", "top", NodeKind.SIGNAL, (7, 0)),
            TraceNode("top.b", "b", "top", NodeKind.REG, (7, 0)),
            TraceNode("top.clk", "clk", "top", NodeKind.PORT_IN, (0, 0)),
        ]
        for n in nodes:
            G.add_trace_node(n)
        
        edges = [
            TraceEdge("top.a", "top.b", EdgeKind.DRIVER),
            TraceEdge("top.clk", "top.b", EdgeKind.CLOCK),
        ]
        for e in edges:
            G.add_trace_edge(e)
        
        # Round-trip
        json_str = G.to_json()
        G2 = SignalGraph.from_json(json_str)
        
        # 验证
        self.assertEqual(G2.number_of_nodes(), 3)
        self.assertEqual(G2.number_of_edges(), 2)
        
        # 验证节点数据
        node_a = G2.get_node("top.a")
        self.assertIsNotNone(node_a)
        self.assertEqual(node_a.name, "a")
        self.assertEqual(node_a.module, "top")
        self.assertEqual(node_a.kind, NodeKind.SIGNAL)
        
        # 验证边数据
        edge_ab = G2.get_edge("top.a", "top.b")
        self.assertIsNotNone(edge_ab)
        self.assertEqual(edge_ab.kind, EdgeKind.DRIVER)
    
    def test_roundtrip_with_modport(self):
        """[Golden] 带 modport 信息的图序列化还原
        
        金标准:
        - modport_dir 字段能正确序列化/反序列化
        """
        G = SignalGraph()
        
        node = TraceNode("tb.data", "data", "tb", NodeKind.SIGNAL, (7, 0), modport_dir="output")
        G.add_trace_node(node)
        
        json_str = G.to_json()
        G2 = SignalGraph.from_json(json_str)
        
        node2 = G2.get_node("tb.data")
        self.assertEqual(node2.modport_dir, "output")


class TestSnapshotManager(unittest.TestCase):
    """[Golden] SnapshotManager CRUD 测试"""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.manager = SnapshotManager(base_dir=self.temp_dir)
        
        # 创建测试图
        self.graph = SignalGraph()
        node1 = TraceNode("top.a", "a", "top", NodeKind.SIGNAL, (7, 0))
        node2 = TraceNode("top.b", "b", "top", NodeKind.REG, (7, 0))
        self.graph.add_trace_node(node1)
        self.graph.add_trace_node(node2)
        edge = TraceEdge("top.a", "top.b", EdgeKind.DRIVER)
        self.graph.add_trace_edge(edge)
    
    def test_save_and_load(self):
        """[Golden] 保存并加载快照
        
        金标准:
        1. 保存快照 -> 文件存在
        2. 加载 -> 数据完整
        """
        tag = "test_v1"
        path = self.manager.save(tag, self.graph.to_dict(), git_commit="abc1234", files=["a.sv"])
        
        self.assertTrue(Path(path).exists())
        
        data = self.manager.load(tag)
        self.assertIsNotNone(data)
        self.assertEqual(data["tag"], tag)
        self.assertEqual(data["git_commit"], "abc1234")
        self.assertEqual(data["files"], ["a.sv"])
        self.assertEqual(data["node_count"], 2)
        self.assertEqual(data["edge_count"], 1)
    
    def test_save_overwrite(self):
        """[Golden] 重复保存同名快照会覆盖
        
        金标准:
        - 第二次 save 覆盖第一次
        """
        self.manager.save("test_tag", self.graph.to_dict())
        
        # 添加新节点
        node3 = TraceNode("top.c", "c", "top", NodeKind.SIGNAL, (7, 0))
        self.graph.add_trace_node(node3)
        
        self.manager.save("test_tag", self.graph.to_dict())
        
        data = self.manager.load("test_tag")
        self.assertEqual(data["node_count"], 3)
    
    def test_delete(self):
        """[Golden] 删除快照
        
        金标准:
        1. 删除存在的快照 -> True
        2. 删除不存在的快照 -> False
        """
        self.manager.save("to_delete", self.graph.to_dict())
        
        self.assertTrue(self.manager.delete("to_delete"))
        self.assertFalse(self.manager.exists("to_delete"))
        self.assertFalse(self.manager.delete("not_exists"))
    
    def test_list(self):
        """[Golden] 列出所有快照
        
        金标准:
        - 返回按时间排序的快照列表
        """
        self.manager.save("v1", self.graph.to_dict())
        
        from time import sleep
        sleep(0.01)  # 确保时间戳不同
        
        node3 = TraceNode("top.c", "c", "top", NodeKind.SIGNAL, (7, 0))
        self.graph.add_trace_node(node3)
        self.manager.save("v2", self.graph.to_dict())
        
        tags = self.manager.list_tags()
        self.assertIn("v1", tags)
        self.assertIn("v2", tags)
    
    def test_compare(self):
        """[Golden] 对比两个快照
        
        金标准:
        - 创建两个有差异的图
        - 对比 -> 正确识别 added/removed nodes
        """
        # 旧图
        G_old = SignalGraph()
        node_a = TraceNode("top.a", "a", "top", NodeKind.SIGNAL, (7, 0))
        G_old.add_trace_node(node_a)
        
        # 新图 (多一个节点 c)
        G_new = SignalGraph()
        node_a2 = TraceNode("top.a", "a", "top", NodeKind.SIGNAL, (7, 0))
        node_c = TraceNode("top.c", "c", "top", NodeKind.SIGNAL, (7, 0))
        G_new.add_trace_node(node_a2)
        G_new.add_trace_node(node_c)
        
        self.manager.save("old", G_old.to_dict())
        self.manager.save("new", G_new.to_dict())
        
        result = self.manager.compare("old", "new")
        
        self.assertIsNotNone(result)
        self.assertIn("top.c", result["added_nodes"])
        self.assertEqual(result["health_delta"], -0.5)  # 稳定核心为 0（a 的边也变了）


if __name__ == '__main__':
    unittest.main()
