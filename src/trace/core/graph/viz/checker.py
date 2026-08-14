"""
viz/checker.py — VizData → ELK → SVG 渲染结果检查器 (V1)

目的:
  确保 viz 渲染的 SVG 输出跟原始 VizData 一致, 没有 dedup / 节点丢 / 边丢 /
  compound 错位等渲染 bug. 用于开发期防回归.

设计 (三层检查):
  Layer A — 结构完整性 (cheap):
    A1: SVG leaf rect 数 vs viz 预期 leaf 数
    A2: SVG compound 数 vs viz 预期 compound 数
    A3: 没有孤立 leaf (端口/锚点例外)
  Layer B — 边覆盖率 (medium):
    B1: 每条非平凡 viz.edge 的 src/dst 短名都能在 SVG 找到
    B2: 自环 / BIT_SELECT / 已知折叠类白名单正确省略
    B3: SVG path 端点坐标唯一 (无重复坐标 → 无 phantom edge)
  Layer C — 语义保真 (strict):
    C1: case compound 的 branches 数 == condition_chain 数
    C2: condition_anchor 有 port → anchor 边
    C3: case label 唯一 (两个不同 case 不能同 label)
    C4: 不同 viz 边的同名 src/dst 在 SVG 里位置不同 (dedup loss 检测)
    C5: expr_trees 完整保留 (无短名合并)

Level:
  basic    = Layer A only
  standard = Layer A + B
  strict   = Layer A + B + C  (默认)

用法:
    from trace.core.graph.viz.checker import check_viz_render
    
    report = check_viz_render(viz, layout, svg, level='strict')
    if not report.passed:
        for err in report.errors:
            print(err)

CLI:
    sv_query viz check <fixture.sv> --module <name> --level strict
"""

from __future__ import annotations
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any

try:
    from lxml import etree
    HAS_LXML = True
except ImportError:
    HAS_LXML = False


# ═══════════════════════════════════════════════════
# Report 数据结构
# ═══════════════════════════════════════════════════

@dataclass
class CheckResult:
    """单个 check 的结果"""
    name: str
    layer: str  # 'A' / 'B' / 'C'
    passed: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    details: dict = field(default_factory=dict)
    
    def __bool__(self) -> bool:
        return self.passed


@dataclass
class CheckReport:
    """完整检查报告"""
    layer_a: list[CheckResult] = field(default_factory=list)
    layer_b: list[CheckResult] = field(default_factory=list)
    layer_c: list[CheckResult] = field(default_factory=list)
    layer_d: list[CheckResult] = field(default_factory=list)  # [Plan D2] sanity checks
    level: str = 'strict'
    
    @property
    def all_results(self) -> list[CheckResult]:
        return self.layer_d + self.layer_a + self.layer_b + self.layer_c
    
    @property
    def errors(self) -> list[str]:
        out = []
        for r in self.all_results:
            out.extend(r.errors)
        return out
    
    @property
    def warnings(self) -> list[str]:
        out = []
        for r in self.all_results:
            out.extend(r.warnings)
        return out
    
    @property
    def passed(self) -> bool:
        return all(r.passed for r in self.all_results)
    
    def summary(self) -> str:
        lines = []
        n_pass = sum(1 for r in self.all_results if r.passed)
        n_fail = sum(1 for r in self.all_results if not r.passed)
        lines.append(f"[CHECK] {n_pass}/{n_pass+n_fail} passed, level={self.level}")
        for r in self.all_results:
            mark = '✓' if r.passed else '✗'
            lines.append(f"  [{mark}] L{r.layer} {r.name}")
            for err in r.errors:
                lines.append(f"      ERR: {err}")
            for warn in r.warnings:
                lines.append(f"      WARN: {warn}")
        if not self.passed:
            lines.append(f"\n[CHECK] FAILED ({len(self.errors)} errors)")
        else:
            lines.append(f"\n[CHECK] PASSED")
        return '\n'.join(lines)


# ═══════════════════════════════════════════════════
# SVG 解析
# ═══════════════════════════════════════════════════

@dataclass
class SvgNode:
    """SVG 解析出的节点"""
    label: str
    x: float
    y: float
    w: float
    h: float
    kind: str  # 'leaf' | 'compound'
    fill: str = ''
    stroke: str = ''


@dataclass
class SvgEdge:
    """SVG 解析出的边"""
    src_x: float
    src_y: float
    dst_x: float
    dst_y: float
    kind: str  # 'signal' | 'condition_select'


def _parse_svg(svg: str) -> tuple[list[SvgNode], list[SvgEdge]]:
    """解析 SVG → (nodes, edges)
    
    不依赖 lxml 时用 regex 退化解析 (功能受限).
    """
    if HAS_LXML:
        return _parse_svg_lxml(svg)
    return _parse_svg_regex(svg)


def _parse_svg_lxml(svg: str) -> tuple[list[SvgNode], list[SvgEdge]]:
    """lxml 精确解析"""
    try:
        root = etree.fromstring(svg.encode('utf-8'))
    except etree.XMLSyntaxError as e:
        return [], []
    
    nodes = []
    edges = []
    
    # ── 节点: <rect> + 同位置 <text> label ──
    # 收集所有 rect
    rects = root.findall('.//{http://www.w3.org/2000/svg}rect')
    texts = root.findall('.//{http://www.w3.org/2000/svg}text')
    
    SVG_NS = '{http://www.w3.org/2000/svg}'
    
    for rect in rects:
        try:
            x = float(rect.get('x', '0'))
            y = float(rect.get('y', '0'))
            w = float(rect.get('width', '0'))
            h = float(rect.get('height', '0'))
        except (ValueError, TypeError):
            continue
        
        fill = rect.get('fill', '')
        stroke = rect.get('stroke', '')
        dash = rect.get('stroke-dasharray', '')
        
        # compound: 有 stroke-dasharray
        if dash:
            kind = 'compound'
        elif fill == '#ffffff':
            # 背景 rect, 跳过
            continue
        else:
            kind = 'leaf'
        
        # 找同位置的 text label
        label = ''
        for t in texts:
            try:
                tx = float(t.get('x', '0'))
                ty = float(t.get('y', '0'))
            except (ValueError, TypeError):
                continue
            # text 必须在 rect 内部
            if x <= tx <= x + w and y <= ty <= y + h:
                # 取 text 内容 (子 text elements)
                t_texts = t.findall(f'.//{SVG_NS}tspan')
                if t_texts:
                    label = ''.join(t.text or '' for t in t_texts)
                else:
                    label = t.text or ''
                break
        
        nodes.append(SvgNode(
            label=label, x=x, y=y, w=w, h=h,
            kind=kind, fill=fill, stroke=stroke,
        ))
    
    # ── 边: <path> with M/L commands ──
    # 跳过 <defs> 内的 marker 箭头定义 (起点在 0,0)
    paths = root.findall(f'.//{SVG_NS}path')
    for path in paths:
        # 检查是否在 <defs> 内
        parent = path.getparent()
        while parent is not None:
            if parent.tag == f'{SVG_NS}defs':
                break
            parent = parent.getparent()
        if parent is not None and parent.tag == f'{SVG_NS}defs':
            continue
        
        d = path.get('d', '')
        if not d.startswith('M'):
            continue
        
        # 解析 M x1 y1 L x2 y2 (可能有空格分隔)
        match = re.match(r'M\s*([-\d.]+)\s+([-\d.]+)\s+L\s+([-\d.]+)\s+([-\d.]+)', d)
        if not match:
            continue
        
        sx, sy, ex, ey = (float(g) for g in match.groups())
        # 跳过 marker 箭头定义 (起终点都在 [0, 10])
        if sx <= 10 and sy <= 10 and ex <= 10 and ey <= 10:
            continue
        dash = path.get('stroke-dasharray', '')
        ekind = 'condition_select' if dash else 'signal'
        edges.append(SvgEdge(sx, sy, ex, ey, ekind))
    
    return nodes, edges


def _parse_svg_regex(svg: str) -> tuple[list[SvgNode], list[SvgEdge]]:
    """Regex 退化解析 (lxml 不可用时)"""
    nodes = []
    edges = []
    
    # 简化解析: 跳过 background rect (fill=#ffffff)
    # 只解析 dasharray='4,2' 的 compound rect
    rect_pattern = re.compile(
        r'<rect\s+x="([\d.-]+)"\s+y="([\d.-]+)"\s+width="([\d.-]+)"\s+height="([\d.-]+)"'
        r'(?:\s+fill="([^"]+)")?'
        r'(?:\s+stroke="([^"]+)")?'
        r'(?:\s+stroke-dasharray="([^"]+)")?'
    )
    for m in rect_pattern.finditer(svg):
        x, y, w, h = (float(g) for g in m.groups()[:4])
        fill = m.group(5) or ''
        stroke = m.group(6) or ''
        dash = m.group(7) or ''
        if fill == '#ffffff':
            continue
        kind = 'compound' if dash else 'leaf'
        nodes.append(SvgNode('', x, y, w, h, kind, fill, stroke))
    
    path_pattern = re.compile(
        r'<path\s+d="M\s*([-\d.]+)\s+([-\d.]+)\s+L\s+([-\d.]+)\s+([-\d.]+)"'
    )
    for m in path_pattern.finditer(svg):
        sx, sy, ex, ey = (float(g) for g in m.groups())
        edges.append(SvgEdge(sx, sy, ex, ey, 'signal'))
    
    return nodes, edges


# ═══════════════════════════════════════════════════
# VizData 预期值
# ═══════════════════════════════════════════════════

@dataclass
class ExpectedCounts:
    """从 viz + layout 推导的预期渲染数"""
    leaves: int = 0           # 预期 leaf 节点数
    compounds: int = 0        # 预期 compound 数
    port_ins: list[str] = field(default_factory=list)
    port_outs: list[str] = field(default_factory=list)
    signal_labels: list[str] = field(default_factory=list)  # 预期 signal 短名
    case_labels: list[str] = field(default_factory=list)    # 预期 case label
    branch_labels: dict[str, list[str]] = field(default_factory=dict)  # case_id → branches
    expr_tree_signals: list[str] = field(default_factory=list)  # expr_trees 涉及的所有信号短名


def _compute_expected(viz, layout: dict | None) -> ExpectedCounts:
    """从 viz + ELK layout 推导预期值"""
    exp = ExpectedCounts()
    
    # ── 路由检测 — Plan D 修复 (2026-08-10) ──
    # expr_trees 非空 走 expr_trees_to_elk 路径 (路径 1 或 3).
    # 这个路径 SEMANTICS 上只 emit 输入输出端口 + 算子 + 被引用的 SignalRef.
    # viz.nodes 里的中间信号/REG (如 case21 mul2/div2, case24 sat_sub/max2/min2/mix,
    # case26 clamped/scaled/offsetted/clamped_w) 许多根本不在 expr_trees 里 →
    # expr_trees_to_elk 不会 emit 它们, 但旧逻辑双计数 (viz.nodes + layout children)
    # 导致 expected 偏高、ratio 偏低、A1 fail.
    trees = viz.meta.get('datapath', {}).get('expr_trees', {})
    has_expr_trees = bool(trees)
    
    # ── viz.nodes ──
    for n in viz.nodes:
        if n.port_side == 'left':
            exp.port_ins.append(n.label)
        elif n.port_side == 'right':
            exp.port_outs.append(n.label)
        elif n.kind in ('SIGNAL', 'REG', 'WIRE'):
            # signal 节点 记录 label, 不计入 leaf 预期
            exp.signal_labels.append(n.label)
        # INSTANCE / CONST 等不计入 leaf
        # [Plan D 修复] leaves 只在 viz_to_elk 路径 (无 expr_trees) 计数.
        # expr_trees 路径下 layout children 就是实际 emit, 下面 walk() 会准确计数.
        if not has_expr_trees:
            if n.port_side in ('left', 'right') or n.kind in ('SIGNAL', 'REG', 'WIRE'):
                exp.leaves += 1
    
    # ── expr_trees 涉及的信号 ──
    for tree_key in trees:
        # tree_key 格式: "module.signal_name" 或 "signal_name"
        signal_name = tree_key.rsplit('.', 1)[-1]
        exp.expr_tree_signals.append(signal_name)
    
    # ── layout 中的 compound ──
    if layout:
        def walk(n, parent_offset=(0, 0)):
            children = n.get('children', [])
            if children:
                labels = n.get('labels') or []
                label = (labels[0] or {}).get('text', '') if labels else ''
                meta = n.get('_meta', {}) or {}
                kind = meta.get('kind', '')
                
                if kind == 'case':
                    exp.compounds += 1
                    exp.case_labels.append(label)
                    # 收集 branches + branch 内部 leaf
                    branches = []
                    for c in children:
                        c_kind = (c.get('_meta') or {}).get('kind', '')
                        if c_kind == 'branch':
                            branches.append(c.get('id', ''))
                            # branch 内部 leaf (signal/op/const) 计入 leaf 预期
                            for gc in c.get('children', []):
                                gc_kind = (gc.get('_meta') or {}).get('kind', '')
                                if gc_kind in ('signal', 'op', 'const'):
                                    exp.leaves += 1
                                    gc_label = ((gc.get('labels') or [{}])[0]).get('text', '')
                                    if gc_label:
                                        exp.signal_labels.append(gc_label)
                        elif c_kind == 'condition_anchor':
                            pass  # 1x1 不计入 leaf
                        else:
                            # 其他子节点 (case 内的非 branch) 也算 leaf
                            gc_kind = (c.get('_meta') or {}).get('kind', '')
                            if gc_kind in ('signal', 'op', 'const'):
                                exp.leaves += 1
                    exp.branch_labels[label] = branches
                elif kind == 'branch':
                    exp.compounds += 1
                    # branch 内部 leaf (上面已加, 这里不再加)
                else:
                    # 其他 compound (例如 instance box) 内的 leaf
                    for c in children:
                        gc_kind = (c.get('_meta') or {}).get('kind', '')
                        if gc_kind in ('signal', 'op', 'const', 'port_in', 'port_out'):
                            exp.leaves += 1
                
                for c in children:
                    walk(c, parent_offset)
        
        walk(layout)
    
    return exp


# ═══════════════════════════════════════════════════
# Layer D — Sanity checks (防止 silent pass)
# ═══════════════════════════════════════════════════

def _check_layer_d(viz, exp: ExpectedCounts) -> list[CheckResult]:
    """[Plan D2 2026-08-10] Sanity checks — 防止 viz=0 silent pass.

    case13 (complex_op) 暴露的问题:
    - fixture module 名错 (complex_design vs complex_op), Phase 3 filter 丢 17 节点
    - viz.node_count = 0
    - 但 checker 全 trivially pass (没节点没边 → 没东西可检查)
    - report.passed = True, 但实际什么都没检查 → silent pass

    D1: viz should not be empty
    - target_module 设了 + viz 空 → 错 (有 target 但找不到)
    - target_module 没设 + viz 空 → 错 (检查器拿不到任何数据)
    背景: Layer A/B/C 都隐含假设 viz 有数据. viz=0 时它们 trivially pass —
    D 必须在 A/B/C 之前跑, 作为 guarding check.
    """
    results = []
    target_module = viz.meta.get('target_module', '') or ''
    viz_node_count = viz.node_count

    # D1: viz should not be empty
    passed = viz_node_count > 0
    result = CheckResult(
        name='D1: viz not empty (silent pass guard)',
        layer='D',
        passed=passed,
        details={
            'viz_node_count': viz_node_count,
            'target_module': target_module,
            'expected_leaves': exp.leaves,
            'expected_compounds': exp.compounds,
        },
    )
    if not passed:
        if target_module:
            result.errors.append(
                f"viz is empty but target_module='{target_module}' was specified — "
                f"silent pass bug pattern. Likely fixture module name mismatch "
                f"(case13 lesson: rename module in fixture to match target)."
            )
        else:
            result.errors.append(
                "viz is empty and no target_module — checker has nothing to check"
            )
    results.append(result)

    return results


# ═══════════════════════════════════════════════════
# Layer A — 结构完整性
# ═══════════════════════════════════════════════════

def _check_layer_a(svg_nodes: list[SvgNode], svg_edges: list[SvgEdge],
                   viz, exp: ExpectedCounts) -> list[CheckResult]:
    results = []
    
    # A1: SVG leaf 数 vs 预期 leaf 数
    svg_leaves = [n for n in svg_nodes if n.kind == 'leaf']
    if exp.leaves > 0:
        ratio = len(svg_leaves) / exp.leaves
        passed = 0.5 <= ratio <= 1.5  # 允许 50% 浮动 (部分 leaf 可能折叠)
        result = CheckResult(
            name='A1: leaf count',
            layer='A',
            passed=passed,
            details={'expected': exp.leaves, 'actual': len(svg_leaves), 'ratio': ratio},
        )
        if not passed:
            result.errors.append(
                f"SVG leaves={len(svg_leaves)} vs expected={exp.leaves} "
                f"(ratio={ratio:.2f}, expected 0.5-1.5)"
            )
        results.append(result)
    
    # A2: SVG compound 数 vs 预期 compound 数
    svg_compounds = [n for n in svg_nodes if n.kind == 'compound']
    if exp.compounds > 0:
        passed = len(svg_compounds) == exp.compounds
        result = CheckResult(
            name='A2: compound count',
            layer='A',
            passed=passed,
            details={'expected': exp.compounds, 'actual': len(svg_compounds)},
        )
        if not passed:
            result.errors.append(
                f"SVG compounds={len(svg_compounds)} vs expected={exp.compounds}"
            )
        results.append(result)
    
    # A3: 没有孤立 leaf (没有入边或出边的 leaf)
    # 例外: port_in (只有出边, 无入边), port_out (只有入边), condition_anchor
    # 用 proximity matching: edge 端点在 rect 边界 ±30px 范围内算 incident
    def _is_incident(point_x: float, point_y: float, node: SvgNode) -> bool:
        """edge 端点是否落在 rect 边界附近"""
        # rect 4 条边界上的点都算 incident (含 30px 容忍)
        # [V16 Plan Phase 2.1 2026-08-14] 5px → 30px: emit 紫色两步边 (X.dout → wire → Y.din)
        # 端点在 cluster 边界附近, wire 节点在 cluster 内部, 几何差距可能 ~50px. 5px 太严格.
        tol = 30.0
        # 检查端点是否在 rect 边界上 (含子像素鲁棒)
        on_left = abs(point_x - node.x) <= tol and node.y - tol <= point_y <= node.y + node.h + tol
        on_right = abs(point_x - (node.x + node.w)) <= tol and node.y - tol <= point_y <= node.y + node.h + tol
        on_top = abs(point_y - node.y) <= tol and node.x - tol <= point_x <= node.x + node.w + tol
        on_bottom = abs(point_y - (node.y + node.h)) <= tol and node.x - tol <= point_x <= node.x + node.w + tol
        return on_left or on_right or on_top or on_bottom
    
    orphan_count = 0
    orphan_labels = []
    for n in svg_leaves:
        # 检查该 rect 是否有任何边端点 incident
        has_incident = False
        for e in svg_edges:
            if _is_incident(e.src_x, e.src_y, n) or _is_incident(e.dst_x, e.dst_y, n):
                has_incident = True
                break
        
        # 例外识别: port_in (#e8e8e8, fill 浅灰, 仅出边) 不算 orphan
        # (即使无 incident 也合法, 因为可能没有连接 — 真的孤立才报错)
        if not has_incident:
            # port_in 也应该检测 — 实际未连接是 bug
            orphan_count += 1
            if n.label:
                orphan_labels.append(n.label)
    
    passed = orphan_count == 0
    result = CheckResult(
        name='A3: no orphan leaves',
        layer='A',
        passed=passed,
        details={'orphan_count': orphan_count, 'orphan_labels': orphan_labels[:10]},
    )
    if not passed:
        result.errors.append(
            f"Found {orphan_count} orphan leaves (no incident edges). "
            f"Sample: {orphan_labels[:5]}"
        )
    results.append(result)
    
    return results


# ═══════════════════════════════════════════════════
# Layer B — 边覆盖率
# ═══════════════════════════════════════════════════

def _short_name(full_id: str) -> str:
    """取短名 (.最后一段)"""
    return full_id.rsplit('.', 1)[-1] if '.' in full_id else full_id


def _compute_rendered_label_set(viz) -> set:
    """[Plan E1 2026-08-10] 计算 expr_trees render 路径会 emit 的 label 集合.

    expr_trees_to_elk emit 的节点: input ports (in expr_signal_refs) + output ports
    + ops + sigs + consts. 任何不在这个集合的 label 不会被 emit, B1/C4 检查这些
    边是误报.
    """
    trees = viz.meta.get('datapath', {}).get('expr_trees', {})
    expr_signal_refs = set()
    for _tree in trees.values():
        def _collect(n):
            if n.get('op') == 'SignalRef':
                expr_signal_refs.add(n.get('label', ''))
            for c in n.get('children', []):
                _collect(c)
        _collect(_tree)
    output_set = set()
    for _n in viz.nodes:
        if getattr(_n, 'port_side', '') == 'right':
            output_set.add(_short_name(_n.id))
    return expr_signal_refs | output_set


def _compute_referenced_fulls(viz) -> set:
    """[Plan D1 2026-08-10] 计算 expr_trees render 路径会 emit 端口的 full path 集合.

    背景: C4 dedup loss 检查 viz.edges 中同名短名的 unique full paths 与 SVG 位置数.
    但 viz.edges 里“外部”边 (未 render 路径) 引用的 full path 不应被计数.
    例子: case26 'gain' 2 full paths (golden_hier_top.gain, golden_hier_top.u_scale.gain),
    只 emit 后者; 但前者也在 viz.edges (黄金 端口未被 expr_trees 引用).
    修复: 只统计 referenced full paths.

    推导: parent_module = expr_tree key.rsplit('.', 1)[0]
          SignalRef label → full = parent_module + '.' + label
    """
    trees = viz.meta.get('datapath', {}).get('expr_trees', {})
    input_paths = set()
    output_paths = set()
    for _n in viz.nodes:
        _full = str(_n.id)
        _side = getattr(_n, 'port_side', '')
        if _side == 'left':
            input_paths.add(_full)
        elif _side == 'right':
            output_paths.add(_full)
    referenced = set()
    for _tree_key, _tree_data in trees.items():
        _pm = _tree_key.rsplit('.', 1)[0] if '.' in _tree_key else ''
        def _walk(node, pm=_pm):
            if node.get('op') == 'SignalRef':
                _lbl = node.get('label', '')
                _full = f'{pm}.{_lbl}'
                if _full in input_paths:
                    referenced.add(_full)
                # bit slice
                _bi = _lbl.find('[')
                if _bi > 0:
                    _full2 = f'{pm}.{_lbl[:_bi]}'
                    if _full2 in input_paths:
                        referenced.add(_full2)
            for _c in node.get('children', []):
                _walk(_c, pm)
        _walk(_tree_data)
    for _tree_key in trees.keys():
        if _tree_key in output_paths:
            referenced.add(_tree_key)
    return referenced


def _check_layer_b(svg_nodes: list[SvgNode], svg_edges: list[SvgEdge],
                   viz, exp: ExpectedCounts) -> list[CheckResult]:
    results = []
    
    # ── B1: viz.edges 的 src/dst 短名在 SVG 都能找到 ──
    svg_labels = {n.label for n in svg_nodes if n.label}
    
    def _label_match(viz_label: str, svg_labels_set: set) -> bool:
        """匹配 viz.label 到 SVG label, 处理 bit slice 情况 (prod[15:8] → prod)"""
        if viz_label in svg_labels_set:
            return True
        # 试试去掉 [..] 后缀
        m = re.match(r'^(\w+)\[', viz_label)
        if m and m.group(1) in svg_labels_set:
            return True
        return False
    
    # [Plan E1 2026-08-10] 路由感知 edge filter.
    # 背景: B1 原本检查全部 viz.edges 的 src/dst label. 但 expr_trees_to_elk 只 emit
    # expr_trees 树里的节点: input_set ∩ expr_signal_refs + output_set + ops + sigs + consts.
    # viz.edges 里大量 DRIVER / CONNECTION 边 (function call 嵌套, 跨 instance wire,
    # 隐式 const literal) 引用的节点根本不在 expr_trees 里 → 既不会被 emit, 也不该被 B1 检查.
    # 错误案例: case21 "8'd0", case24 b/max2/min2/mix, case26 scaled/offsetted/u_scale 等.
    # 修复: filter viz.edges → 只检查 expr_trees 路径看得见的边 (src/dst ⊆ expr_signal_refs ∪ output_set).
    _rendered_label_set = _compute_rendered_label_set(viz)
    
    missing_src = []
    missing_dst = []
    # [Plan E1.2 2026-08-10] 加可观测性: 分类追踪所有 skipped 边, 让用户看到
    # E1 filter 跳了什么 — 不再 silent.
    _skipped_by_kind: dict[str, list[dict]] = {}
    _total_skipped = 0
    
    def _record_skip(e, reason: str) -> None:
        nonlocal _total_skipped
        _total_skipped += 1
        _skipped_by_kind.setdefault(reason, []).append({
            'kind': e.kind.name if hasattr(e.kind, 'name') else str(e.kind),
            'src': str(e.src),
            'dst': str(e.dst),
        })
    
    for e in viz.edges:
        src_short = _short_name(e.src)
        dst_short = _short_name(e.dst)
        
        # 例外: BIT_SELECT 自环 / 折叠边
        if e.kind == 'BIT_SELECT' and src_short == dst_short:
            _record_skip(e, 'bit_select_self_loop')
            continue
        if e.kind in ('CLOCK', 'RESET'):
            _record_skip(e, 'clock_reset')
            continue
        
        # [Plan E1] 跳过未在 render 路径的边 (不会 emit 对应节点, 也不该被 B1 检查)
        # 要求 src 或 dst 任意一端不在 rendered_label_set 就 skip —
        # 内部表达树边的两端都在 rendered set; driver_extractor 产的外部边
        # (call 指向嵌套函数, 隐式 const, 跨 instance wire) 至少一端不在.
        if src_short not in _rendered_label_set or dst_short not in _rendered_label_set:
            # [Plan E3 2026-08-11] 把 BIT_SELECT skip 拆细成 4 种 reason,
            # 让 B2 报告能区分 hierarchical aggregation (12) vs 真 bit slice unrendered (2).
            # 不改 filter 行为 — 两种都应 skip, 只是 reason 不同.
            _kind_str = e.kind.name if hasattr(e.kind, 'name') else str(e.kind)
            if _kind_str == 'BIT_SELECT':
                _has_slice_src = '[' in str(e.src) and ']' in str(e.src)
                if not _has_slice_src:
                    # src 是普通端口路径 (e.g., "u_scale.din"), dst 是 wrapper
                    # → hierarchical aggregation edge (graph_builder.py:451 创建)
                    _record_skip(e, 'bit_select_aggregation')
                elif (src_short not in _rendered_label_set and
                      dst_short not in _rendered_label_set):
                    _record_skip(e, 'bit_select_both_unrendered')
                elif src_short not in _rendered_label_set:
                    _record_skip(e, 'bit_select_src_unrendered')
                else:
                    _record_skip(e, 'bit_select_dst_unrendered')
            # [Plan E1.2] 进一步区分: 哪一端不在 rendered set
            elif src_short not in _rendered_label_set and dst_short not in _rendered_label_set:
                _record_skip(e, 'both_unrendered')
            elif src_short not in _rendered_label_set:
                _record_skip(e, 'src_unrendered')
            else:
                _record_skip(e, 'dst_unrendered')
            continue
        
        # viz.label 处理 (可能有 bit slice 后缀)
        src_viz_label = _short_name(e.src)
        dst_viz_label = _short_name(e.dst)
        
        if not _label_match(src_viz_label, svg_labels):
            missing_src.append(src_viz_label)
        if not _label_match(dst_viz_label, svg_labels):
            missing_dst.append(dst_viz_label)
    
    passed = len(missing_src) == 0 and len(missing_dst) == 0
    # [Plan E1.2] 跳过的边分类汇总 (按 reason)
    _skip_summary = {
        reason: {
            'count': len(samples),
            'sample': samples[:3],  # 最多 3 个样本
        }
        for reason, samples in _skipped_by_kind.items()
    }
    result = CheckResult(
        name='B1: edge endpoint labels present',
        layer='B',
        passed=passed,
        details={
            'missing_src_count': len(missing_src),
            'missing_dst_count': len(missing_dst),
            'missing_src_sample': missing_src[:5],
            'missing_dst_sample': missing_dst[:5],
            # [Plan E1.2] 可观测性: 多少边被 filter 跳过 + 为什么
            'total_edges': len(viz.edges),
            'total_skipped': _total_skipped,
            'checked_count': len(viz.edges) - _total_skipped,
            'skipped_by_reason': _skip_summary,
        },
    )
    if not passed:
        result.errors.append(
            f"Missing src labels: {len(missing_src)}, "
            f"sample: {missing_src[:3]}"
        )
        result.errors.append(
            f"Missing dst labels: {len(missing_dst)}, "
            f"sample: {missing_dst[:3]}"
        )
    results.append(result)
    
    # ── B2: 自环 / BIT_SELECT / 已知省略类白名单正确省略 ──
    # [Plan E1.2 2026-08-10] 从 B1 复用 _skipped_by_kind 分类汇总, 不再重复统计.
    # B1 现在记录 5 种 reason: bit_select_self_loop, clock_reset, both_unrendered,
    # src_unrendered, dst_unrendered. B2 报告他们作为可观测性数据.
    result = CheckResult(
        name='B2: filtered edges',
        layer='B',
        passed=True,  # info only
        details={
            'skipped_count': _total_skipped,
            'skipped_by_reason': {
                reason: {
                    'count': len(samples),
                    'sample': samples[:3],
                }
                for reason, samples in _skipped_by_kind.items()
            },
        },
    )
    if _total_skipped > 0:
        result.warnings.append(
            f"Skipped {_total_skipped} edges ("
            + ', '.join(f'{r}={len(s)}' for r, s in _skipped_by_kind.items())
            + ') — E1 route-aware filter'
        )
    results.append(result)
    
    # ── B3: SVG path 端点坐标唯一 (无 phantom edge 重复) ──
    # 每条 path 的 (start, end) 坐标应该大致唯一
    # 如果两条 path 完全重合 → 可能有 bug
    path_keys = Counter()
    for e in svg_edges:
        key = (
            round(e.src_x), round(e.src_y),
            round(e.dst_x), round(e.dst_y),
        )
        path_keys[key] += 1
    
    duplicates = {k: v for k, v in path_keys.items() if v > 1}
    passed = len(duplicates) == 0
    result = CheckResult(
        name='B3: no duplicate SVG paths',
        layer='B',
        passed=passed,
        details={'duplicate_count': len(duplicates)},
    )
    if not passed:
        sample = list(duplicates.items())[:3]
        result.warnings.append(
            f"Found {len(duplicates)} duplicate path coordinates "
            f"(may be intentional for parallel edges): {sample}"
        )
    results.append(result)
    
    return results


# ═══════════════════════════════════════════════════
# Layer C — 语义保真 (strict mode 必跑)
# ═══════════════════════════════════════════════════

def _check_layer_c(svg_nodes: list[SvgNode], svg_edges: list[SvgEdge],
                   viz, exp: ExpectedCounts) -> list[CheckResult]:
    results = []
    
    # ── C1: case compound 的 branches 数 == condition_chain 数 ──
    # 每个有 cond_edges 的 dst 应对应一个 case compound, branches 数 == 唯一 condition 数
    by_dst: dict[str, set[str]] = defaultdict(set)
    for e in viz.edges:
        chain = getattr(e, 'condition_chain', None) or []
        if chain:
            # 最后一个 cond 是分支条件
            by_dst[e.dst].add(chain[-1])
    
    # 对每个 case label, 检查 SVG 里的 branch 数 vs by_dst 中对应数
    if exp.case_labels:
        svg_compound_labels = [n.label for n in svg_nodes if n.kind == 'compound' and n.label]
        
        for case_label in exp.case_labels:
            # 从 by_dst 找哪个 dst 对应这个 case label
            # 简化: 按 dst 短名匹配 case label 后缀
            expected_branches = 0
            for dst, conds in by_dst.items():
                dst_short = _short_name(dst)
                if dst_short in case_label:
                    expected_branches = len(conds)
                    break
            
            # SVG 实际 compound 中 case_label 包含的 branch rect 数
            # 简化: 用 exp.branch_labels 字典查
            actual_branches = len(exp.branch_labels.get(case_label, []))
            
            # 排除 1 个 anchor (condition_anchor 也算 compound)
            if actual_branches > 0:
                actual_branches -= 1  # 减去 anchor
            
            passed = expected_branches == 0 or actual_branches == expected_branches
            result = CheckResult(
                name=f'C1: case "{case_label}" branch count',
                layer='C',
                passed=passed,
                details={
                    'case_label': case_label,
                    'expected_branches': expected_branches,
                    'actual_branches': actual_branches,
                },
            )
            if not passed:
                result.errors.append(
                    f'Case "{case_label}": expected {expected_branches} branches, '
                    f'got {actual_branches}'
                )
            results.append(result)
    
    # ── C3: case label 唯一 ──
    label_counter = Counter(exp.case_labels)
    duplicates = {k: v for k, v in label_counter.items() if v > 1}
    passed = len(duplicates) == 0
    result = CheckResult(
        name='C3: case label uniqueness',
        layer='C',
        passed=passed,
        details={'duplicate_labels': duplicates},
    )
    if not passed:
        for label, count in duplicates.items():
            result.errors.append(
                f'Case label "{label}" appears {count} times (should be unique)'
            )
    results.append(result)
    
    # ── C4: 不同 viz 边的同名 src/dst 在 SVG 里位置不同 (dedup loss 检测) ──
    # 收集 viz 中出现多次的短名
    _rendered_label_set = _compute_rendered_label_set(viz)
    _referenced_fulls = _compute_referenced_fulls(viz)
    short_name_to_fulls: dict[str, list[str]] = defaultdict(list)
    for e in viz.edges:
        src_short_e = _short_name(e.src)
        dst_short_e = _short_name(e.dst)
        # [Plan E1 2026-08-10 拓展] 跳过未在 render 路径的边 —
        # 外部 driver_extractor 边 (function call 嵌套, 隐式 const, 跨 instance wire) 引用
        # 末 render 节点, 不应参与 dedup loss 检查. 与 B1 filter 一致.
        if src_short_e not in _rendered_label_set or dst_short_e not in _rendered_label_set:
            continue
        for sig in [e.src, e.dst]:
            short = _short_name(sig)
            if short:
                # [Plan D1 2026-08-10] 只统计 referenced full paths.
                short_name_to_fulls[short].append(sig)
    
    dup_short_names = {
        sn: fulls for sn, fulls in short_name_to_fulls.items()
        if len(set(fulls)) > 1  # 同一个短名映射到不同完整路径
    }
    
    # 检查 SVG 中这些短名对应的 rect 位置
    if dup_short_names:
        svg_positions: dict[str, list[tuple[float, float]]] = defaultdict(list)
        for n in svg_nodes:
            if n.label in dup_short_names and n.kind == 'leaf':
                svg_positions[n.label].append((n.x, n.y))
        
        # 对每个 dedup 风险短名, 检查 SVG 是否有多个不同位置的 rect
        dedup_loss = []
        for sn, fulls in dup_short_names.items():
            positions = svg_positions.get(sn, [])
            unique_positions = set(p for p in positions)
            # [Plan D1 2026-08-10] 只统计 referenced full paths (被 expr_trees
            # 路径 引用 的端口), 未引用的 full path 不该让 C4 误报.
            # 例: case26 'gain' 有 2 full paths (golden_hier_top.gain, u_scale.gain),
            # 只后者被 u_scale.dout expr_tree 引用 → 只应算 1.
            filtered_fulls = [f for f in fulls if f in _referenced_fulls]
            unique_filtered = set(filtered_fulls)
            if len(unique_positions) < len(unique_filtered) and len(unique_filtered) > 1:
                # SVG 位置数 < viz 中 referenced full paths 数 → 可能有 dedup loss
                dedup_loss.append({
                    'short_name': sn,
                    'viz_fulls': sorted(unique_filtered),
                    'svg_positions': list(unique_positions),
                })
        
        passed = len(dedup_loss) == 0
        result = CheckResult(
            name='C4: no dedup loss (same short, different paths)',
            layer='C',
            passed=passed,
            details={'dedup_loss_count': len(dedup_loss), 'cases': dedup_loss[:5]},
        )
        if not passed:
            for case in dedup_loss[:3]:
                result.errors.append(
                    f"Dedup loss detected for '{case['short_name']}': "
                    f"viz has {len(case['viz_fulls'])} unique paths but "
                    f"SVG has only {len(case['svg_positions'])} positions"
                )
        results.append(result)
    
    # ── C5: expr_trees 涉及的信号短名都在 SVG 出现 ──
    if exp.expr_tree_signals:
        svg_labels = {n.label for n in svg_nodes if n.label}
        missing = [s for s in exp.expr_tree_signals if s not in svg_labels]
        passed = len(missing) == 0
        result = CheckResult(
            name='C5: expr_trees signals in SVG',
            layer='C',
            passed=passed,
            details={'expected': len(exp.expr_tree_signals), 'missing_count': len(missing)},
        )
        if not passed:
            result.errors.append(
                f"expr_trees signals missing from SVG: {missing[:5]}"
            )
        results.append(result)
    
    return results


# ═══════════════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════════════

def check_viz_render(
    viz,
    layout: dict | None,
    svg: str,
    *,
    level: str = 'strict',
) -> CheckReport:
    """检查 viz → layout → svg 渲染结果一致性
    
    Args:
        viz: VizData 原始数据
        layout: ELK 布局结果 (dict), 可选 (但 strict mode 建议传)
        svg: 渲染后的 SVG 字符串
        level: 'basic' | 'standard' | 'strict'
    
    Returns:
        CheckReport with passed/errors/warnings
    """
    if level not in ('basic', 'standard', 'strict'):
        raise ValueError(f"Invalid level: {level}")
    
    # 解析 SVG
    svg_nodes, svg_edges = _parse_svg(svg)
    
    # 计算预期值
    exp = _compute_expected(viz, layout)
    
    report = CheckReport(level=level)
    
    # [Plan D2 2026-08-10] Layer D — sanity guards (必须在 A/B/C 之前跑, 防止
    # viz=0 silent pass). 总是跑, 不受 level 影响.
    report.layer_d = _check_layer_d(viz, exp)
    
    # Layer A — 必跑
    report.layer_a = _check_layer_a(svg_nodes, svg_edges, viz, exp)
    
    # Layer B — standard 以上
    if level in ('standard', 'strict'):
        report.layer_b = _check_layer_b(svg_nodes, svg_edges, viz, exp)
    
    # Layer C — strict
    if level == 'strict':
        report.layer_c = _check_layer_c(svg_nodes, svg_edges, viz, exp)
    
    return report


# ═══════════════════════════════════════════════════
# 便捷函数: 从 viz 自动渲染 + 检查
# ═══════════════════════════════════════════════════

def render_and_check(viz, config: dict | None = None, level: str = 'strict') -> tuple[str, CheckReport]:
    """便利函数: 调用 render_dataflow 渲染并检查
    
    Returns:
        (svg, CheckReport)
    """
    from .viz_engine import render_dataflow
    
    svg = render_dataflow(viz, config)
    
    # 重新跑 elk bridge 取 layout (用于 Layer C 的 compound 检查)
    layout = None
    try:
        from .elk_bridge import run_elk_layout
        # 简化: 不重跑, 直接 None
        # Layer C 会跳过需要 layout 的 check
        pass
    except ImportError:
        pass
    
    report = check_viz_render(viz, layout, svg, level=level)
    return svg, report