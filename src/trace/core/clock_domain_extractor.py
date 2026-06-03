# ==============================================================================
# clock_domain_extractor.py - Clock Domain 提取器 (从 graph_builder.py 物理拆分, P1 cycle 9c)
#
# 职责: 解析 SV always 块, 提取 clock domain (CLOCK) 边.
# ==============================================================================

import logging

from .base import PyslangAdapter
from .extractor_models import ExtractorResult
from .graph.models import NodeKind, TraceNode

logger = logging.getLogger(__name__)



class ClockDomainExtractor:
    def __init__(self, adapter: PyslangAdapter):
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
                            msb = 0
                        try:
                            lsb = int(lsb) if lsb is not None else 0
                        except (ValueError, TypeError):
                            lsb = 0
                        port_width = (msb, lsb)
                    result.nodes.append(
                        TraceNode(
                            id=port_id, name=port_name, module=module_name, kind=kind, width=port_width, is_port=True
                        )
                    )

            for port in self.adapter.get_port_names(module):
                port_name, direction = self.adapter.get_port_name_and_direction(port)
                if not port_name:
                    continue

                port_name = self.adapter.clean_name(port_name)

                is_clock = "clk" in port_name.lower()
                is_reset = "rst" in port_name.lower()

                if is_clock or is_reset:
                    result.nodes.append(
                        TraceNode(
                            id=f"{module_name}.{port_name}",
                            name=port_name,
                            module=module_name,
                            kind=NodeKind.PORT_IN,
                            width=(1, 0),
                            is_clock=is_clock,
                            is_reset=is_reset,
                        )
                    )

        return result


