#==============================================================================
# unified_tracer.py - Query Layer
# 使用 Semantic AST (Compilation + getRoot())
#==============================================================================

from dataclasses import dataclass
from typing import Optional, List, Dict, Any
import logging
import os
import networkx as nx

from .core.graph import (
    SignalGraph, TraceNode, TraceEdge, NodeKind, EdgeKind
)
from .core.graph_builder import GraphBuilder
from .core.class_graph_builder import ClassGraphBuilder
from .core.bit_select_handler import BitSelectHandler
from .core.module_instance_graph import ModuleInstanceGraph, PathResolver
from .core.query import (
    SignalTracer, SignalChain,
    LoadTracer, LoadChain,
    ModuleTracer, ModuleConnections,
    ClockDomainTracer, ClockDomainTrace,
)
from .core.query.signal import DriverChain
from .core.compiler import SVCompiler
from .core.semantic_adapter import SemanticAdapter
from dataclasses import dataclass
from typing import List, Set
import re


#==============================================================================
# 状态机分析器
#==============================================================================
@dataclass
class StateTransition:
    """单个状态转换"""
    from_state: str
    to_state: str
    condition: str


@dataclass
class StateMachineInfo:
    """状态机信息"""
    name: str
    state_signal: str
    module: str
    states: Set[str]
    transitions: List[StateTransition]
    reset_state: str
    
    def to_dot(self) -> str:
        """生成 DOT 格式状态图"""
        lines = [
            f'digraph {self.name} {{',
            '    rankdir=LR;',
            '    node [shape=circle];',
            f'    // State signal: {self.state_signal}',
            f'    // Reset state: {self.reset_state}',
            ''
        ]
        for state in sorted(self.states):
            if state == self.reset_state:
                lines.append(f'    {state} [style=filled, color=lightgray];')
            else:
                lines.append(f'    {state};')
        lines.append('')
        for t in sorted(self.transitions, key=lambda x: (x.from_state, x.to_state)):
            cond = t.condition if t.condition else '1'
            lines.append(f'    {t.from_state} -> {t.to_state} [label="{cond}"];')
        lines.append('}')
        return '\n'.join(lines)
    
    def to_mermaid(self) -> str:
        """生成 Mermaid 格式状态图"""
        lines = [
            f'stateDiagram-v2',
            f'    direction LR',
            f'    [*] --> {self.reset_state}',
            ''
        ]
        for t in sorted(self.transitions, key=lambda x: (x.from_state, x.to_state)):
            cond = t.condition if t.condition else ''
            if cond:
                lines.append(f'    {t.from_state} --> {t.to_state} : {cond}')
            else:
                lines.append(f'    {t.from_state} --> {t.to_state}')
        return '\n'.join(lines)


class StateMachineAnalyzer:
    """状态机图生成器 - 分析控制流图中的状态转换
    
    从 UnifiedTracer 获取控制流图,提取状态机转换信息,生成 DOT/Mermaid 格式图.
    """
    
    def __init__(self, tracer):
        self.tracer = tracer
        self.graph = tracer.build_graph()
    
    def analyze(self, state_signal: str, module: str = None) -> StateMachineInfo:
        """分析状态机
        
        Args:
            state_signal: 状态寄存器信号名 (如 "state")
            module: 所在模块 (可选)
            
        Returns:
            StateMachineInfo 或 None
        """
        candidates = []
        for node in self.graph.nodes:
            if module and not node.startswith(module + '.'):
                continue
            if node.endswith('.' + state_signal) or node == state_signal:
                candidates.append(node)
        
        if not candidates:
            return None
        
        state_node = candidates[0]
        
        states = set()
        transitions = []
        reset_state = None
        
        # [FIX] 遍历所有边而不是只检查 get_edge(src, dst)
        for src_node in self.graph.nodes:
            # [FIX] 使用 get_edges 获取所有边（可能有多个不同 condition）
            edges = self.graph.get_edges(src_node, state_node)
            if not edges:
                continue
            
            for edge in edges:
                if 'DRIVER' not in str(edge.kind):
                    continue
                
                condition = edge.condition or ""
                
                # src_node 是状态值常量 (如 fsm3.IDLE)
                to_state = self._extract_state_value(src_node)
                if not to_state:
                    continue
                
                # 从 condition 中提取"当前状态"
                from_state = self._extract_current_state(condition, state_signal)
                
                states.add(to_state)
                if from_state:
                    states.add(from_state)
                
                # 检查是否是复位转换
                if self._is_reset_condition(condition):
                    reset_state = from_state or to_state
                elif from_state:
                    extra_cond = self._strip_state_condition(condition, state_signal)
                    transitions.append(StateTransition(
                        from_state=from_state,
                        to_state=to_state,
                        condition=extra_cond if extra_cond else '1'
                    ))
        
        if not states:
            return None
        
        if '.' in state_node:
            mod = state_node.rsplit('.', 1)[0]
        else:
            mod = module or 'top'
        
        reset_state = reset_state or min(states)
        
        return StateMachineInfo(
            name=f"FSM_{state_signal.replace('.', '_')}",
            state_signal=state_signal,
            module=mod,
            states=states,
            transitions=transitions,
            reset_state=reset_state
        )
    
    def _extract_state_value(self, node: str) -> str:
        if '.' in node:
            return node.rsplit('.', 1)[1]
        return node
    
    def _extract_current_state(self, condition: str, state_signal: str) -> str:
        pattern = rf'{state_signal}\s*(?:==|===)\s*(\w+)'
        m = re.search(pattern, condition)
        if m:
            return m.group(1)
        return None
    
    def _is_reset_condition(self, condition: str) -> bool:
        """检查是否为复位条件
        
        只有纯复位条件（不包含 && 或 ||）才被认为是复位转换。
        例如：
        - "!rst_n" -> True (复位)
        - "!!rst_n" -> True (复位)
        - "!rst_n && state == IDLE" -> False (条件转换)
        """
        stripped = condition.replace(' ', '')
        # 包含 && 或 || 表示有额外条件，不是纯复位
        if '&&' in stripped or '||' in stripped:
            return False
        return 'rst' in stripped.lower() or 'reset' in stripped.lower()
    
    def _strip_state_condition(self, condition: str, state_signal: str) -> str:
        """移除条件中的 state == X 部分，只保留额外条件
        
        例如: "!!rst_n && state == REQ" -> "!!rst_n"
        "state == REQ" -> "1"
        "state == REQ && go" -> "go"
        "!!rst_n && state == REQ && go" -> "!!rst_n && go"
        """
        import re
        # 移除 state == X 部分
        pattern = rf'{state_signal}\s*(?:==|===)\s*\w+\s*'
        result = re.sub(pattern, '', condition).strip()
        
        # 清理多余的 && 和空格
        result = re.sub(r'^\s*&&\s*', '', result)
        result = re.sub(r'\s*&&\s*$', '', result)
        
        # 如果结果为空，返回 "1" (无条件)
        return result if result else '1'

#==============================================================================
# 日志级别配置
#==============================================================================
# 支持的日志级别: DEBUG, INFO, WARNING, ERROR
# 默认使用环境变量 SV_QUERY_LOG_LEVEL，默认为 WARNING
_log_level_from_env = os.environ.get('SV_QUERY_LOG_LEVEL', 'WARNING').upper()
_log_level_map = {
    'DEBUG': logging.DEBUG,
    'INFO': logging.INFO,
    'WARNING': logging.WARNING,
    'ERROR': logging.ERROR,
}
_default_log_level = _log_level_map.get(_log_level_from_env, logging.WARNING)

# 配置根 logger
_root_logger = logging.getLogger('trace')
_root_logger.setLevel(_default_log_level)

# 配置 __main__ logger (用于 build_graph 等操作)
_main_logger = logging.getLogger('trace.core')
_main_logger.setLevel(_default_log_level)

#==============================================================================
# 数据类
#==============================================================================
@dataclass
class InstanceInfo:
    """模块实例信息 - 封装实例提取结果
    
    Attributes:
        name: 实例名称 (不含父路径), 如 "u_dut"
        module_type: 模块类型, 如 "dut"
        full_path: 完整路径, 如 "top.u_dut"
        parent: 父实例路径, 如 "top" 或 None (顶层)
    """
    name: str
    module_type: str
    full_path: str
    parent: Optional[str] = None

#==============================================================================
# UnifiedTracer
#==============================================================================
class UnifiedTracer:
    """统一追踪入口"""
    
    def __init__(self, sources: Dict[str, str] = None, files: List[str] = None,
                 filelist: str = None, log_level: str = None):
        """初始化 UnifiedTracer
        
        Args:
            sources: 源文件字典 {"filename.sv": "source code"}
            files: SV 源文件路径列表
            filelist: SV 文件列表 (.fl/.f/.filelist) 路径
            log_level: 日志级别 (DEBUG/INFO/WARNING/ERROR)
                      默认为环境变量 SV_QUERY_LOG_LEVEL 的值
        """
        if sources is None:
            sources = {}
        self._sources = sources
        self._log_level = log_level or os.environ.get('SV_QUERY_LOG_LEVEL', 'WARNING')
        self._compiler: Optional[SVCompiler] = None
        self._files = files or []
        self._filelist = filelist
        self._adapter = None
        self._graph: Optional[SignalGraph] = None
        self._signal_tracer: Optional[SignalTracer] = None
        self._module_tracer: Optional[ModuleTracer] = None
        self._clock_tracer: Optional[ClockDomainTracer] = None
        self._load_tracer: Optional[LoadTracer] = None
        
        # 日志级别控制
        if log_level is not None:
            self.set_log_level(log_level)
    
    def set_log_level(self, level: str):
        """动态设置日志级别
        
        Args:
            level: DEBUG, INFO, WARNING, ERROR
        """
        level = level.upper()
        log_level_val = _log_level_map.get(level, logging.WARNING)
        _root_logger.setLevel(log_level_val)
        _main_logger.setLevel(log_level_val)
    
    def get_log_level(self) -> str:
        """获取当前日志级别名称"""
        return logging.getLevelName(_root_logger.level)
    
    def _get_compiler(self) -> SVCompiler:
        """获取 SVCompiler (Semantic AST 编译入口)"""
        if self._compiler is None:
            self._compiler = SVCompiler(self._sources, log_level=self._log_level)
            if self._files:
                self._compiler.add_files(self._files)
            if self._filelist:
                self._compiler.add_filelist(self._filelist)
        return self._compiler
    
    def _get_adapter(self):
        """获取 SemanticAdapter wrapping Semantic AST root (RootSymbol)"""
        if self._adapter is None:
            self._adapter = SemanticAdapter(self._get_compiler().get_root())
        return self._adapter
    
    @property
    def sources(self) -> Dict[str, str]:
        """获取源文件字典"""
        return self._sources.copy()
    
    @property
    def compilation(self):
        """获取 Compilation 对象"""
        return self._get_compiler().get_compilation()
    
    def build_graph(self, force: bool = False) -> SignalGraph:
        if self._graph is None or force:
            root = self._get_compiler().get_root()
            
            # 创建 SemanticAdapter 供各组件使用
            from .core.semantic_adapter import SemanticAdapter
            compiler = self._get_compiler()
            semantic_adapter = SemanticAdapter(root, compiler)
            self._adapter = semantic_adapter  # Store for later access by _get_adapter()
            
            builder = GraphBuilder(semantic_adapter)
            self._graph = builder.build()
            # [Phase2] 追加 class 子图
            class_builder = ClassGraphBuilder(semantic_adapter)
            class_builder.build(self._graph)
            # [Phase3] 处理位选节点 (提取位宽、设置父子关系) - 在所有节点创建后
            bit_select_handler = BitSelectHandler(semantic_adapter, self._graph)
            bit_select_handler.process()
            
            # [Phase4] 构建模块实例图 (跨模块边界追踪)
            self._module_graph = ModuleInstanceGraph(semantic_adapter, self._graph)
            self._module_graph.build(semantic_adapter)  # 传入 SemanticAdapter 用于 generate 实例收集
            self._path_resolver = PathResolver(self._graph, self._module_graph)
            self._init_tracers()
        return self._graph
    
    def load_graph(self, graph: SignalGraph):
        self._graph = graph
        self._init_tracers()
    
    def get_graph(self) -> Optional[SignalGraph]:
        return self._graph
    
    # =========================================================================
    # 实例提取 API (Req-1: API 简化)
    # =========================================================================
    def get_instances(self, module: str = None) -> List[InstanceInfo]:
        """获取模块实例列表
        
        简化实例提取 API，自动合并 Module 和 Generate 中的实例，
        并返回结构化的 InstanceInfo 对象。
        
        Args:
            module: 可选，限定实例必须在指定模块内 (如 "top")
                   不指定则返回所有实例
        
        Returns:
            List[InstanceInfo]: 实例信息列表，按 full_path 去重
        
        Example:
            tracer = UnifiedTracer(parser, trees)
            tracer.build_graph()
            
            # 获取所有实例
            all_instances = tracer.get_instances()
            
            # 获取 top 模块内的实例
            top_instances = tracer.get_instances(module='top')
            
            for inst in top_instances:
                print(f"{inst.full_path} ({inst.module_type})")
        """
        adapter = self._get_adapter()  # SemanticAdapter
        semantic_adapter = SemanticAdapter(adapter)
        
        # 获取 Module 和 Generate 中的实例
        module_insts = semantic_adapter.get_module_instances()
        gen_insts = []  # Semantic AST 暂不处理 generate 实例
        
        # 合并并去重
        seen = set()
        result = []
        
        for inst_list in [module_insts, gen_insts]:
            for node in inst_list:
                inst_info = self._parse_instance_node(node)
                if inst_info and inst_info.full_path not in seen:
                    seen.add(inst_info.full_path)
                    # 模块过滤
                    if module is None or inst_info.parent == module or inst_info.full_path == module:
                        result.append(inst_info)
        
        return result
    
    def _parse_instance_node(self, node) -> Optional[InstanceInfo]:
        """解析模块实例节点为 InstanceInfo
        
        支持 Semantic AST (InstanceSymbol) 和 SyntaxTree (HierarchyInstantiationSyntax)
        
        Args:
            node: InstanceSymbol 或 HierarchyInstantiationSyntax 节点
        
        Returns:
            InstanceInfo 或 None (解析失败)
        """
        try:
            # Semantic AST: InstanceSymbol
            if hasattr(node, 'kind') and 'Instance' in str(node.kind):
                name = getattr(node, 'name', None)
                if not name:
                    return None
                
                # 获取模块类型
                module_type = None
                if hasattr(node, 'definition'):
                    defn = node.definition
                    if hasattr(defn, 'name'):
                        module_type = getattr(defn, 'name', None) or str(defn)
                elif hasattr(node, 'body'):
                    # InstanceBodySymbol
                    if hasattr(node.body, 'definition'):
                        defn = node.body.definition
                        module_type = getattr(defn, 'name', None) or str(defn)
                
                return InstanceInfo(
                    name=str(name),
                    module_type=str(module_type) if module_type else 'unknown',
                    full_path=str(name),
                    parent=None
                )
            
            # SyntaxTree: HierarchyInstantiationSyntax
            module_type = None
            if hasattr(node, 'type'):
                if hasattr(node.type, 'value'):
                    module_type = node.type.value
                elif hasattr(node.type, 'text'):
                    module_type = node.type.text
            
            if not module_type:
                return None
            
            if not hasattr(node, 'instances') or not node.instances:
                return None
            
            instances = []
            for inst_item in node.instances:
                if not hasattr(inst_item, 'kind') or str(inst_item.kind) != 'SyntaxKind.HierarchicalInstance':
                    continue
                
                name = None
                if hasattr(inst_item, 'decl') and hasattr(inst_item.decl, 'name'):
                    name_val = getattr(inst_item.decl.name, 'value', None) or getattr(inst_item.decl.name, 'text', None)
                    name = name_val
                
                if not name:
                    continue
                
                instances.append(InstanceInfo(
                    name=name,
                    module_type=module_type,
                    full_path=name,
                    parent=None
                ))
            
            # 返回第一个实例 (通常 HierarchyInstantiation 每个节点只有一个实例)
            return instances[0] if instances else None
            
        except Exception as e:
            _main_logger.debug(f"[InstanceInfo] parse failed: {e}")
            return None
    
    # =========================================================================
    # 信号追踪 API
    # =========================================================================
    def trace_signal(self, signal: str, module: str = None) -> SignalChain:
        self.build_graph()
        return self._signal_tracer.trace(signal, module)

    def trace_loads(self, signal: str, module: str = None) -> LoadChain:
        """Trace signal fanout (loads)"""
        self.build_graph()
        return self._load_tracer.trace(signal, module)
    
    def trace_fanout(self, signal: str, module: str = None, depth: int | None = None) -> list:
        self.build_graph()
        return self._signal_tracer.trace_fanout(signal, module, depth)

    def trace_fanin(self, signal: str, module: str = None, depth: int | None = None) -> list:
        self.build_graph()
        return self._signal_tracer.trace_fanin(signal, module, depth)

    def trace_detailed(self, signal: str, module: str = None) -> DriverChain:
        """[方案C] Trace signal with detailed driver information
        
        返回包含 condition, clock_domain 等详细信息的驱动链
        
        Args:
            signal: signal name
            module: module name (optional)
            
        Returns:
            DriverChain - 包含 DriverInfo 列表
        """
        self.build_graph()
        return self._signal_tracer.trace_detailed(signal, module)

    def trace_fanin_detailed(self, signal: str, module: str = None, depth: int | None = None) -> list:
        """[方案C] Trace signal fanin with detailed driver information
        
        Args:
            signal: signal name
            module: module name (optional)
            depth: 1=direct drivers only, N=recursive N levels, None=recursive all
            
        Returns:
            List[DriverInfo] - 驱动信息列表
        """
        self.build_graph()
        return self._signal_tracer.trace_fanin_detailed(signal, module, depth)

    # =========================================================================
    # 模块追踪 API
    # =========================================================================
    def trace_module(self, module: str) -> ModuleConnections:
        self.build_graph()
        return self._module_tracer.trace(module)
    
    def trace_port(self, module: str, port_name: str) -> list:
        self.build_graph()
        return self._module_tracer.trace_port(module, port_name)
    
    def find_connected_modules(self, module: str) -> list:
        self.build_graph()
        return self._module_tracer.find_connected_modules(module)
    
    # =========================================================================
    # 时钟域追踪 API
    # =========================================================================
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
    
    # =========================================================================
    # 分析 API
    # =========================================================================
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
    # =========================================================================
    # 状态机分析 API
    # =========================================================================
    def analyze_fsm(self, state_signal: str, module: str = None) -> StateMachineInfo:
        """分析状态机,生成状态转换图
        
        从控制流分析结果中提取状态机转换信息,生成 DOT/Mermaid 格式图.
        
        Args:
            state_signal: 状态寄存器信号名 (如 "state", "fsm_state")
            module: 所在模块 (可选, 用于限定搜索范围)
            
        Returns:
            StateMachineInfo - 包含状态、转换、输出格式等信息
            
        Example:
            >>> tracer = UnifiedTracer({'top.sv': src})
            >>> fsm = tracer.analyze_fsm('state', 'fsm3')
            >>> print(fsm.to_dot())  # DOT 格式
            >>> print(fsm.to_mermaid())  # Mermaid 格式
        """
        self.build_graph()
        analyzer = StateMachineAnalyzer(self)
        return analyzer.analyze(state_signal, module)
