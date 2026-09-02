# ==============================================================================
# extractors/net_decl_extractor.py - 带初始化器的 net 声明 driver 边提取
#
# [ARCHITECTURE_TODOLIST #1 Step 3b 2026-08-28]
# 从 driver_extractor.py 拆出 _create_net_decl_edges (line 905-1014, 110 行).
#
# 处理 `wire X = expr;` 形式的 net 声明, 为 RHS 每个真实信号建 DRIVER 边。
#
# ── 为什么依赖注入而不是搬 helper ────────────────────────────────────────────
# 本函数依赖 6 个 driver_extractor 内部 helper, 传递闭包共 12 个 / 563 行。
# 但实测这些 helper 是**全文件共享**的 (调用点数: _get_signal 35 / _store_expr_tree 7
# / _build_signal_source 6 / _append_edge 6 / _get_all_real_signals 5 /
# _ensure_signal_node 4), 搬走会波及 Step 4-7 尚未拆分的 assign/always/function 部分,
# 属于跨 Step 的大改动, 不在 Step 3b 范围。
#
# 故沿用 Step 1+2 (alias_extractor) 已验证的模式: helper 以 Callable 参数注入,
# 定义仍留在 driver_extractor。这样 Step 3b 只搬"业务逻辑", 不动共享基础设施。
#
# ── 行为契约 (必须 1:1 跟原方法一致, 测试保护) ──────────────────────────────
# - 输入: adapter (有 get_net_declarations / get_generate_net_declarations /
#         clean_name / get_genvar_context), module, result, module_name, port_names
# - 输出: 写 DRIVER 边 (assign_type="continuous") + SIGNAL TraceNode 到 result
# - 两段循环:
#   1) get_net_declarations  → module.body 顶层的 wire decl, node id = f"{module}.{name}"
#   2) get_generate_net_declarations → generate-for 内展开的 wire decl,
#      node id 用 hierarchical_path (4 个 entry 的 prod 是 4 个独立 symbol,
#      不能都叫 'generate_loop.prod', 否则 tree_key 会 max-合并成 1 个)
# - 跳过: 空名 / 名在 port_names / initializer 为 None / src_id == lhs_id
# - genvar_ctx: 每个 net_decl 独立取 (generate-for 内 weights[i] 需 ctx 替换成 weights[N])
# ==============================================================================
from typing import Any, Callable

from ..graph.models import EdgeKind, NodeKind, SignalSource, TraceNode


def create_net_decl_edges(
    adapter: Any,
    module: Any,
    result: Any,
    module_name: str,
    port_names: set,
    *,
    store_expr_tree: Callable,
    ensure_signal_node: Callable,
    get_signal: Callable,
    get_all_real_signals: Callable,
    build_signal_source: Callable,
    append_edge: Callable,
    genvar_ctx: dict | None = None,
) -> int:
    """[2026-08-28 Step 3b] 从 driver_extractor._create_net_decl_edges 拆出.

    处理带初始化器的 Net 声明: `wire X = expr;` → 创建 DRIVER 边.
    通过 build_signal_source 提取 source_op/operand_side/casts,
    使 net-decl 边和 assign 边的 signal source 信息一致。

    Args:
        adapter: SemanticAdapter 实例
        module: pyslang module symbol
        result: ExtractorResult 累积目标
        module_name: 完整 hierarchy path (e.g. "top.u_dut")
        port_names: port 名集合 (跳过)
        store_expr_tree / ensure_signal_node / get_signal / get_all_real_signals /
        build_signal_source / append_edge: 共享 helper, 来自 driver_extractor 实例
        genvar_ctx: 外层传入的 genvar 上下文 (与每个 decl 自身的 ctx 合并)

    Returns:
        生成的 DRIVER 边数 (供测试断言 / metrics 用)
    """
    edge_count = 0

    # ── 循环 1: module.body 顶层的 net 声明 ──────────────────────────────────
    for net_decl in adapter.get_net_declarations(module):
        # NetSymbol (semantic AST): 有 name + initializer, 没有 declarators
        # 访问 .name 时可能触发 utf-8 转换 (escape 序列), 需要 try/except
        try:
            raw_name = getattr(net_decl, "name", "")
            lhs_name = adapter.clean_name(raw_name or "")
        except (UnicodeDecodeError, TypeError):
            lhs_name = "<id:non-utf8>"
        if not lhs_name or lhs_name in port_names:
            continue

        # [iter_105] 所有 net 都建节点/补宽度 (含无 init 的 `wire [N:M] x;`) —
        # 之前只有带 init 的建节点, 无 init 的惰性由 ensure_signal_node 建 (1,0) 假宽度.
        lhs_id = f"{module_name}.{lhs_name}"
        _ensure_net_node(result, lhs_id, lhs_name, module_name,
                         adapter.extract_data_width(net_decl))

        try:
            init = getattr(net_decl, "initializer", None)
        except (UnicodeDecodeError, TypeError):
            init = None
        if init is None:
            continue

        # [Plan G3 2026-08-27 12:35] 每个 net_decl 独立拿 genvar_ctx
        # wire decl 在 generate-for 内时, e.g. case27 gen_accum.iter[0] 内的
        # 'wire prod = data * weights[i]' 需要 ctx={'i': 0} 来 substitute weights[i] → weights[0]
        try:
            net_decl_ctx = dict(adapter.get_genvar_context(net_decl) or {})
            if genvar_ctx:
                net_decl_ctx.update(genvar_ctx)
        except Exception:
            net_decl_ctx = dict(genvar_ctx or {})

        # [REFACTOR 2026-08-07 A计划] 从 netdecl init 构建表达式树 (wire sum = a + b)
        # init 是 semantic BinaryExpression, .syntax 直接可用 (已实证)
        store_expr_tree(lhs_name, init, module_name, result, genvar_ctx=net_decl_ctx)
        rhs_expr_str = get_signal(init) or ""
        rhs_signals = get_all_real_signals(init, module=module, genvar_ctx=genvar_ctx) if init else []
        edge_count += _emit_driver_edges(
            result=result,
            module_name=module_name,
            lhs_id=lhs_id,
            init=init,
            rhs_expr_str=rhs_expr_str,
            rhs_signals=rhs_signals,
            ensure_signal_node=ensure_signal_node,
            build_signal_source=build_signal_source,
            append_edge=append_edge,
        )

    # ── 循环 2: generate-for 内展开的带 init wire decl ───────────────────────
    # [Plan G3 2026-08-27 13:01] 例如 case27 'wire [W-1:0] prod = data * weights[i]'
    # (line 25, 藏在 gen_accum entry 内)。get_net_declarations(module) 只遍历
    # module.body 顶层, 拿不到这些; 用纯 semantic get_generate_net_declarations 补上。
    # 每个 entry 有 arrayIndex → genvar_ctx {'i': N}, RHS 信号名 substitute 用 entry 的 ctx。
    for g_decl in adapter.get_generate_net_declarations(module):
        g_name = g_decl.get("name", "")
        g_init = g_decl.get("initializer")
        g_ctx = g_decl.get("genvar_ctx") or {}
        if not g_name or g_init is None:
            continue

        # [Plan G3 2026-08-27 13:20] 用 hierarchicalPath 当 node id — 4 entry 的 prod 是
        # 4 个独立 symbol (generate_loop.gen_accum[N].prod). 之前用 f"{module_name}.{g_name}"
        # = 'generate_loop.prod' 全一样, 导致 tree_key max-合并成 1 个 (gap_2 只 1 个 '*').
        g_hp = g_decl.get("hierarchical_path") or ""
        if g_hp:
            # hp 已经是完整路径 (generate_loop.gen_accum[0].prod), 直接用当 node id
            g_lhs_id = g_hp
            g_short = g_hp.rsplit(".", 1)[-1] if "." in g_hp else g_hp
        else:
            g_hp_fallback = f"{module_name}.gen_accum[{g_decl.get('array_index')}].{g_name}"
            g_lhs_id = g_hp_fallback
            g_short = g_name

        # [iter_101] 缺陷 B: generate 内 wire 也用声明位宽建节点 (ensure_signal_node 硬编码 1 位)
        _ensure_net_node(result, g_lhs_id, g_short, module_name, g_decl.get("width"))
        # expr tree (换入 entry ctx, weights[i] → 数值), 用 g_lhs_id 当 tree_key 区分
        store_expr_tree(g_lhs_id, g_init, "", result, genvar_ctx=g_ctx)
        g_rhs_str = get_signal(g_init) or ""
        g_signals = get_all_real_signals(g_init, module=module, genvar_ctx=g_ctx) if g_init else []
        edge_count += _emit_driver_edges(
            result=result,
            module_name=module_name,
            lhs_id=g_lhs_id,
            init=g_init,
            rhs_expr_str=g_rhs_str,
            rhs_signals=g_signals,
            ensure_signal_node=ensure_signal_node,
            build_signal_source=build_signal_source,
            append_edge=append_edge,
        )

    return edge_count


def _ensure_net_node(result, node_id: str, name: str, module_name: str, width) -> None:
    """[iter_101] 创建 net 声明节点, 用声明位宽 (缺陷 B 修复).

    ensure_signal_node 硬编码 width=(1,0) — `wire [15:0] x = ...` 的位宽
    被忽略 (下游 width 消费错误). 本 helper 用 extract_data_width 的结果建节点;
    已存在则跳过, 但 [iter_105] 若已存在节点是 ensure_signal_node 的 (1,0)
    假宽度而声明宽度已知 (如无 init 的 `wire [7:0] x;`), 补成真宽度.
    """
    for n in result.nodes:
        if n.id == node_id:
            if (width is not None and width != (1, 0)
                    and n.width == (1, 0)):
                n.width = width
            return
    result.nodes.append(
        TraceNode(id=node_id, name=name, module=module_name,
                  kind=NodeKind.SIGNAL, width=width or (1, 0))
    )


def _emit_driver_edges(
    *,
    result: Any,
    module_name: str,
    lhs_id: str,
    init: Any,
    rhs_expr_str: str,
    rhs_signals: list,
    ensure_signal_node: Callable,
    build_signal_source: Callable,
    append_edge: Callable,
) -> int:
    """[2026-08-28 Step 3b] 两段循环共用的边发射逻辑.

    原实现在 _create_net_decl_edges 里**逐行重复了两遍** (顶层 decl 与 generate
    展开 decl 各一份), 仅 lhs_id 的构造方式不同。这里抽成单一函数消除重复 —
    行为 1:1 一致, 不改变任何边的字段。

    Returns:
        本次发射的边数
    """
    count = 0
    for src_name in rhs_signals:
        src_id = f"{module_name}.{src_name}"
        ensure_signal_node(result, src_id, src_name, module_name)
        if src_id == lhs_id:
            continue
        # 通过 build_signal_source 提取 source_op/operand_side/casts
        # 保证 net-decl 边和 assign 边的 signal source 信息一致
        ds = build_signal_source(src_name, init, rhs_expr_str)
        append_edge(
            result,
            src=src_id,
            dst=lhs_id,
            kind=EdgeKind.DRIVER,
            assign_type="continuous",
            expression=rhs_expr_str,
            source=SignalSource(
                signal=src_name,
                full_expression=rhs_expr_str,
                op=ds.op if ds.op else "",
                operand_side=ds.operand_side if ds.operand_side else "",
                casts=list(ds.casts) if ds.casts else [],
                is_decomposed=True,
            ),
        )
        count += 1
    return count
