#==============================================================================
# unified_tracer.py - Query Layer
#==============================================================================

from typing import Optional
import networkx as nx

from .graph_models import (
    SignalGraph, TraceNode, TraceEdge, NodeKind, EdgeKind
)
from .graph_builder import GraphBuilder
from .query_signal import SignalTracer, SignalChain
from .query_module import ModuleTracer, ModuleConnections
from .query_clock_domain import ClockDomainTracer, ClockDomainTrace

class UnifiedTracer:
    """统一追踪入口"""
    
    def __init__(self, parser=None):
        self.parser = parser
        self._graph: Optional[SignalGraph] = None
        self._signal_tracer: Optional[SignalTracer] = None
        self._module_tracer: Optional[ModuleTracer] = None
        self._clock_tracer: Optional[ClockDomainTracer] = None
    
    def build_graph(self, force: bool = False) -> SignalGraph:
        if self._graph is None or force:
            if self.parser is None:
                raise ValueError("Parser required")
            builder = GraphBuilder(self.parser)
            self._graph = builder.build()
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
