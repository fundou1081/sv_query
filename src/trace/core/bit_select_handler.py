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

# [2026-08-28 #2 G3 Option3 收尾] 模块级 `import re` 已删:
#   位选解析改用 pyslang semantic API (_common.iter_bit_selects), 不再 regex 反推节点 ID。
#   Phase 3 的 constraint 字符串扫描 (_scan_constraint_bit_selects) 自带函数内 import re,
#   那是对 constraint 表达式**文本**做模式提取, 不是对 AST 结构反推, 属合理用法。

import logging

from trace.core.base import PyslangAdapter

logger = logging.getLogger(__name__)


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

    def process(self) -> None:
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
        # [FIX 2026-06-26] pyslang binary garbage in cls.name
        for cls in self.adapter.get_classes():
            cls_name = ""
            try:
                raw_name = getattr(cls, "name", None)
                if raw_name:
                    cls_name = raw_name.value if hasattr(raw_name, "value") else str(raw_name).strip()
            except (UnicodeDecodeError, TypeError):
                continue
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
                except (ValueError, TypeError) as _e:
                    logger.debug("位宽 int 转换失败: %s", _e)
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
            except (ValueError, TypeError) as _e:
                logger.debug("位宽 int 转换失败: %s", _e)
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
        # [FIX 2026-06-26] pyslang binary garbage in cls.name
        for cls in self.adapter.get_classes():
            cls_name = ""
            try:
                raw_name = getattr(cls, "name", None)
                if raw_name:
                    cls_name = raw_name.value if hasattr(raw_name, "value") else str(raw_name).strip()
            except (UnicodeDecodeError, TypeError):
                continue
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

        - 用 pyslang semantic API 识别 RangeSelect (`data[3:0]`) 位选
        - 设置 bit_range, parent, parent_bit_start, parent_bit_end, width
        - 创建 BIT_SELECT 边

        [ARCHITECTURE_TODOLIST #2 G3 Option 3 收尾 2026-08-28]
        原实现用 regex `^([^\\[]+)\\[(\\d+):(\\d+)\\]$` 反推节点 ID 字符串, 与路径 B
        (`graph_builder._create_hierarchical_bit_nodes`) 并行且同样脆弱。本次改为复用
        与路径 B **同一个** semantic helper (`_common.iter_bit_selects`), 彻底消除
        本文件的 regex 位选解析, 完成 G3 选项 3 的另一半。

        与路径 B 的分工保持不变 (职责不同, 非重复实现):
        - 本方法 (路径 A): 依赖 `self.signal_widths` 补建缺失父节点, 供 unified_tracer
          在 class_builder 之后调用
        - 路径 B: GraphBuilder.build() 内部调用, 走 base_chain 建多级边

        注意: 只处理 RangeSelect (`[msb:lsb]`)。ElementSelect (`data[0]`) 维持原
        regex 实现的行为 —— 原正则要求 `(\\d+):(\\d+)` 冒号形式, 从不匹配单下标,
        这是**刻意保留的语义**, 不是遗漏 (见类 docstring: 数组下标不是位选)。
        """
        from trace.core.extractors._common import iter_bit_selects
        from trace.core.graph.models import EdgeKind, NodeKind, TraceEdge, TraceNode

        pyslang_root = self._get_pyslang_root()

        # 收集 (child_id, parent_id, msb, lsb) —— 语义遍历替代 regex
        found: list[tuple[str, str, int, int]] = []
        for i in range(len(pyslang_root.topInstances)):
            mod = pyslang_root.topInstances[i]
            instance_path = mod.name or ''
            for hit in iter_bit_selects(mod, instance_path=instance_path):
                if hit.select_kind != 'RangeSelect':
                    continue
                # msb/lsb 无法折叠成常量 (如 `data[i]` 符号下标) 时跳过:
                # 原 regex `(\d+):(\d+)` 同样只接受字面量, 行为对齐。
                if hit.msb is None or hit.lsb is None:
                    continue
                if not hit.base_chain:
                    continue
                found.append((hit.full_id, hit.base_chain[-2] if len(hit.base_chain) >= 2
                              else hit.base_chain[0], hit.msb, hit.lsb))

        for child_id, parent_id, msb, lsb in found:
            # 只处理图中已存在的位选节点 (与原 regex 实现一致: 它遍历 self.graph.nodes())
            if child_id not in self.graph.nodes():
                continue

            # 确保父节点存在
            if parent_id not in self.graph.nodes():
                parent_width = self.signal_widths.get(parent_id, (1, 0))
                module = parent_id.rsplit(".", 1)[0] if "." in parent_id else ""
                name = parent_id.rsplit(".", 1)[-1] if "." in parent_id else parent_id

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
                child_node.bit_range = f"[{msb}:{lsb}]"
                child_node.parent = parent_id
                # parent_bit_start 是 LSB 侧 (值小的), parent_bit_end 是 MSB 侧 (值大的)
                child_node.parent_bit_start = min(msb, lsb)
                child_node.parent_bit_end = max(msb, lsb)
                child_node.width = (max(msb, lsb), min(msb, lsb))

                if child_node.kind is None:
                    child_node.kind = NodeKind.SIGNAL

            # 创建 BIT_SELECT 边
            agg_edge = TraceEdge(
                src=child_id,
                dst=parent_id,
                kind=EdgeKind.BIT_SELECT,
            )
            self.graph.add_trace_edge(agg_edge)

    def _get_pyslang_root(self):
        """取 pyslang semantic root。

        Raises:
            ValueError: adapter 拿不到 root。BitSelectHandler 恒由 unified_tracer 传入
                SemanticAdapter (其 __init__ 必设 _root), 故取不到只可能是调用方传错
                adapter 类型。依 AGENTS.md 纪律 #2, 显式报错而非静默跳过位选处理。
        """
        adapter_root = getattr(self.adapter, '_root', None)
        if adapter_root is not None:
            if hasattr(adapter_root, 'get_root'):
                return adapter_root.get_root()
            if hasattr(adapter_root, 'topInstances'):
                return adapter_root
        raise ValueError(
            f"BitSelectHandler: 无法从 adapter ({type(self.adapter).__name__}) 取得 "
            "pyslang root。位选处理需要 semantic root; 静默跳过会让 BIT_SELECT 边缺失。"
        )

    def get_signal_width(self, signal_id: str) -> tuple[int, int]:
        """获取信号的位宽

        Args:
            signal_id: 信号 ID，如 "top.data"

        Returns:
            (msb, lsb) 元组
        """
        return self.signal_widths.get(signal_id, (1, 0))
