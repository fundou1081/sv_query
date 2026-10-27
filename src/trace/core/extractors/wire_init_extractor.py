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
# [Step 3b 2026-08-28 已完成 — 上面这段估计是错的, 保留作记录]
#   _create_net_decl_edges 已拆到**同目录的 net_decl_extractor.py**, 实际耗时 0.5 小时。
#   原估计 "1+ 天 / 需先把 helper 提到 _common" 的前提不成立: 那 6 个直接依赖
#   (传递闭包 12 个 / 563 行) 是**全文件共享基础设施** (_get_signal 有 35 处调用),
#   搬走会波及 Step 4-7 尚未拆分的区域。改用 Step 1+2 已验证的 Callable 依赖注入,
#   helper 定义留在 driver_extractor 即可。详见 iter_037。
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
        adapter: SemanticAdapter 实例 (提供 get_variable_declarations 等)
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
    symbols = adapter.get_variable_symbols(module)
    for var_decl in adapter.get_variable_declarations(module):
        var_name = adapter.get_signal_name(var_decl)
        if not var_name or var_name in port_names:
            continue
        var_name = adapter.clean_name(var_name)
        var_id = f"{module_name}.{var_name}"
        # [iter_299 / PLAN P11.1] typedef（packed struct/union）在 syntax 层没有
        # 宽度/signedness；优先用语义符号的 .type.bitWidth / .type.isSigned
        sym = symbols.get(var_name)
        var_width = (adapter.extract_data_width(sym) if sym is not None
                     else adapter.extract_data_width(var_decl))
        var_signed = (adapter.extract_data_signed(sym) if sym is not None
                      else adapter.extract_data_signed(var_decl))
        # [iter_307 / PLAN P13.6] 标记 unpacked array（元素节点宽度据此回填）
        is_array = bool(getattr(getattr(sym, "type", None), "isUnpackedArray", False))
        existing = next((n for n in result.nodes if n.id == var_id), None)
        if existing is not None:
            # [iter_298 / PLAN P10.2] 懒建节点 (1,0) 回填声明宽度（integer 等）
            if (var_width is not None and var_width != (1, 0)
                    and existing.width == (1, 0)):
                existing.width = var_width
            if existing.is_signed is None and var_signed is not None:
                existing.is_signed = var_signed
            if is_array:
                if existing.extra is None:
                    existing.extra = {}
                existing.extra["is_array"] = True
            continue
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
                is_signed=var_signed,
                extra={"is_array": True} if is_array else {},
            )
        )
        count += 1
    return count
