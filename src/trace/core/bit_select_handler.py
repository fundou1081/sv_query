"""
bit_select_handler.py - Bit Select 节点处理模块

[铁律11] 单一职责 - 专门处理位选节点

职责：
1. 从 DataDeclaration 提取所有信号的位宽
2. 为 bit-select 节点 (如 data[3:0]) 建立父子关系
3. 填充 bit_range, parent_bit_start, parent_bit_end 属性
4. 创建 BIT_SELECT 边

使用方式：
  handler = BitSelectHandler(adapter, graph)
  handler.process()
"""

import re
from typing import Dict, Optional, Tuple, List
from trace.core.base import PyslangAdapter


class BitSelectHandler:
    """位选节点处理器"""
    
    def __init__(self, adapter: PyslangAdapter, graph):
        """
        Args:
            adapter: PyslangAdapter 实例
            graph: SignalGraph 实例
        """
        self.adapter = adapter
        self.graph = graph
        self.signal_widths: Dict[str, Tuple[int, int]] = {}  # 信号名 → (msb, lsb)
    
    def process(self):
        """处理所有模块的位选节点"""
        # Phase 1: 提取所有模块的信号位宽
        self._extract_all_widths()
        
        # Phase 2: 处理位选节点
        self._create_hierarchical_bit_nodes()
    
    def _extract_all_widths(self):
        """提取所有模块中所有信号声明的位宽"""
        for module in self.adapter.get_modules():
            module_name = self.adapter.get_module_name(module)
            
            # 提取 Port 位宽
            for port_decl in self.adapter.get_port_declarations(module):
                port_name = self.adapter.get_port_name(port_decl)
                if port_name:
                    port_name = self.adapter.clean_name(port_name)
                    width = self.adapter.extract_port_width(port_decl)
                    self.signal_widths[f"{module_name}.{port_name}"] = width
            
            # 提取 Internal Signal 位宽
            for data_decl in self.adapter.get_data_declarations(module):
                decl_names = self._get_data_decl_names(data_decl)
                width = self.adapter.extract_data_width(data_decl)
                for name in decl_names:
                    full_name = f"{module_name}.{name}"
                    self.signal_widths[full_name] = width
                    
                    # 确保节点存在 (声明的信号都应该在图中)
                    if full_name not in self.graph.nodes():
                        name = name  # 信号名
                        module = module_name  # 模块名
                        from trace.core.graph_models import TraceNode, NodeKind
                        node = TraceNode(
                            id=full_name,
                            name=name,
                            module=module,
                            kind=NodeKind.SIGNAL,
                            width=width,
                        )
                        self.graph.add_trace_node(node)
                    else:
                        # 更新已存在节点的宽度
                        node = self.graph.get_node(full_name)
                        if node:
                            node.width = width
    
    def _get_data_decl_names(self, data_decl) -> List[str]:
        """从 DataDeclaration 提取所有声明的信号名
        
        处理 multi-declarator: logic [7:0] a, b, c;
        Returns: ['a', 'b', 'c']
        """
        names = []
        declarators = getattr(data_decl, 'declarators', None)
        if not declarators:
            return names
        
        for decl in declarators:
            decl_str = str(decl).strip()
            # 跳过逗号等分隔符
            if decl_str == ',':
                continue
            # 检查是否是 NamedObject
            if hasattr(decl, 'name'):
                name_obj = decl.name
                if hasattr(name_obj, 'value'):
                    name = name_obj.value
                elif hasattr(name_obj, 'text'):
                    name = name_obj.text
                else:
                    name = str(name_obj).strip()
            else:
                # 直接从字符串提取 (multi-declarator 情况)
                name = decl_str.split('[')[0].split('=')[0].strip()
            
            if name and name not in [',', '']:
                names.append(name)
        
        return names
    
    def _create_hierarchical_bit_nodes(self):
        """为位选节点创建父子关系和属性
        
        - 识别 data[3:0] 形式的节点
        - 解析位选择范围
        - 设置 bit_range, parent_bit_start, parent_bit_end
        - 创建 BIT_SELECT 边
        """
        # 找到所有位选节点 (包含 [ 且包含 ] 但不包含 ['][)
        child_ids = []
        for nid in list(self.graph.nodes()):
            if '[' in nid and ']' in nid:
                # 排除数组访问格式 like signal[0] (可能是数组下标，不是位选)
                # 位选格式: data[3:0], data[7:4], data[msb:lsb]
                # 数组下标: arr[0], arr[i] (没有冒号)
                match = re.match(r'^([^\[]+)\[(\d+):(\d+)\]$', nid)
                if match:
                    child_ids.append((nid, match.group(1), match.group(2), match.group(3)))
        
        for child_id, parent_name, msb_str, lsb_str in child_ids:
            msb = int(msb_str)
            lsb = int(lsb_str)
            
            # 构造完整父节点 ID
            # parent_name 已经是完整路径 (从正则捕获的)，直接使用
            # child_id 格式: "top.data[3:0]" → parent_name = "top.data"
            parent_id = parent_name
            
            # 确保父节点存在
            if parent_id not in self.graph.nodes():
                # 从 signal_widths 获取或创建默认节点
                parent_width = self.signal_widths.get(parent_id, (1, 0))
                # 提取 module: parent_id = "top.data" → module = "top", name = "data"
                module = parent_id.rsplit('.', 1)[0] if '.' in parent_id else ''
                name = parent_id.rsplit('.', 1)[-1] if '.' in parent_id else parent_id
                from trace.core.graph_models import TraceNode, NodeKind
                parent_node = TraceNode(
                    id=parent_id,
                    name=name,
                    module=module,
                    kind=NodeKind.SIGNAL,
                    width=parent_width,
                )
                self.graph.add_trace_node(parent_node)
            
            # 更新子节点的属性
            child_node = self.graph.get_node(child_id)
            if child_node:
                # 设置 bit_range
                child_node.bit_range = f"[{msb}:{lsb}]"
                
                # 设置父节点信息
                child_node.parent = parent_id
                
                # 设置在父节点中的起止位置
                # parent_bit_start 是 LSB 侧 (值小的)
                # parent_bit_end 是 MSB 侧 (值大的)
                child_node.parent_bit_start = min(msb, lsb)
                child_node.parent_bit_end = max(msb, lsb)
                
                # 更新宽度为位选范围
                child_node.width = (max(msb, lsb), min(msb, lsb))
                
                # 确保有 kind
                if child_node.kind is None:
                    child_node.kind = NodeKind.SIGNAL
            
            # 创建 BIT_SELECT 边
            from trace.core.graph_models import TraceEdge, EdgeKind
            agg_edge = TraceEdge(
                src=child_id,
                dst=parent_id,
                kind=EdgeKind.BIT_SELECT,
            )
            self.graph.add_trace_edge(agg_edge)
    
    def get_signal_width(self, signal_id: str) -> Tuple[int, int]:
        """获取信号的位宽
        
        Args:
            signal_id: 信号 ID，如 "top.data"
            
        Returns:
            (msb, lsb) 元组
        """
        return self.signal_widths.get(signal_id, (1, 0))