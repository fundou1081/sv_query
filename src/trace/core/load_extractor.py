# ==============================================================================
# load_extractor.py - Load 提取器 (从 graph_builder.py 物理拆分, P1 cycle 9)
#
# 职责: 解析 SV 模块端口, 提取端口连接 (load) 关系.
# ==============================================================================

import logging

from .._safe import safe_attr, safe_str, safe_str  # [iter_182]

import pyslang

from .semantic_adapter import SemanticAdapter
from .extractor_models import ExtractorResult  # [P1 cycle 9] 共享
from .graph.models import NodeKind, TraceNode

logger = logging.getLogger(__name__)


class LoadExtractor:
    def __init__(self, adapter: SemanticAdapter):
        self.adapter = adapter

    def extract(self) -> ExtractorResult:
        result = ExtractorResult()

        for module in self.adapter.get_modules():
            module_name = self.adapter.get_module_name(module)

            # [铁律4] 为端口创建 TraceNode (根据方向创建正确的 kind)
            port_decls = self.adapter.get_port_declarations(module)
            for port_decl in port_decls:
                port_name, direction = self.adapter.get_port_name_and_direction(port_decl)
                if not port_name:
                    continue
                port_name = self.adapter.clean_name(port_name)
                port_id = f"{module_name}.{port_name}"
                if port_id not in [n.id for n in result.nodes]:
                    # 根据方向确定 kind
                    if "inout" in direction.lower():
                        kind = NodeKind.PORT_INOUT
                    elif "output" in direction.lower():
                        kind = NodeKind.PORT_OUT
                    else:
                        kind = NodeKind.PORT_IN
                    # 提取端口位宽 (传入 module 作为 scope 以解析参数)
                    port_width = self.adapter.extract_port_width(port_decl, scope=module)
                    # convert dict to tuple for compatibility
                    if isinstance(port_width, dict):
                        msb = port_width.get("msb_eval", port_width.get("msb_raw", 0))
                        lsb = port_width.get("lsb_eval", port_width.get("lsb_raw", 0))
                        try:
                            msb = int(msb) if msb is not None else 0
                        except (ValueError, TypeError):
                            # [P0 核实 2026-08-29] 位宽值无法转 int (非数字) → 0
                            # 显式 sentinel: 下游会按 (0,0) 或再 fallback 到 (1,0) 处理,
                            # 不会静默产出错误位宽.
                            msb = 0
                        try:
                            lsb = int(lsb) if lsb is not None else 0
                        except (ValueError, TypeError):
                            # 同上: 非数字 lsb → 0 (显式 sentinel)
                            lsb = 0
                        port_width = (msb, lsb)
                    # [V6.2 2026-07-20] Capture source location for jump-to-source
                    port_file, port_line, _, _ = self.adapter.get_source_location(port_decl)
                    result.nodes.append(
                        TraceNode(
                            id=port_id, name=port_name, module=module_name, kind=kind, width=port_width, is_port=True,
                            file=port_file, line=port_line,
                        )
                    )

            # [P0-3] Build interface port map for this module
            interface_ports = {}  # port_name -> (interface_name, modport_name)
            try:
                if hasattr(module, "header") and module.header:
                    header = module.header
                    if hasattr(header, "ports") and hasattr(header.ports, "ports"):
                        for item in header.ports.ports:
                            if not hasattr(item, "kind") or item.kind != pyslang.SyntaxKind.ImplicitAnsiPort:
                                continue
                            try:
                                h = getattr(item, "header", None)
                                decl = getattr(item, "declarator", None)
                            except AttributeError:
                                continue
                            if h is None or decl is None:
                                continue
                            if hasattr(h, "kind") and "InterfacePortHeader" in str(h.kind):
                                port_name = safe_str(safe_attr(decl, "name", "")).value if hasattr(safe_str(safe_attr(decl, "name", "")), "value") else str(safe_str(safe_attr(decl, "name", "")))
                                interface_name = None
                                if hasattr(h, "nameOrKeyword"):
                                    nk = h.nameOrKeyword
                                    interface_name = nk.rawText if hasattr(nk, "rawText") else str(nk)
                                modport_name = None
                                if hasattr(h, "modport") and hasattr(h.modport, "member"):
                                    member_val = h.modport.member
                                    # [iter_183] safe_attr (hasattr 不吞 UnicodeDecodeError)
                                modport_name = safe_str(safe_attr(member_val, "name", "")) or str(member_val)
                                if port_name and interface_name:
                                    interface_ports[port_name.strip()] = (interface_name, modport_name)
                            elif hasattr(h, "kind") and "VariablePortHeader" in str(h.kind):
                                port_name = safe_str(safe_attr(decl, "name", "")).value if hasattr(safe_str(safe_attr(decl, "name", "")), "value") else str(safe_str(safe_attr(decl, "name", "")))
            except (ValueError, AttributeError, TypeError) as e:
                logger.debug("端口名提取失败: %s", e)

        return result

    # [重构 2026-08-07] 删除孤儿死方法 _parse_assign:
    # 它在本模块无任何调用点, LoadExtractor.extract() 不调用它,
    # 也没有外部调用者 (仅 re-export 类本身). 属于历史遗留死代码.
    # [iter_245] 同源清理: 删除 _get_signal (283 行). 它只被自己递归调用,
    # extract() 从不调用, 且末尾 raise 之后还有不可达分支.

