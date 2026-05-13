#==============================================================================
# unified_tracer.py - Query Layer
# 使用 PyslangAdapter (Syntax Layer)
#==============================================================================

from typing import Optional
import networkx as nx

from .core.graph_models import (
    SignalGraph, TraceNode, TraceEdge, NodeKind, EdgeKind
)
from .core.graph_builder import GraphBuilder
from .core.class_graph_builder import ClassGraphBuilder
from .core.bit_select_handler import BitSelectHandler
from .core.module_instance_graph import ModuleInstanceGraph, PathResolver
from .core.query_signal import SignalTracer, SignalChain
from .core.query_load import LoadTracer, LoadChain
from .core.query_module import ModuleTracer, ModuleConnections
from .core.query_clock_domain import ClockDomainTracer, ClockDomainTrace
from .core.base import PyslangAdapter

class UnifiedTracer:
    """统一追踪入口"""
    
    def __init__(self, parser=None, trees: dict = None):
        self.parser = parser
        self.trees = trees or {}
        self._adapter: Optional[PyslangAdapter] = None
        self._graph: Optional[SignalGraph] = None
        self._signal_tracer: Optional[SignalTracer] = None
        self._module_tracer: Optional[ModuleTracer] = None
        self._clock_tracer: Optional[ClockDomainTracer] = None
        self._load_tracer: Optional[LoadTracer] = None
    
    def _get_adapter(self) -> PyslangAdapter:
        """获取 PyslangAdapter (Syntax Layer)"""
        if self._adapter is None:
            # 构造适配器需要的 parser 结构
            class TreeParser:
                def __init__(self, trees):
                    self.trees = trees
            self._adapter = PyslangAdapter(TreeParser(self.trees))
        return self._adapter
    
    def build_graph(self, force: bool = False) -> SignalGraph:
        if self._graph is None or force:
            adapter = self._get_adapter()
            builder = GraphBuilder(adapter)
            self._graph = builder.build()
            # [Phase2] 追加 class 子图
            class_builder = ClassGraphBuilder(adapter)
            class_builder.build(self._graph)
            # [Phase3] 处理位选节点 (提取位宽、设置父子关系) - 在所有节点创建后
            bit_select_handler = BitSelectHandler(adapter, self._graph)
            bit_select_handler.process()
            
            # [Phase4] 构建模块实例图 (跨模块边界追踪)
            self._module_graph = ModuleInstanceGraph(adapter, self._graph)
            self._module_graph.build(self.trees)
            self._path_resolver = PathResolver(self._graph, self._module_graph)
            self._init_tracers()
        return self._graph
    
    def load_graph(self, graph: SignalGraph):
        self._graph = graph
        self._init_tracers()
    
    def get_graph(self) -> Optional[SignalGraph]:
        return self._graph
    
    # 场景A
    def trace_signal(self, signal: str, module: str = None) -> SignalChain:
        self.build_graph()
        return self._signal_tracer.trace(signal, module)

    def trace_loads(self, signal: str, module: str = None) -> LoadChain:
        """Trace signal fanout (loads)"""
        self.build_graph()
        return self._load_tracer.trace(signal, module)
    
    def trace_fanout(self, signal: str, module: str = None) -> list:
        self.build_graph()
        return self._signal_tracer.trace_fanout(signal, module)
    
    def trace_fanin(self, signal: str, module: str = None) -> list:
        self.build_graph()
        return self._signal_tracer.trace_fanin(signal, module)
    
    # 场景B
    def trace_module(self, module: str) -> ModuleConnections:
        self.build_graph()
        return self._module_tracer.trace(module)
    
    def trace_port(self, module: str, port_name: str) -> list:
        self.build_graph()
        return self._module_tracer.trace_port(module, port_name)
    
    def find_connected_modules(self, module: str) -> list:
        self.build_graph()
        return self._module_tracer.find_connected_modules(module)
    
    # 场景C
    def trace_clock_domain(self, clock: str) -> ClockDomainTrace:
        self.build_graph()
        return self._clock_tracer.trace(clock)
    
    def trace_all_domains(self) -> list:
        self.build_graph()
        return self._clock_tracer.trace_all_domains()
    
    def find_synchronizers(self, clock: str) -> list:
        self.build_graph()
        return self._clock_tracer.find_synchronizers(clock)
    
    def check_cdc_violations(self) -> list:
        self.build_graph()
        return self._clock_tracer.check_cdc_violations()
    
    # 分析
    def find_path(self, src: str, dst: str) -> list:
        self.build_graph()
        return self._graph.find_path(src, dst)
    
    def detect_cycles(self) -> list:
        self.build_graph()
        return self._graph.detect_cycles()
    
    def stats(self) -> dict:
        if self._graph:
            return self._graph.stats()
        return {}
    
    def _init_tracers(self):
        self._signal_tracer = SignalTracer(self._graph)
        self._module_tracer = ModuleTracer(self._graph)
        self._clock_tracer = ClockDomainTracer(self._graph)
        self._load_tracer = LoadTracer(self._graph)
