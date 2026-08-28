# ==============================================================================
# extractors/expr_tree_builder.py - 表达式树 / 常量 / 函数信息构建器
#
# [ARCHITECTURE_TODOLIST #6 2026-08-28]
# 从 driver_extractor.py 拆出 expr_trees/const_map/func_info 提取逻辑:
#   - _store_expr_tree            (driver_extractor L207-274)
#   - _tree_complexity            (L44)
#   - _collect_from_tree          (L55)
#   - _substitute_genvar_in_tree  (L276, staticmethod)
#
# 关注点分离:
#   driver_extractor 只负责"原始 driver 边"; 表达式树/常量/函数信息
#   是独立关注点, 由本模块负责。
#
# 设计: 纯函数风格 (与 _common.py 一致), 无状态, 便于单测。
#   build_expr_tree() 是唯一入口, 等价原 _store_expr_tree。
#
# ── 行为契约 ──────────────────────────────────────────────────────────────────
# - build_expr_tree(lhs_name, rhs_expr, module_name, result, genvar_ctx):
#   等价原 driver_extractor._store_expr_tree, 写 result.expr_trees/const_map/func_info
# - 多分支 max 合并 (保留最复杂代表)
# - genvar_ctx substitute (Plan G2: 'acc[i]' → 'acc[N]')
# - unwrap Conversion wrappers (最多 10 层)
# ==============================================================================
from typing import Any


def tree_complexity(d: dict) -> int:
    """计算 tree_dict 的 descendants 总数（含自身）.

    用于多分支 case/if 赋值时，选择最复杂的代表表达式。
    [从 driver_extractor._tree_complexity 搬入]
    """
    total = 1
    for c in d.get('children', []):
        total += tree_complexity(c)
    return total


def collect_from_tree(tree_dict: dict, dst_short: str, const_map: dict, func_info: dict) -> None:
    """从 expr_tree 树遍历提取 Const 叶子 → const_map，Call 节点 → func_info.

    替代旧 regex 从源码文本扫 assign/wire 行的 const_map 提取方式，
    数据源改为表达式树本身（更准确，旧 regex 在复杂 case 会漏）。
    [从 driver_extractor._collect_from_tree 搬入]
    """
    op = tree_dict.get('op')
    lbl = tree_dict.get('label')
    if op == 'Const' and lbl:
        lst = const_map.setdefault(dst_short, [])
        if lbl not in lst:
            lst.append(lbl)
    if op == 'Call' and lbl:
        if lbl not in func_info:
            func_info[lbl] = None  # 宽度由 extract() 阶段从 semantic function symbol 补充
    for c in tree_dict.get('children', []):
        collect_from_tree(c, dst_short, const_map, func_info)


def substitute_genvar_in_tree(tree_dict: dict, ctx: dict) -> dict:
    """[Plan G2 2026-08-27] Walk ExpressionTree._to_dict() tree and substitute
    genvar references in SignalRef leaf labels.

    raw AST ExpressionTree._parse_expr emit leaves like 'acc[i]' (literal),
    even though ctx={'i': N} is available. viz layer reads these labels
    directly → SVG has 'acc[i]' literal. 用户 directive: "viz 不要从 raw AST
    拿数据, 仅从 graph 拿需要的数据" — substitute 发生在 graph 层,
    不在 viz。

    行为 1:1 复刻原 driver_extractor._substitute_genvar_in_tree:
    - SignalRef / BitSelect + label 'base[idx]' 且 idx ∈ ctx → 'base[N]'
    - label 本身是 genvar 名 (∈ ctx) → str(N)
    - 递归 children (仅 dict)

    [从 driver_extractor._substitute_genvar_in_tree 搬入, 保持原逻辑]
    """
    if not isinstance(tree_dict, dict) or not ctx:
        return tree_dict
    op = tree_dict.get("op", "")
    label = tree_dict.get("label", "")
    children = tree_dict.get("children", []) or []
    new_label = label
    if op in ("SignalRef", "BitSelect") and label:
        if "[" in label and label.endswith("]"):
            base, _, idx_str = label[:-1].rpartition("[")
            if idx_str in ctx:
                new_label = f"{base}[{ctx[idx_str]}]"
        elif label in ctx:
            new_label = str(ctx[label])
    new_children = [
        substitute_genvar_in_tree(c, ctx)
        for c in children if isinstance(c, dict)
    ]
    return {**tree_dict, "label": new_label, "children": new_children}


def build_expr_tree(
    lhs_name: str,
    rhs_expr: Any,
    module_name: str,
    result: Any,
    genvar_ctx: dict | None = None,
) -> None:
    """构建表达式树 + 提取 const/func 信息, 写入 result.

    等价原 driver_extractor._store_expr_tree (行为 1:1)。

    Args:
        lhs_name: 被赋值信号名 (不含 module 前缀)
        rhs_expr: pyslang semantic AST 表达式节点
        module_name: 模块/实例路径前缀
        result: ExtractorResult
        genvar_ctx: {genvar_name: int_value} e.g. {'i': 2}
    """
    if not lhs_name or rhs_expr is None:
        return
    # [Plan F2.6 2026-08-13 BUG FIX] unwrap Conversion wrappers
    cur = rhs_expr
    for _ in range(10):  # 最多解 10 层防无限循环
        if cur is None:
            return
        sk = str(getattr(cur, 'kind', ''))
        if 'Conversion' not in sk:
            break
        operand = getattr(cur, 'operand', None)
        if operand is None or operand is cur:
            break
        cur = operand
    syntax = getattr(cur, 'syntax', None)
    if syntax is None:
        return
    try:
        tokens = list(syntax)
    except (TypeError, ValueError):
        return
    if not tokens:
        return

    from ..graph.viz.expression_tree import ExpressionTree

    root = ExpressionTree._parse_expr(tokens, 0, len(tokens))
    if root is None:
        return

    tree_key = f"{module_name}.{lhs_name}" if module_name else lhs_name
    tree_dict = ExpressionTree._to_dict(root)

    # [Plan G2] substitute genvar refs in tree leaves
    if genvar_ctx and tree_dict:
        tree_dict = substitute_genvar_in_tree(tree_dict, genvar_ctx)

    # 多分支合并：已有则保留更复杂的一个
    existing = result.expr_trees.get(tree_key)
    if existing is not None and tree_complexity(tree_dict) <= tree_complexity(existing):
        return
    result.expr_trees[tree_key] = tree_dict

    # 从树遍历提取 Const → const_map, Call → func_info
    collect_from_tree(tree_dict, lhs_name, result.const_map, result.func_info)
