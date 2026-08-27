# ==============================================================================
# extractors/wire_init_extractor.py - 变量声明 + (后续) net decl 边创建
#
# [ARCHITECTURE_TODOLIST #1 Step 3 2026-08-27 21:33]
# 从 driver_extractor.py 拆出.
#
# 拆出的方法:
#   - _create_var_nodes (driver_extractor line 861-883, 22 行)
#     为非端口变量/网表声明创建 SIGNAL TraceNode. [已拆]
#
# 暂未拆出 (Step 3b 后续):
#   - _create_net_decl_edges (driver_extractor line 911-1033, ~123 行)
#     依赖 7 个 driver_extractor 内部 helper (_build_signal_source,
#     _get_all_real_signals, _get_signal, _store_expr_tree, ...),
#     工程量 1+ 天, 留到 Step 3b 单独处理.
#
# 行为契约 (必须 1:1 跟原方法一致, 测试保护):
# - 输入: adapter (有 get_variable_declarations/get_signal_name/clean_name/
#                extract_data_width/get_source_location), module, result,
#        module_name, port_names
# - 输出: 写 SIGNAL TraceNode 到 result.nodes (跳过端口 + 重复 id)
# - 节点: var_width 来自 adapter.extract_data_width, 跟原方法一致
# ==============================================================================
from typing import Any


def create_var_nodes(
    adapter: Any,
    module: Any,
    result: Any,
    module_name: str,
    port_names: set,
) -> int:
    """[2026-08-27 21:33] 从 driver_extractor._create_var_nodes 拆出.

    为非端口变量/网表声明创建 SIGNAL TraceNode.

    Args:
        adapter: PyslangAdapter 实例 (提供 get_variable_declarations 等)
        module: pyslang module symbol
        result: ExtractorResult 累积目标
        module_name: 完整 hierarchy path (e.g. "top.u_dut")
        port_names: port 名集合 (跳过)

    Returns:
        创建的节点数 (供测试断言 / metrics 用)
    """
    # [铁律4] 直接 import — wire_init_extractor 跟 graph.models 在不同子目录, 无循环
    from ..graph.models import NodeKind, TraceNode

    count = 0
    for var_decl in adapter.get_variable_declarations(module):
        var_name = adapter.get_signal_name(var_decl)
        if not var_name or var_name in port_names:
            continue
        var_name = adapter.clean_name(var_name)
        var_id = f"{module_name}.{var_name}"
        if var_id not in [n.id for n in result.nodes]:
            var_width = adapter.extract_data_width(var_decl)
            var_file, var_line, _, _ = adapter.get_source_location(var_decl)
            result.nodes.append(
                TraceNode(
                    id=var_id,
                    name=var_name,
                    module=module_name,
                    kind=NodeKind.SIGNAL,
                    width=var_width,
                    file=var_file,
                    line=var_line,
                )
            )
            count += 1
    return count