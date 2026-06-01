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
        self.signal_widths: dict[str, tuple[int, int]] = {}  # 信号名 → (msb, lsb)

    def process(self):
        """处理所有模块的位选节点"""
        # Phase 1: 提取所有模块的信号位宽
        self._extract_all_widths()

        # Phase 2: 处理位选节点
        self._create_hierarchical_bit_nodes()

        # Phase 3: 扫描 constraint 中的位选引用
        self._scan_constraint_bit_selects()

    def _extract_all_widths(self):
        """提取所有模块和类中所有信号声明的位宽"""

        # === 处理 Module 中的信号 ===
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
                        from trace.core.graph.models import NodeKind, TraceNode

                        node = TraceNode(
                            id=full_name,
                            name=name,
                            module=module_name,
                            kind=NodeKind.SIGNAL,
                            width=width,
                        )
                        self.graph.add_trace_node(node)
                    else:
                        # 更新已存在节点的宽度
                        node = self.graph.get_node(full_name)
                        if node:
                            node.width = width

        # === 处理 Class 中的属性 ===
        for cls in self.adapter.get_classes():
            cls_name = getattr(cls, "name", None)
            if cls_name:
                cls_name = cls_name.value if hasattr(cls_name, "value") else str(cls_name).strip()
            if not cls_name:
                continue

            # 遍历 ClassPropertyDeclaration
            for item in getattr(cls, "items", []):
                kind_str = str(getattr(item, "kind", ""))
                if "ClassPropertyDeclaration" in kind_str:
                    # 提取属性名和位宽
                    decl = getattr(item, "declaration", None)
                    if decl:
                        prop_name = getattr(decl, "name", None)
                        if prop_name:
                            prop_name = prop_name.value if hasattr(prop_name, "value") else str(prop_name).strip()

                        # 提取位宽
                        width = (0, 0)
                        type_node = getattr(decl, "type", None)
                        if type_node:
                            dims = getattr(type_node, "dimensions", None)
                            if dims:
                                for dim in dims:
                                    if hasattr(dim, "kind") and str(dim.kind) == "SyntaxKind.VariableDimension":
                                        spec = getattr(dim, "specifier", None)
                                        if spec and hasattr(spec, "selector"):
                                            sel = spec.selector
                                            msb = self._extract_int_value(getattr(sel, "left", None))
                                            lsb = self._extract_int_value(getattr(sel, "right", None))
                                            width = (msb, lsb)
                                            break

                        if prop_name:
                            full_name = f"{cls_name}.{prop_name}"
                            self.signal_widths[full_name] = width

                            # 确保节点存在
                            if full_name not in self.graph.nodes():
                                from trace.core.graph.models import NodeKind, TraceNode

                                node = TraceNode(
                                    id=full_name,
                                    name=prop_name,
                                    module=cls_name,
                                    kind=NodeKind.CLASS_PROPERTY,
                                    width=width,
                                )
                                self.graph.add_trace_node(node)
                            else:
                                node = self.graph.get_node(full_name)
                                if node:
                                    node.width = width

    def _extract_int_value(self, expr) -> int:
        """从表达式中提取整数值"""
        if expr is None:
            return 0
        # LiteralExpressionSyntax: expr.literal.valueText
        if hasattr(expr, "literal"):
            lit = expr.literal
            if hasattr(lit, "valueText"):
                try:
                    return int(lit.valueText)
                except (ValueError, TypeError):
                    pass
        # 直接的值属性
        if hasattr(expr, "value"):
            v = expr.value
            if isinstance(v, (int, float)):
                return int(v)
        # text 属性
        if hasattr(expr, "text"):
            try:
                return int(expr.text)
            except (ValueError, TypeError):
                pass
        return 0

    def _get_data_decl_names(self, data_decl) -> list[str]:
        """从 DataDeclaration 提取所有声明的信号名

        处理 multi-declarator: logic [7:0] a, b, c;
        Returns: ['a', 'b', 'c']
        """
        names = []
        declarators = getattr(data_decl, "declarators", None)
        if not declarators:
            return names

        for decl in declarators:
            decl_str = str(decl).strip()
            # 跳过逗号等分隔符
            if decl_str == ",":
                continue
            # 检查是否是 NamedObject
            if hasattr(decl, "name"):
                name_obj = decl.name
                if hasattr(name_obj, "value"):
                    name = name_obj.value
                elif hasattr(name_obj, "text"):
                    name = name_obj.text
                else:
                    name = str(name_obj).strip()
            else:
                # 直接从字符串提取 (multi-declarator 情况)
                name = decl_str.split("[")[0].split("=")[0].strip()

            if name and name not in [",", ""]:
                names.append(name)

        return names

    def _scan_constraint_bit_selects(self):
        """扫描 constraint 表达式中的位选引用

        处理类似 constraint c1 { data[7:4] == 4'hF; } 中的位选
        从 constraint 表达式字符串中提取 bit select 模式并创建节点
        """
        import re

        # 遍历所有类
        for cls in self.adapter.get_classes():
            cls_name = getattr(cls, "name", None)
            if cls_name:
                cls_name = cls_name.value if hasattr(cls_name, "value") else str(cls_name).strip()
            if not cls_name:
                continue

            # 遍历 constraint blocks
            for item in getattr(cls, "items", []):
                kind_str = str(getattr(item, "kind", ""))
                if "ConstraintDeclaration" not in kind_str:
                    continue

                # 获取 constraint block 内容
                block = getattr(item, "block", None)
                if not block or not hasattr(block, "items") or not block.items:
                    continue

                # 遍历 block 中的 constraint items
                for block_item in block.items:
                    item_str = str(block_item).strip()

                    # 查找位选模式: identifier[msb:lsb]
                    pattern = r"(\w+)\[(\d+):(\d+)\]"
                    matches = re.findall(pattern, item_str)

                    for base_name, msb_str, lsb_str in matches:
                        msb = int(msb_str)
                        lsb = int(lsb_str)

                        # 构造 bit select 节点 ID
                        bit_select_id = f"{cls_name}.{base_name}[{msb}:{lsb}]"
                        parent_id = f"{cls_name}.{base_name}"

                        # 检查父节点是否存在
                        parent_node = self.graph.get_node(parent_id)
                        if not parent_node:
                            # 父节点不存在，跳过
                            continue

                        # 确保 bit select 节点存在
                        if bit_select_id not in self.graph.nodes():
                            from trace.core.graph.models import NodeKind, TraceNode

                            node = TraceNode(
                                id=bit_select_id,
                                name=f"{base_name}[{msb}:{lsb}]",
                                module=cls_name,
                                kind=NodeKind.CONSTRAINT_EXPR,  # bit select in constraint context
                                width=(max(msb, lsb), min(msb, lsb)),
                                bit_range=f"[{msb}:{lsb}]",
                                parent=parent_id,
                                parent_bit_start=min(msb, lsb),
                                parent_bit_end=max(msb, lsb),
                            )
                            self.graph.add_trace_node(node)

                        # 创建 BIT_SELECT 边
                        existing_edge = self.graph.get_edge(bit_select_id, parent_id)
                        if not existing_edge:
                            from trace.core.graph.models import EdgeKind, TraceEdge

                            edge = TraceEdge(
                                src=bit_select_id,
                                dst=parent_id,
                                kind=EdgeKind.BIT_SELECT,
                            )
                            self.graph.add_trace_edge(edge)

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
            if "[" in nid and "]" in nid:
                # 排除数组访问格式 like signal[0] (可能是数组下标，不是位选)
                # 位选格式: data[3:0], data[7:4], data[msb:lsb]
                # 数组下标: arr[0], arr[i] (没有冒号)
                match = re.match(r"^([^\[]+)\[(\d+):(\d+)\]$", nid)
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
                module = parent_id.rsplit(".", 1)[0] if "." in parent_id else ""
                name = parent_id.rsplit(".", 1)[-1] if "." in parent_id else parent_id
                from trace.core.graph.models import NodeKind, TraceNode

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
            from trace.core.graph.models import EdgeKind, TraceEdge

            agg_edge = TraceEdge(
                src=child_id,
                dst=parent_id,
                kind=EdgeKind.BIT_SELECT,
            )
            self.graph.add_trace_edge(agg_edge)

    def get_signal_width(self, signal_id: str) -> tuple[int, int]:
        """获取信号的位宽

        Args:
            signal_id: 信号 ID，如 "top.data"

        Returns:
            (msb, lsb) 元组
        """
        return self.signal_widths.get(signal_id, (1, 0))
