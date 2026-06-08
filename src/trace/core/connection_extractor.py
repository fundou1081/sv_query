# ==============================================================================
# connection_extractor.py - Connection 提取器 (从 graph_builder.py 物理拆分, P1 cycle 9b)
#
# 职责: 解析 SV 模块实例化, 提取端口到内部信号的连接 (CONNECTION) 关系.
# ==============================================================================

import logging

from .base import PyslangAdapter
from .extractor_models import ExtractorResult
from .graph.models import EdgeKind, NodeKind, TraceEdge, TraceNode

logger = logging.getLogger(__name__)


class ConnectionExtractor:
    def __init__(self, adapter: PyslangAdapter):
        self.adapter = adapter
        self.root_module_name = None

    def _get_parent_module_name(self, inst) -> str:
        """Safely get parent module name from instance (handles generate blocks)."""
        node = inst
        for _ in range(5):
            if not hasattr(node, "parent") or node.parent is None:
                break
            node = node.parent
            if type(node).__name__ == "ModuleDeclarationSyntax":
                if hasattr(node, "header") and hasattr(node.header, "name"):
                    return node.header.name.rawText.strip()
                elif hasattr(node, "name"):
                    return node.name.rawText.strip()
        # Fallback: use parent_module if it's a string (actual parent module name)
        # For top-level instances (parent_module is None), return '__root__'
        if hasattr(inst, "parent_module"):
            if inst.parent_module is None:
                return "__root__"
            if isinstance(inst.parent_module, str) and inst.parent_module:
                return inst.parent_module
        # Fallback to type.value or inst_name
        if hasattr(inst, "type") and hasattr(inst.type, "value") and inst.type.value:
            return inst.type.value
        return getattr(inst, "name", "unknown") or "unknown"

    def _get_generate_block_name(self, inst) -> str:
        """Get the generate block label if instance is inside a generate block."""
        # First try parent chain (works for SyntaxTree)
        node = inst
        for _ in range(5):
            if not hasattr(node, "parent") or node.parent is None:
                break
            node = node.parent
            if type(node).__name__ == "GenerateBlockSyntax":
                if hasattr(node, "beginName") and node.beginName:
                    bn = node.beginName
                    if hasattr(bn, "name") and hasattr(bn.name, "value"):
                        return bn.name.value.strip()

        # [FIX] Fallback: try to extract genblock name from hierarchicalPath
        # For SemanticAdapter instances with hierarchicalPath like 'top.gen[0].u_dut'
        if hasattr(inst, "_symbol"):
            hp = getattr(inst._symbol, "hierarchicalPath", None)
            if hp:
                hp_str = str(hp)
                # Pattern: top.GEN[INDEX].instance -> extract GEN
                # Look for pattern like .gen[ or .GEN[
                import re

                match = re.search(r"\.([a-zA-Z_][a-zA-Z0-9_]*)\[[0-9]+\]", hp_str)
                if match:
                    return match.group(1)

        return None

    def _missing_module_warning(self, inst_module_name: str, inst_name: str):
        """输出可能缺少文件的警告信息"""
        import logging

        logger = logging.getLogger("sv_query")
        msg = (
            f"[sv_query] 可能缺少文件: 实例 '{inst_name}' 的模块 '{inst_module_name}' "
            f"没有找到端口定义。\n"
            f"  → 可能原因: 解析的文件范围不完整,缺少 '{inst_module_name}' 的定义文件\n"
            f"  → 建议: 确保传入所有相关的 Verilog 文件,或使用 glob 模式匹配整个目录\n"
            f"  → 例如: sv_query 'path/to/**/*.v' (递归) 或 sv_query 'file1.v file2.v' (多文件)"
        )
        logger.warning(msg)
        # 同时记录到 ExtractorResult.warnings 中
        if not hasattr(self, "_warnings"):
            self._warnings = []
        self._warnings.append(f"Missing module: {inst_module_name} (instance: {inst_name})")

    def extract(self) -> ExtractorResult:
        result = ExtractorResult()

        # [FIX Issue 20] 初始化 warnings 列表
        self._warnings = []

        # [FIX Issue 19] 动态获取根模块名而非硬编码 "top"
        # 优先从 trees 的键中获取根模块名(trees 包含当前处理的文件),
        # 如果没有则使用第一个模块
        if self.root_module_name is None:
            trees = getattr(self.adapter.parser, "trees", {})
            if trees:
                # trees 的键是 tree 文件的键,不一定等于实际模块名
                # 需要验证该键是否对应实际模块,否则使用实际模块名
                tree_key = list(trees.keys())[0]
                actual_modules = [self.adapter.get_module_name(m) for m in self.adapter.get_modules()]
                if tree_key in actual_modules:
                    self.root_module_name = tree_key
                else:
                    # tree key 与实际模块名不匹配,查找包含实例的模块
                    # 找到没有被其他模块实例化的模块(顶层模块)
                    instances = self.adapter.get_module_instances() + self.adapter.get_generate_instances()

                    # 收集所有被实例化的模块名
                    instantiated_modules = set()
                    for inst in instances:
                        if hasattr(inst, "type") and hasattr(inst.type, "value"):
                            instantiated_modules.add(inst.type.value.strip())

                    # 找到没有被实例化的模块(顶层模块)
                    for mod in self.adapter.get_modules():
                        mod_name = self.adapter.get_module_name(mod)
                        if mod_name not in instantiated_modules:
                            self.root_module_name = mod_name
                            break

                    # 如果没找到,使用第一个实际模块
                    if self.root_module_name is None:
                        self.root_module_name = actual_modules[0] if actual_modules else tree_key
            else:
                for mod in self.adapter.get_modules():
                    self.root_module_name = self.adapter.get_module_name(mod)
                    break

        trees = getattr(self.adapter.parser, "trees", {})
        instances = self.adapter.get_module_instances() + self.adapter.get_generate_instances()

        # 收集所有模块的端口定义 (方向和位宽)
        all_module_ports = {}
        all_module_widths = {}
        for module in self.adapter.get_modules():
            module_name = self.adapter.get_module_name(module)
            port_dirs = {}
            port_widths = {}
            for port in self.adapter.get_port_declarations(module):
                name, direction = self.adapter.get_port_name_and_direction(port)
                port_dirs[name] = direction.strip()
                # 获取位宽 (传入 module 作为 scope 以解析参数)
                width = self.adapter.extract_port_width(port, scope=module)
                # extract_port_width with scope returns dict, convert to tuple for compatibility
                if isinstance(width, dict):
                    msb = width.get("msb_eval", width.get("msb_raw", 0))
                    lsb = width.get("lsb_eval", width.get("lsb_raw", 0))
                    try:
                        msb = int(msb) if msb is not None else 0
                    except (ValueError, TypeError):
                        msb = 0
                    try:
                        lsb = int(lsb) if lsb is not None else 0
                    except (ValueError, TypeError):
                        lsb = 0
                    width = (msb, lsb)
                port_widths[name] = width
            all_module_ports[module_name] = port_dirs
            all_module_widths[module_name] = port_widths

        # [FIX] 第一阶段:收集所有实例信息
        instances_info = []  # [(inst_module_name, inst_name, parent_module)]

        for inst in instances:
            inst_name = (
                inst.instances[0].decl.name.value.strip()
                if hasattr(inst.instances[0], "decl")
                and hasattr(inst.instances[0].decl, "name")
                and inst.instances[0].decl.name.value
                else str(inst).split("(")[0].strip()
            )

            inst_type_value = inst.type.value.strip() if hasattr(inst.type, "value") and inst.type.value else ""
            inst_module_name = (
                inst_type_value
                if inst_type_value and inst_type_value != inst_name
                else self._get_parent_module_name(inst)
            )
            parent_module = self._get_parent_module_name(inst)

            gen_block = self._get_generate_block_name(inst)
            instances_info.append(
                {
                    "inst_module_name": inst_module_name,
                    "inst_name": inst_name,
                    "parent_module": parent_module,
                    "gen_block": gen_block,
                }
            )

        # [FIX] 第二阶段:构建模块 -> 实例路径的映射
        module_to_path = {}  # (inst_module_name, inst_name) -> full_path

        # 递归确定路径
        def get_path(info, depth=0):
            """递归获取实例的完整路径"""
            if depth > 20:
                return f"{self.root_module_name}.{info['inst_name']}"
            parent_mod = info["parent_module"]
            gen_block = info.get("gen_block")

            # Handle '__root__' specially - instance is at top level
            if parent_mod == "__root__":
                if gen_block:
                    return f"{self.root_module_name}.{gen_block}.{info['inst_name']}"
                # Special case: if inst_module_name is also '__root__',
                # this instance IS the root module (not a sub-instance)
                if info["inst_module_name"] == "__root__":
                    return info["inst_name"]
                return f"{self.root_module_name}.{info['inst_name']}"
            elif parent_mod == "top":
                if gen_block:
                    return f"{self.root_module_name}.{gen_block}.{info['inst_name']}"
                return f"{self.root_module_name}.{info['inst_name']}"
            else:
                # parent_mod is not in instances_info
                # Determine if it's a top-level module (use parent_mod as prefix)
                # or a submodule of root (use root_module_name as prefix)
                #
                # Heuristic: if parent_mod appears as inst_module_name in instances_info,
                # then it's a submodule (instances of it exist elsewhere), use root_module_name.
                # Otherwise, it's a top-level module, use parent_mod as prefix.
                parent_is_submodule_of_root = any(
                    info["inst_module_name"] == parent_mod for info in instances_info
                )
                if not parent_is_submodule_of_root:
                    # parent_mod is a top-level module, not in instances_info
                    # Use parent_mod as the path prefix (this fixes wrong root_module_name fallback)
                    if gen_block:
                        return f"{parent_mod}.{gen_block}.{info['inst_name']}"
                    return f"{parent_mod}.{info['inst_name']}"
                # parent_mod is a submodule of root, use root_module_name fallback
                for other_info in instances_info:
                    if other_info["inst_module_name"] == parent_mod:
                        parent_path = get_path(other_info, depth + 1)
                        if gen_block:
                            return f"{parent_path}.{gen_block}.{info['inst_name']}"
                        return f"{parent_path}.{info['inst_name']}"
                # Fallback (should not reach here if parent_is_submodule_of_root check works)
                if gen_block:
                    return f"{self.root_module_name}.{gen_block}.{info['inst_name']}"
                return f"{self.root_module_name}.{info['inst_name']}"

        for info in instances_info:
            path = get_path(info)
            gen_block = info.get("gen_block")
            if gen_block:
                key = (info["inst_module_name"], info["inst_name"], gen_block)
            else:
                key = (info["inst_module_name"], info["inst_name"])
            module_to_path[key] = path

        # [FIX] 第三阶段:使用正确路径创建节点和边
        for inst in instances:
            inst_name = (
                inst.instances[0].decl.name.value.strip()
                if hasattr(inst.instances[0], "decl")
                and hasattr(inst.instances[0].decl, "name")
                and inst.instances[0].decl.name.value
                else str(inst).split("(")[0].strip()
            )

            inst_type_value = inst.type.value.strip() if hasattr(inst.type, "value") and inst.type.value else ""
            inst_module_name = (
                inst_type_value
                if inst_type_value and inst_type_value != inst_name
                else self._get_parent_module_name(inst)
            )

            gen_block = self._get_generate_block_name(inst)
            if gen_block:
                key = (inst_module_name, inst_name, gen_block)
                inst_path = module_to_path.get(key, f"{self.root_module_name}.{gen_block}.{inst_name}")
            else:
                key = (inst_module_name, inst_name)
                inst_path = module_to_path.get(key, f"{self.root_module_name}.{inst_name}")

            # [DEBUG] Trace inst_path and module_to_path state

            inst_path = module_to_path.get(key, f"{self.root_module_name}.{inst_name}")

            module_ports = all_module_ports.get(inst_module_name, {})
            conns = self.adapter.get_instance_connection(inst)

            # [FIX Issue 20] 检测可能缺少文件的情况
            if not module_ports and conns:
                # 实例有连接但模块没有端口定义,可能是缺少了实例模块的文件
                self._missing_module_warning(inst_module_name, inst_name)

            named_conns = {}
            positional_conns = []

            for port_key, signal_name in conns:
                if port_key.startswith("_pos_"):
                    idx = int(port_key.replace("_pos_", ""))
                    positional_conns.append((idx, signal_name))
                else:
                    named_conns[port_key] = signal_name

            positional_conns.sort(key=lambda x: x[0])
            port_names = list(module_ports.keys())

            for idx, signal_name in positional_conns:
                if idx < len(port_names):
                    port_name = port_names[idx]
                    named_conns[port_name] = signal_name

            # 如果在 generate block 中,创建 generate block 容器节点
            if gen_block:
                gen_path = inst_path.rsplit(".", 1)[0]  # e.g., top.GEN from top.GEN.g
                gen_module = (
                    ".".join(gen_path.rsplit(".", 1)[:-1]) or gen_path.rsplit(".", 1)[0]
                )  # e.g., top from top.GEN
                # 检查是否已经存在
                if not any(n.id == gen_path for n in result.nodes):
                    result.nodes.append(
                        TraceNode(
                            id=gen_path,
                            name=gen_block,
                            module=gen_module,
                            kind=NodeKind.GENERATE_BLOCK
                            if hasattr(NodeKind, "GENERATE_BLOCK")
                            else NodeKind.INSTANTIATED_MODULE,
                            width=(1, 0),
                            is_port=False,
                        )
                    )

            # 创建实例父节点
            result.nodes.append(
                TraceNode(
                    id=inst_path,
                    name=inst_name,
                    module=inst_path.rsplit(".", 1)[0] if "." in inst_path else "top",
                    kind=NodeKind.INSTANTIATED_MODULE,
                    width=(1, 0),
                    is_port=False,
                )
            )

            # 为每个端口创建节点和边
            for port_name, signal_name in named_conns.items():
                port_name = self.adapter.clean_name(port_name)
                signal_name = self.adapter.clean_name(signal_name)

                direction = module_ports.get(port_name, "unknown").strip()

                inst_port_id = f"{inst_path}.{port_name}"
                if "inout" in direction.lower():
                    kind = NodeKind.PORT_INOUT
                elif "output" in direction.lower():
                    kind = NodeKind.PORT_OUT
                else:
                    kind = NodeKind.PORT_IN
                # 获取端口位宽
                port_widths = all_module_widths.get(inst_module_name, {})
                width = port_widths.get(port_name, (1, 0))

                # [NEW] 如果位宽为 (0,0),尝试从父模块的信号宽度推断
                if width == (0, 0) and signal_name:
                    parent_path = inst_path.rsplit(".", 1)[0] if "." in inst_path else "top"
                    parent_widths = all_module_widths.get(parent_path, {})
                    if signal_name in parent_widths:
                        width = parent_widths[signal_name]

                result.nodes.append(
                    TraceNode(
                        id=inst_port_id,
                        name=port_name,
                        module=inst_path,
                        kind=kind,
                        width=width if width != (0, 0) else (1, 0),
                        is_port=True,
                    )
                )

                direction_clean = direction.strip()
                parent_path = inst_path.rsplit(".", 1)[0] if "." in inst_path else "top"

                if direction_clean == "input":
                    result.edges.append(
                        TraceEdge(
                            src=f"{parent_path}.{signal_name}",
                            dst=inst_port_id,
                            kind=EdgeKind.CONNECTION,
                            assign_type="connection",
                        )
                    )
                    child_signal_id = f"{inst_module_name}.{port_name}"
                    result.edges.append(
                        TraceEdge(
                            src=inst_port_id, dst=child_signal_id, kind=EdgeKind.CONNECTION, assign_type="internal"
                        )
                    )
                    # 同步构建 port_to_internal 映射
                    result.port_to_internal[inst_port_id] = child_signal_id
                elif direction_clean == "output":
                    # 输出端口: 子模块输出端口驱动实例端口
                    # 连接关系: child.data (child output) -> top.u_driver.data (instance port) -> top.data (parent wire)
                    # 边1: child output -> instance port (DRIVER)
                    # 边2: instance port -> parent wire (CONNECTION)
                    child_signal_id = f"{inst_module_name}.{port_name}"
                    parent_signal = f"{parent_path}.{signal_name}"
                    # 边1: child output -> instance port (DRIVER)
                    result.edges.append(
                        TraceEdge(src=child_signal_id, dst=inst_port_id, kind=EdgeKind.DRIVER, assign_type="internal")
                    )
                    # 边2: instance port -> parent wire (CONNECTION)
                    result.edges.append(
                        TraceEdge(
                            src=inst_port_id, dst=parent_signal, kind=EdgeKind.CONNECTION, assign_type="connection"
                        )
                    )
                    result.port_to_internal[inst_port_id] = child_signal_id

        # [FIX] 后处理:修复实例端口的位宽
        # 如果实例端口位宽为默认值(1,0),尝试从连接推断实际位宽
        for edge in result.edges:
            if edge.kind != EdgeKind.CONNECTION:
                continue

            # 找 src 是外部信号,dst 是实例端口的情况
            src_node = None
            dst_node = None
            for node in result.nodes:
                if node.id == edge.src:
                    src_node = node
                if node.id == edge.dst:
                    dst_node = node

            if src_node and dst_node:
                # dst 是实例端口吗?
                # 实例端口格式: path.inst.port
                parts = dst_node.id.split(".")
                if len(parts) >= 3 and dst_node.kind.name.startswith("PORT_"):
                    # 如果 dst 的位宽是默认值(1,0)且 src 有有效位宽,使用 src 的位宽
                    if dst_node.width == (1, 0) and src_node.width != (0, 0):
                        # 找到 dst_node 并更新
                        for i, n in enumerate(result.nodes):
                            if n.id == dst_node.id:
                                # 创建新的 TraceNode with correct width
                                result.nodes[i] = TraceNode(
                                    id=n.id,
                                    name=n.name,
                                    module=n.module,
                                    kind=n.kind,
                                    width=src_node.width,
                                    is_port=n.is_port,
                                )
                                break

        # [FIX Issue 20] 将警告信息添加到 result
        if hasattr(self, "_warnings") and self._warnings:
            result.warnings = self._warnings

        return result


