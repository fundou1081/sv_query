# ==============================================================================
# extractors/alias_extractor.py - alias 语句 driver 边提取
#
# [ARCHITECTURE_TODOLIST #1 Step 1+2 2026-08-27 20:38]
# 从 driver_extractor.py 拆出. 原方法 _create_net_alias_edges (line 1140-1168)
# + _extract_alias_ref_name (line 1164-1168).
#
# alias 语句 SV 规范: `alias b = a;` 表示 b 是 a 的别名, pyslang 给出
# `netReferences = [target, source]` 顺序. 驱动方向 a → b.
# 实测确认: commit 554aee9 审查已验证.
#
# 行为契约 (必须 1:1 跟原方法一致, 测试保护):
# - 输入: adapter (有 get_net_aliases), module, result, module_name
# - 输出: 写 DRIVER 边到 result.edges
# - assign_type: "alias"
# - 节点: source/target 都确保创建 SIGNAL TraceNode
# - 跳过: netReferences < 2 或 ref_name 提取失败
# ==============================================================================
from typing import Any, Callable

from ..graph.models import EdgeKind


def extract_alias_edges(
    adapter: Any,
    module: Any,
    result: Any,
    module_name: str,
    ensure_signal_node: Callable,
    append_edge: Callable,
) -> int:
    """[2026-08-27] 从 driver_extractor._create_net_alias_edges 拆出.

    遍历 module 的所有 NetAlias, 为每个 alias 创建 DRIVER 边 (source → target).

    Args:
        adapter: SemanticAdapter 实例 (提供 get_net_aliases)
        module: pyslang module symbol
        result: ExtractorResult 累积目标
        module_name: 完整 hierarchy path (e.g. "top.u_dut")
        ensure_signal_node: 共享 helper, 来自 driver_extractor 实例
        append_edge: 共享 helper, 来自 driver_extractor 实例

    Returns:
        生成的 DRIVER 边数 (供测试断言 / metrics 用)
    """
    edge_count = 0
    for alias in adapter.get_net_aliases(module):
        refs = getattr(alias, "netReferences", None)
        if not refs or len(refs) < 2:
            continue
        # refs[0] = target (b), refs[1] = source (a)
        target_name = _extract_alias_ref_name(refs[0])
        source_name = _extract_alias_ref_name(refs[1])
        if not target_name or not source_name:
            continue
        target_id = f"{module_name}.{target_name}"
        source_id = f"{module_name}.{source_name}"
        ensure_signal_node(result, source_id, source_name, module_name)
        ensure_signal_node(result, target_id, target_name, module_name)
        append_edge(
            result,
            src=source_id,
            dst=target_id,
            kind=EdgeKind.DRIVER,
            assign_type="alias",
        )
        edge_count += 1
    return edge_count


def _extract_alias_ref_name(ref_expr: Any) -> str | None:
    """[REFACTOR 2026-06-26] 从 alias ref expr 提取 .symbol.name (None if missing).

    与 driver_extractor._extract_alias_ref_name 完全一致, 复制以避免跨文件依赖.
    """
    if hasattr(ref_expr, "symbol") and hasattr(ref_expr.symbol, "name"):
        return str(ref_expr.symbol.name)
    return None
