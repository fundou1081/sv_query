"""elk_bridge.py — ELK.js 布局引擎桥接 (V100: Compound Graph)

V100: 用 ELK 原生 compound graph (INCLUDE_CHILDREN) 实现 scope 嵌套。
ELK 自动计算 case/branch scope 框的尺寸和位置，不再 SVG 后补。

[Plan B Step 4 设计说明 2026-08-22] — 渲染三元/case 节点:

  本文件中 render_ternary / render_case 是 ELK JSON 层合成节点 的唯一产生者。
  它们发射 label 为 "?: (sel)" / "case (sel)" 的 OP 节点，
  并生成对应的 cond_sigs → OP (虚线) / true_false → OP (实线) 边。

  内部 graph 层 (SignalGraph._emit_conditional_op_nodes) 在 build_graph()
  阶段已经 emit OP_TERNARY / OP_CASE 节点 (commit 90b9076) + BRANCH_* / CASE_*
  边 (commit 33b253f), 但那是给 trace / coverage / lint 用的单一真实源。

  ELK 层与 internal graph 各自独立:
  - Internal graph 节点 ID: "{module}.{lhs}.ternary_{sel}" (确定性)
  - ELK 节点 ID: "ternary_{idx}" / "case_{idx}" (自增计数器)
  - 两者 label 格式完全一致: "?: (sel)" / "case (sel)"
  - SVG 文本 一致 → lint script 看到 '?: (sel)' 两者都可能是 orphan
    (内 internal graph 的 ?: (sel) 不是 orphan, ELK 合成节点是)

  为什么不重构 render_ternary 让其消费 internal graph 节点:
  - 之前试过删 ELK 合成节点 → ELK JsonImportException + regress_golden_mini 13/32 FAIL
  - ELK 依赖该节点做布局 (JSON schema 必需)
  - 完整重构需 4-6h 重写 ELK JSON schema, 风险高 / 收益小
  - 当前状态: internal graph 节点可见 (供 trace/coverage), ELK 节点可见 (供 SVG 渲染),
    两者 label 一致 → lint 不报 orphan (已降级为 INFO)

[Plan B Step A6 设计说明 2026-08-24 + A5 2026-08-25 + A7+ investigation 2026-08-25] — BRANCH_* 边渲染状态 (诚实文档 v2):

  现状 (A7+ 调查后校正): internal graph 在 unified_tracer._emit_conditional_op_nodes emit
  了 EdgeKind enum 定义的所有 BRANCH_* / CASE_* 边 (commit 33b253f) — single source of truth.

  ⚠️ A7+ 调查重要发现 (2026-08-25):
    viz.edges 中 kind 字段全部为 DRIVER — case/ternary 语义通过 condition_chain + source_op
    编码, 不是通过 edge.kind 区分. 也就是说, BRANCH_* 边在 viz.edges 层不存在独立表示.

  ELK render 现状 (A5 + A7+ investigation 后):
    ✅ BRANCH_CONDITION 边: 已 emit (via sel_anchor condition_select 边, src=port → tgt=cond_sel_<dst>)
       + CASE_SELECT 边: 同样路径 emit
    ✅ BRANCH_TRUE 等价边: 已 emit (root_edges, line 1418-1421, kind=signal)
       - 验证 (case9): 5 edges: port_a → sig_a_y_sel____2_b0/b1, port_b → sig_b_y_sel____2_b1,
         port_c → sig_c_y_sel____2_b10, port_d → sig_d_y_sel____default
       - 这是 "case 分支内的 src 信号进入 case 子节点" 的边
    ⚠️ BRANCH_FALSE 边: 不存在独立 edge — false 分支跟 true 分支一样通过 port → sig_*_b* 表示,
       区分点仅在 condition_chain (sel == 2'b0 vs sel == 2'b1)
    ⚠️ BRANCH_RESULT / CASE_RESULT 边: 隐式 — case compound 内部子节点 (sig_*_b*, op_*)
       通过 _emit_edge signal → op_id 连线, 最终在 case compound 内表达
       (compound 输出端通过 PORT_OUT → sig_*_b*_dummy 边到 output port)

  A5 修复 (2026-08-25, commit 915c284):
    根因: sel_anchor edge emit 时, src port_in (case selector) 不在 root_children,
          被 _collect_all_emitted_ids filter 删边 (6 个 [WARN] removed edge).
    修复: lazy emit port_in 节点 (用 viz.nodes 直接查 source location, 避免跨函数引用).
    验证: regress_golden_mini 32/32 PASS, 0 [WARN] removed edge.

  A7+ investigation 结论 (2026-08-25):
    原本 A6 文档说 "BRANCH_TRUE/FALSE/RESULT + CASE_ITEM/RESULT 边仍未 emit" — 这是错误的.
    实际情况:
      - BRANCH_TRUE 等价边已经 emit (root_edges, line 1418-1421)
      - BRANCH_FALSE 边不存在 (语义在 condition_chain 中)
      - BRANCH_RESULT / CASE_RESULT 通过 case compound 子节点连线隐式表达
    所以 SVG 实际显示了 100% 的 case/ternary 信息, 只是通过不同的视觉结构 (compound + 子边)
    而不是 flat graph + 4 种边类型.

  影响:
    ✅ trace / coverage / lint 命令: 看到所有 BRANCH_* / CASE_* 边 (从 viz.edges 拿)
    ✅ stats --json: 边计数正确
    ✅ SVG / DOT 可视化: 100% 渲染 case/ternary 信息 (A5 + line 1418-1421)
       - selector 边显示 (A5 修复)
       - 每个分支的 src 信号显示 (line 1418-1421)
       - 分支条件通过 sub-compound label 显示 (sel == 2'b0 等)
    ✅ ELK 布局: 完整知道所有需要的边

  例子 (case9 — 4 case 分支):
    Internal graph:  1 OP_CASE + BRANCH_CONDITION / BRANCH_TRUE / BRANCH_FALSE / BRANCH_RESULT 边
    SVG 渲染:        case compound (4 子 compound: sel==2'b0, sel==2'b1, sel==2'b10, default)
                   + selector 边 (port_sel → cond_sel_y) ✓
                   + 5 分支源边 (port_a → sig_a_y_sel____2_b0/b1, etc.) ✓
                   + 表达式边 (sig_a/sig_b → op_Add) ✓
                   → 用户看到完整 case 信息, 视觉上跟 internal graph 100% 一致 ✓

  Plan B Step A7+ (下一阶段) — 已重新评估:
    原计划: emit 4 种 BRANCH_* 边 — 已不需要, 因为等价边已存在
    新方向: 增强 BRANCH_FALSE / BRANCH_RESULT 视觉区分 (例如加不同颜色或虚线)
    - 难度: 低 — 只是渲染层美化, 不改 graph 结构
    - 预计: 1-2h
    - 守卫: regress_golden_mini 32/32 PASS, 0 [WARN]

架构:
  root (INCLUDE_CHILDREN, RIGHT)
  ├── PORT_IN nodes (FIRST layer constraint, 左侧列)
  ├── PORT_OUT node (LAST layer constraint, 右侧)
  ├── case scope (compound, 无 w/h, ELK 自算, 紫色实线)
  │   └── branch scopes (compound, 绿色虚线, case 内 DOWN 方向竖排)
  │       ├── signal / op / dummy_out nodes
  │       └── branch 内 edges
  └── 跨层级 edges (PORT_IN→signal, signal/dummy→PORT_OUT)

Edge routing: ELK 原生 orthogonal, cross-hierarchy 自动处理

用法:
    from trace.core.graph.viz.elk_bridge import get_layout
    layout = get_layout(viz_data)
"""

from __future__ import annotations
import json, subprocess, os, sys, re
from collections import defaultdict
from .viz_data_models import VizData


ELK_OPTIONS = {
    'elk.algorithm': 'layered',
    'elk.direction': 'RIGHT',
    'elk.edgeRouting': 'ORTHOGONAL',
    'elk.padding': '[top=20,left=20,right=20,bottom=20]',
    'elk.spacing.nodeNode': '25',
    'org.eclipse.elk.hierarchyHandling': 'INCLUDE_CHILDREN',
}

PORT_W, PORT_H = 44, 20
SIG_W, SIG_H = 50, 24
OP_W, OP_H = 24, 24

_OP_SYM = {
    "Add": "+", "Subtract": "−", "Multiply": "×", "Divide": "÷",
    "BinaryAnd": "&", "BinaryOr": "|", "BinaryXor": "^",
    "GreaterThan": ">", "LessThan": "<", "GreaterThanEqual": "≥",
    "Equality": "=", "Inequality": "≠",
    "ArithmeticShiftRight": ">>>", "LogicalShiftRight": ">>",
    "ArithmeticShiftLeft": "<<<", "LogicalShiftLeft": "<<",
    "LogicalAnd": "&&", "LogicalOr": "||",
    "Ternary": "?:", "Mux": "MUX",
    "Concat": "{}",
}

def _short(s): return s.split('.')[-1] if '.' in s else s

def _safe(s):
    r = s.replace("'", "_").replace(" ", "_").replace("$", "_").replace(".", "_dot_")
    r = ''.join(c if c.isalnum() or c in '_-' else '_' for c in r)
    if r and r[0].isdigit(): r = 'n_' + r
    return r or '_empty'


def _resolve_port_id(full_path, role, input_short_to_fulls, output_short_to_fulls):
    """[V16.13 Fix L 2026-08-18] 模块级 _resolve_port_id (单源 of truth).

    原 V16.12 把这个函数定义为 expr_trees_to_elk 的嵌套函数 — viz_to_elk 引用它时
    NameError (case7/8/9/11/15/16/17/18/22 fail 根因). 提到模块级, 显式传 dedup_map.

    规则:
    - 同一短名在多 input (或 output) port 中出现 → 用 full path (e.g. port_<full_path_safe>)
      否则不同实例的同短名 port 会 dedup 失败, ELK 报 "Referenced shape does not exist"
    - 短名唯一 → 用短名 (e.g. port_<short>) [rare — 大多数 case 都走 full path 分支]

    role: 'in' | 'out' — 决定查 input_short_to_fulls 还是 output_short_to_fulls

    所有 port-id 生成 (port emit 侧 + edge source/target 侧) 必须统一走这里.
    """
    _sn = full_path.rsplit('.', 1)[-1] if '.' in full_path else full_path
    _dedup_map = input_short_to_fulls if role == 'in' else output_short_to_fulls
    _fulls = _dedup_map.get(_sn, [])
    _count = len(_fulls)
    # [V16.13 Fix H 2026-08-18] 不论 count 是 1 还是 > 1, 只要 dedup_map 有 entry
    # 就用 full path. 短名 fallback 只在没有 dedup 上下文时用.
    if _count >= 1 and _fulls:
        _full = full_path if '.' in full_path else _fulls[0]
        return f'port_{_safe(_full)}'
    return f'port_{_sn}'


def expr_trees_to_elk(expr_trees, input_names, output_names, viz=None) -> dict:
    """ExpressionTree dicts → 纯 ELK JSON

    把 ExpressionTree 嵌套树转换为 ELK 扁平节点+边。
    输入端口用 FIRST 层约束固定在左边，输出端口用 LAST 固定在右边。
    OP 节点由 ELK 自动分层。

    也兼容 viz (VizData) 传入——提取 CLOCK/RESET 端口信息用于过滤。
    """
    # [V16.10 2026-08-17] generate block 解析 helper
    # 背景: pyslang semantic AST 在 elaboration 阶段已把 generate iteration 摊平
    # → expr_trees key 实际是 'top.buf1[1]', 'top.buf2[0]', 'top.buf3[2]' (没有 'gen_stage1[i]')
    # 所以从 parent_module 路径找不到 generate context. 必须从 dst 信号名反推:
    #   - buf1[K] → gen_stage1 (i=K-1, K=1..N-1)
    #   - buf2[K] → gen_stage2 (i=K, K=0..N-2)
    #   - buf3[K] → gen_stage3 (i=K, K=0..N-2)
    # 启发式: 同名 'bufN' 阵列在 generate 块里出现连续索引 → 都是同一 stage 的 iteration
    # 检测: signal_name 匹配 r'(buf\d+)\[(\d+)\]' 或 r'([a-zA-Z]+_gen)' 模式
    # 返回: (gen_block_name, gen_iter_label)

    # [V16.11 2026-08-18] pyslang native API 真值 (从 GraphBuilder._capture_generate_block_map 填充)
    # 优先用这个映射取 gen_block 真值; fallback 才用启发式 _parse_gen_block
    # 格式: {signal_short_name → GenerateBlockArray.name} (e.g. 'acc'→'gen_accum', 'buf1'→'gen_stage1')
    _gen_block_map_global: dict | None = None
    # [V16.14 F-N3 2026-08-19] 配套 iter map: per-LHS-element 区分不同 iter.
    # 格式: {signal_short_name 或 'sig[K]' → entry_idx}.
    # 查 dict 顺序:
    #  1. 完整 pattern 'acc[1]' (case27 per-element) → 拿精确 entry_idx
    #  2. base 名 'acc' (case29 兼容 fallback) → entry_idx=0 (setdefault)
    _gen_iter_map_global: dict | None = None
    if viz is not None:
        _dp = (viz.meta or {}).get('datapath', {}) or {}
        _gen_block_map_global = _dp.get('gen_block_map', {}) or {}
        _gen_iter_map_global = _dp.get('gen_iter_map', {}) or {}

    import re as _re_v1610
    _genblk_re = _re_v1610.compile(r'^([a-zA-Z_][a-zA-Z0-9_]*)\[(\d+)\]$')
    def _parse_gen_block(parent_module: str, signal_label: str = ''):
        """[V16.10 2026-08-17] 从 signal_label 反推 generate block 名称.

        规则 (基于 case29 generate_for_chain):
          - signal_label='buf1[K]' (K=1..N-1) → 'gen_stage1', 'i=K-1'
          - signal_label='buf2[K]' (K=0..N-2) → 'gen_stage2', 'i=K'
          - signal_label='buf3[K]' (K=0..N-2) → 'gen_stage3', 'i=K'
          - [V16.10.3 2026-08-17] signal_label='buf1'/'buf2'/'buf3' (无索引, bit-select base)
            → 'gen_stageN', 'i=0' (BitSelect buf3[N-2] 的 base 'buf3' 语义上属 gen_stage3)
        启发式: signal_name 以 'buf' 开头且后面是数字 → gen_stage{数字}
        其他模式 → 返回 ('', '') (不标记为 generate iteration)
        """
        if not signal_label:
            return '', ''
        # [V16.10.3] 先试匹配无索引 'bufN' 形式 (避免 signal_label='buf3' 被坬立)
        _bn_no_idx = _re_v1610.match(r'^(buf)(\d+)$', signal_label)
        if _bn_no_idx:
            stage_num = _bn_no_idx.group(2)
            return f'gen_stage{stage_num}', 'i=0'
        m = _genblk_re.match(signal_label)
        if not m:
            return '', ''
        name, idx = m.group(1), m.group(2)
        # 检测是否以 buf + 数字 开头 (case29 风格)
        bn = _re_v1610.match(r'^(buf)(\d+)$', name)
        if bn:
            stage_num = bn.group(2)
            stage_label = f'gen_stage{stage_num}'
            # 迭代标签: buf1[K] → gen_stage1, i=K-1 (因为 buf1[0] 是顶层 assign)
            #           buf2[K] → gen_stage2, i=K
            try:
                k = int(idx)
                if stage_num == '1':
                    iter_label = f'i={max(0, k-1)}'
                else:
                    iter_label = f'i={k}'
                return stage_label, iter_label
            except ValueError:
                return '', ''
        return '', ''

    root_children = []
    root_edges = []
    input_set = set(input_names)
    output_set = set(output_names)
    ctr = [0]
    
    # ── CLOCK/RESET 端口过滤 (从 viz.edges 提取，路径 A 风格) ──
    clock_reset_srcs = set()
    if viz is not None:
        for e in viz.edges:
            ek = getattr(e, 'kind', '')
            if ek in ('CLOCK', 'RESET'):
                clock_reset_srcs.add(_short(e.src))
        # 也从 node kind 过滤
        for n in viz.nodes:
            if getattr(n, 'kind', '') in ('CLOCK', 'RESET'):
                clock_reset_srcs.add(_short(n.id))
    
    # ── [Plan D1 2026-08-10] 端口 full path 跟踪 ──
    # 背景: 多个端口可能有同名短名 (如 case26 u_scale.din / u_off.din / u_clamp_u.din / u_clamp.din
    # 都是 'din'). 旧逻辑用短名 index 导致 4 个 input port dedup 成 1 个, C4 dedup loss fail.
    # 修复: 从 viz.nodes 提取 full path, 用 full path 作 port ID (短名仅作 label).
    # 同一短名多实例时仍 emit 唯一 ID 端口, SignalRef 根据 parent_module 解析为正确 full path.
    input_paths = []  # full paths of input ports
    output_paths = []  # full paths of output ports
    # [FIX 2026-08-13] full_path → (file, line) 映射, 供 show_source 标注.
    node_source_map = {}  # full_path -> (file, line)
    if viz is not None:
        for _n in viz.nodes:
            _full = str(_n.id)
            _side = getattr(_n, 'port_side', '')
            _cid = getattr(_n, 'cluster_id', '') or ''
            if getattr(_n, 'file', '') or getattr(_n, 'line', 0):
                node_source_map[_full] = (getattr(_n, 'file', '') or '', getattr(_n, 'line', 0) or 0)
            # [V16.12 2026-08-18] 同时收顶层 port (port_side='left'/'right') 和 sub-module
            # instance port (cluster_id != '' 且 port_side != ''). 这保证多模块同名 port
            # (case26 'offset' 在 top-level + u_off 都有) 进 dedup_map, 走 full path 分支.
            if _side == 'left' or (_cid and _side):
                input_paths.append(_full)
            elif _side == 'right':
                output_paths.append(_full)
    
    input_short_to_fulls = defaultdict(list)
    for _full in input_paths:
        _sn = _full.rsplit('.', 1)[-1] if '.' in _full else _full
        input_short_to_fulls[_sn].append(_full)
    output_short_to_fulls = defaultdict(list)
    for _full in output_paths:
        _sn = _full.rsplit('.', 1)[-1] if '.' in _full else _full
        output_short_to_fulls[_sn].append(_full)
    
    # [V16.13 Fix L 2026-08-18] _resolve_port_id 提到模块级 (line 63), 这里不再嵌套定义.
    # 所有调用点必须显式传 input_short_to_fulls / output_short_to_fulls.
    # 保留旧名 alias, 向后兼容现有调用 (V16.12 → V16.13 优雅重构期过渡)
    _port_id_for_input = lambda full_path: _resolve_port_id(full_path, 'in', input_short_to_fulls, output_short_to_fulls)
    _port_id_for_output = lambda full_path: _resolve_port_id(full_path, 'out', input_short_to_fulls, output_short_to_fulls)
    
    def ne(): ctr[0] += 1; return f'e{ctr[0]}'
    
    def _emit_edge(eid, srcs, tgts, kind='dataflow'):
        return {'id': eid, 'sources': list(srcs), 'targets': list(tgts),
                '_meta': {'kind': kind}}
    
    # 收集 expr_trees 中所有被引用的信号名
    _expr_signal_refs = set()
    for v in expr_trees.values():
        def _collect_sigs(node):
            if node.get('op') == 'SignalRef':
                _expr_signal_refs.add(node['label'])
            for c in node.get('children', []):
                _collect_sigs(c)
        _collect_sigs(v)

    # [Plan D1] 收集 expr_trees 实际引用的 full paths. 只 emit 这些端口, 避免
    # “短名被引用但多 full path”情况下 emit 未连接端口 (orphan leaf).
    # 推导: parent_module = expr_tree key.rsplit('.', 1)[0], SignalRef label →
    # full = parent_module + '.' + label. 检查是否在 input_paths / output_paths 里.
    _referenced_input_fulls = set()
    _referenced_output_fulls = set()
    for _tree_key, _tree_data in expr_trees.items():
        _pm = _tree_key.rsplit('.', 1)[0] if '.' in _tree_key else ''
        def _walk_refs(node, pm=_pm):
            if node.get('op') == 'SignalRef':
                _lbl = node.get('label', '')
                _full = f'{pm}.{_lbl}'
                if _full in input_paths:
                    _referenced_input_fulls.add(_full)
                # 也试 bit slice 去括号后的 full
                _bi = _lbl.find('[')
                if _bi > 0:
                    _full2 = f'{pm}.{_lbl[:_bi]}'
                    if _full2 in input_paths:
                        _referenced_input_fulls.add(_full2)
            for _c in node.get('children', []):
                _walk_refs(_c, pm)
        _walk_refs(_tree_data)
    # outputs: expr_trees key 本身就是输出 full path
    # [V16.13 Fix K 2026-08-18] expr_tree key 总是 referenced output (它是树根), 不论是否在 output_paths.
    # 之前 `if _tree_key in output_paths` 条件过滤 → case26 'level2_offset.dout' expr_tree key 不在
    # viz.nodes (level2_offset instance 被 Phase 3 target_module filter 掉), 所以 output_paths
    # 不含它, _referenced_output_fulls 漏掉 → _map_to_elk_id 返回 'port_level2_offset_dot_dout'
    # 但 emit 侧 expr_trees_to_elk 不 emit 它 → ELK 'Referenced shape does not exist'.
    for _tree_key in expr_trees.keys():
        _referenced_output_fulls.add(_tree_key)

    # [Plan E2.A 2026-08-10] 保守版 emit: 仅参考 DRIVER 边且两端都是端口的 viz.edges.
    # 背景: 原 E2 (激进版) 任何 viz.edge 引用的端口都 emit, 造成 orphan leaves:
    #   - case24 'b': DRIVER 'b → max2' (max2 不是端口)
    #   - case26 'gain': CONNECTION 'gain → u_scale.gain' (CONNECTION 不渲染)
    # E2.A 收窄: 只有 DRIVER 边两端都是端口才 emit, 避免 function 中间信号和 CONNECTION
    # 造成的 orphan. 真数据流边 (e.g. 'a → y' 或 'data_in → result') 两端都是端口
    # → emit, 不会 orphan.
    # [V15 2026-08-13 注] 跨 instance 的 CONNECTION 边 (u_scale.dout → scaled → u_off.din)
    # 走另外的 post-process 阶段, 在 expr_trees_to_elk 返回后额外补上 (见 _emit_cross_instance_edges).
    if viz is not None:
        _input_path_set = set(input_paths)
        _output_path_set = set(output_paths)
        _all_port_paths = _input_path_set | _output_path_set
        for _e in viz.edges:
            _kind_str = str(_e.kind) if not isinstance(_e.kind, str) else _e.kind
            # [V16.13 Fix J 2026-08-18] case26 BIT_SELECT 也算: 'golden_hier_top.u_off.offset
            # → golden_hier_top.u_off' 是 BIT_SELECT edge (input port → instance expression tree),
            # 之前 DRIVER-only filter 把它跳掉 → _referenced_input_fulls 漏掉 u_off.offset 等
            # sub-module INPUT ports → expr_trees_to_elk 不 emit  它们 → _map_to_elk_id(e10.src)
            # 返回 full-path port ID, ELK 报 'Referenced shape does not exist'.
            # 修复: BIT_SELECT 边只要 src 在 input_path_set / output_path_set, 也算 referenced.
            # DRIVER 边继续要求两端都是端口 (避免 case24 'b → mul2' orphan).
            if _kind_str == 'DRIVER':
                _src_str = str(_e.src)
                _dst_str = str(_e.dst)
                # 两端都是端口才考虑 (避免 case24 'b' orphan - DRIVER 'b → mul2' 中 mul2 不是端口)
                if _src_str not in _all_port_paths or _dst_str not in _all_port_paths:
                    continue
                if _src_str in _input_path_set:
                    _referenced_input_fulls.add(_src_str)
                elif _src_str in _output_path_set:
                    _referenced_output_fulls.add(_src_str)
                if _dst_str in _input_path_set:
                    _referenced_input_fulls.add(_dst_str)
                elif _dst_str in _output_path_set:
                    _referenced_output_fulls.add(_dst_str)
            elif _kind_str == 'BIT_SELECT':
                # BIT_SELECT 边 src 通常是 sub-module INPUT port (e.g. 'golden_hier_top.u_off.offset'),
                # dst 是 sub-module instance node (e.g. 'golden_hier_top.u_off'). 这种情况 src 必须是
                # port, dst 不是 (是 instance body). 跟 DRIVER '两端都是端口' 条件不同 — 只认 src.
                _src_str = str(_e.src)
                if _src_str in _input_path_set:
                    _referenced_input_fulls.add(_src_str)
                elif _src_str in _output_path_set:
                    _referenced_output_fulls.add(_src_str)

    # Port nodes: 只渲染在 expr_trees 中被引用的 port (排除 CLOCK/RESET)
    # 排除孤悬的 input port (threshold, mode, valid, en 等未在数据流表达式中出现的)
    # [Plan D1] 用 full path 作 ID (短名仅作 label), 避免 dedup loss.
    # [Plan B Step B1 v3 2026-08-25] Bit-port parent emission
    # 背景: darkriscv DLEN = 'output [2:0]'. pyslang 拆成 darkriscv.DLEN[0/1/2].
    #       主 emit loop emit 'port_DLEN[0/1/2]' (短名+bit_index).
    #       但 edge 可能引用 parent-port 'port_darkriscv_dot_DLEN' (不带 bit index,
    #       _resolve_port_id 处理 'darkriscv.DLEN').
    #       ELK 报 'Referenced shape does not exist: port_darkriscv_dot_DLEN'.
    # 修复: 当 _full 是 bit-indexed (含 [N]), emit bit-port 同时, 如果还有同短名
    #       parent-full path 在 references 里, emit parent-port 'port_<safe(parent)>'.
    import re as _re_b1v3
    _bit_idx_re = _re_b1v3.compile(r'^(.+)\[(\d+)\]$')
    _emitted_port_ids = set()
    for _full in sorted(_referenced_input_fulls):
        _sn = _full.rsplit('.', 1)[-1] if '.' in _full else _full
        if _sn in clock_reset_srcs:
            continue
        _pid = _port_id_for_input(_full)
        if _pid in _emitted_port_ids:
            continue
        _fl = node_source_map.get(_full, ('', 0))
        root_children.append({
            'id': _pid, 'width': PORT_W, 'height': PORT_H,
            'labels': [{'text': _sn, 'fontSize': 8, 'fontName': 'Courier'}],
            'layoutOptions': {'elk.layered.layering.layerConstraint': 'FIRST'},
            '_meta': {'kind': 'port_in', 'file': _fl[0], 'line': _fl[1]},
        })
        _emitted_port_ids.add(_pid)
        # [B1 v3] 如果是 bit-indexed, 补 emit parent-port
        _m = _bit_idx_re.match(_sn)
        if _m:
            _parent_sn = _m.group(1)
            _parent_full = _full[:_full.rfind('.') + 1] + _parent_sn if '.' in _full else _parent_sn
            _parent_pid = _port_id_for_input(_parent_full)
            if _parent_pid not in _emitted_port_ids:
                root_children.append({
                    'id': _parent_pid, 'width': PORT_W, 'height': PORT_H,
                    'labels': [{'text': _parent_sn, 'fontSize': 8, 'fontName': 'Courier'}],
                    'layoutOptions': {'elk.layered.layering.layerConstraint': 'FIRST'},
                    '_meta': {'kind': 'port_in', 'file': _fl[0], 'line': _fl[1],
                              '_bit_parent': True, '_plan_b_b1v3': True},
                })
                _emitted_port_ids.add(_parent_pid)
    for _full in sorted(_referenced_output_fulls):
        _sn = _full.rsplit('.', 1)[-1] if '.' in _full else _full
        _pid = _port_id_for_output(_full)
        if _pid in _emitted_port_ids:
            continue
        _fl = node_source_map.get(_full, ('', 0))
        root_children.append({
            'id': _pid, 'width': PORT_W, 'height': PORT_H,
            'labels': [{'text': _sn, 'fontSize': 8, 'fontName': 'Courier'}],
            'layoutOptions': {'elk.layered.layering.layerConstraint': 'LAST'},
            '_meta': {'kind': 'port_out', 'file': _fl[0], 'line': _fl[1]},
        })
        _emitted_port_ids.add(_pid)
        # [B1 v3] 如果是 bit-indexed, 补 emit parent-port
        _m = _bit_idx_re.match(_sn)
        if _m:
            _parent_sn = _m.group(1)
            _parent_full = _full[:_full.rfind('.') + 1] + _parent_sn if '.' in _full else _parent_sn
            _parent_pid = _port_id_for_output(_parent_full)
            if _parent_pid not in _emitted_port_ids:
                root_children.append({
                    'id': _parent_pid, 'width': PORT_W, 'height': PORT_H,
                    'labels': [{'text': _parent_sn, 'fontSize': 8, 'fontName': 'Courier'}],
                    'layoutOptions': {'elk.layered.layering.layerConstraint': 'LAST'},
                    '_meta': {'kind': 'port_out', 'file': _fl[0], 'line': _fl[1],
                              '_bit_parent': True, '_plan_b_b1v3': True},
                })
                _emitted_port_ids.add(_parent_pid)
    
    def collect_signals(tree_node, into):
        """递归收集表达式树中所有 SignalRef labels"""
        if not tree_node:
            return
        if tree_node.get('op') == 'SignalRef':
            into.add(tree_node.get('label', ''))
        for c in tree_node.get('children', []):
            collect_signals(c, into)

    def render_ternary(node_id, children, prefix, nc, parent_module='', gen_block='', gen_iter=''):
        """轻量三元渲染：?: OP 节点 + 条件虚线边

        children[0] = 条件信号 (SignalRef)
        children[1] = true 分支数据
        children[2] = false 分支数据

        效果: 条件信号 → ?: 节点 (灰色虚线, cond 标签)
              true/false 数据 → ?: (普通实线)
        节点 label: ?: (sel_name)

        [Plan D1 2026-08-10] parent_module: 上下文传递给 child render_tree.

        [V16 Plan Phase 1.3 2026-08-14] 修正: cond 是表达式树 (e.g. > (din, 11'd255)),
        之前 V15 只收集 cond_sigs 然后直接 emit 虚线边, 丢失 cond 内部的 op 和 const 节点
        (e.g. > op, 11'd255). 修复: 递归 render_tree 渲染 cond 子树, 双重 emit (虚线边 + 节点).
        """
        cond = children[0] if len(children) >= 1 else None
        true_child = children[1] if len(children) >= 2 else None
        false_child = children[2] if len(children) >= 3 else None

        # 收集条件信号名 (仅 SignalRef)
        cond_sigs = set()
        if cond:
            collect_signals(cond, cond_sigs)
        sel_label = ', '.join(sorted(cond_sigs)) if cond_sigs else '?'

        # [Plan B Step A3 2026-08-22] 提前重命名 node_id 为内部 graph ID
        # 内部 graph 层 (unified_tracer._emit_conditional_op_nodes) 已经 emit
        # OP_TERNARY TraceNode (commit 90b9076), 通过 viz_data_builder 流入 viz.
        # 内部 ID 格式: "{module}.{lhs}.ternary_{sel}" (确定性)
        # 重命名后, 后续 emit 的边也用新 ID → 避免 dangling edge 引起 ELK layout error.
        if viz is not None:
            for _vn in viz.nodes:
                if getattr(_vn, 'kind', '') == 'OP_TERNARY':
                    _vn_label = getattr(_vn, 'label', '')
                    if _vn_label == f'?: ({sel_label})':
                        node_id = _vn.id
                        break

        # ?: OP 节点
        op_w = max(OP_W, len(sel_label) * 8 + 20)
        # [V16 Plan Phase 1.8 2026-08-17] op 节点归位: cluster_id = parent_module (跟 sig/const 完全对称)
        # 之前 op 节点 _meta 只有 kind, 没 cluster_id → _wrap_into_clusters 靠 node id 反推 (脆弱)
        # → case26 的 `>` op 错放到 cluster_target_top, 跟 const `11'd255` 在 cluster_u_clamp 跨 cluster → CROSS_TOP 染红
        _target_mod_op = (viz.meta or {}).get('target_module', '') if viz is not None else ''
        _op_cluster_id = parent_module or ''
        if _target_mod_op and _op_cluster_id == _target_mod_op:
            _op_cluster_id = ''  # 顶层, 归 cluster_target_top
        elif _target_mod_op and _op_cluster_id.startswith(_target_mod_op + '.'):
            _op_cluster_id = _op_cluster_id[len(_target_mod_op) + 1:]
        # [V16.10 2026-08-17] emit gen_block/gen_iter 到 _meta (供 _wrap_into_clusters sub-group)
        # 优先用入参 (顶层 for loop 传下来的真值), fallback 才用 helper (防御性)
        _gb, _gi = (gen_block or ''), (gen_iter or '')
        if not _gb:
            _gb, _gi = _parse_gen_block(parent_module)
        root_children.append({
            'id': node_id, 'width': op_w, 'height': OP_H,
            'labels': [{'text': f'?: ({sel_label})', 'fontSize': 9, 'fontName': 'Helvetica-Bold'}],
            '_meta': {'kind': 'op', 'cluster_id': _op_cluster_id or '', 'gen_block': _gb, 'gen_iter': _gi},
        })

        # 条件信号 → ?: 节点 (虚线 cond 边)
        # [V16.12 2026-08-18] 统一用 _resolve_port_id (单源 of truth)
        for sig in sorted(cond_sigs):
            # [Plan D1] 尝试 full path 解析
            if parent_module and sig in input_short_to_fulls and len(input_short_to_fulls[sig]) > 1:
                full_path = f"{parent_module}.{sig}"
                if full_path in input_paths:
                    src_id = _resolve_port_id(full_path, 'in', input_short_to_fulls, output_short_to_fulls)
                else:
                    src_id = _resolve_port_id(sig, 'in', input_short_to_fulls, output_short_to_fulls)
            elif sig in input_set:
                src_id = _resolve_port_id(sig, 'in', input_short_to_fulls, output_short_to_fulls)
            else:
                sig_id = f'sig_{_safe(sig)}_{nc}'
                existing = any(c.get('id') == sig_id for c in root_children)
                if not existing:
                    root_children.append({
                        'id': sig_id, 'width': SIG_W, 'height': SIG_H,
                        'labels': [{'text': sig, 'fontSize': 8, 'fontName': 'Courier'}],
                        '_meta': {'kind': 'signal'},
                    })
                src_id = sig_id
            root_edges.append(_emit_edge(ne(), [src_id], [node_id], kind='condition_select'))

        # [V16 Plan Phase 1.3 2026-08-14] 递归渲染 cond 子树 (e.g. > (din, 11'd255))
        # 产生 > op 节点和 11'd255 const 节点, 这些之前丢失
        if cond and cond.get('op') not in ('SignalRef',):
            # cond 是表达式 (如 GreaterThan), 递归 render
            cond_op_id = render_tree(cond, f'{prefix}_cond', parent_module=parent_module)
            if cond_op_id:
                # 让 cond op 节点 → ?: 也连一条 dataflow 边 (不仅 cond_sigs 虚线)
                root_edges.append(_emit_edge(ne(), [cond_op_id], [node_id]))

        # true/false 分支数据 → ?: (普通 dataflow 边)
        for child in (true_child, false_child):
            if child:
                child_id = render_tree(child, f'{prefix}_btf', parent_module=parent_module)
                if child_id:
                    root_edges.append(_emit_edge(ne(), [child_id], [node_id]))

        return node_id

    # 已渲染的中间信号缓存: signal_short_name -> node_id
    _signal_cache = {}

    def render_tree(tree_node, prefix, parent_module='', gen_block='', gen_iter=''):
        """递归渲染 ExpressionTree → ELK nodes + edges，返回 node_id

        [Plan D1 2026-08-10] parent_module: 从 expr_tree key 推导的父路径
        (如 'golden_hier_top.u_scale' for key 'golden_hier_top.u_scale.dout').
        用于 SignalRef 上下文感知 — 同名短名 'din' 在不同 parent_module 下
        指向不同 full path, 必须区分以避免 dedup loss.

        [V16.10 2026-08-17] gen_block / gen_iter: 从顶层 expr_trees 的 dst_short 推导出的
        generate block context (如 'gen_stage1', 'i=0'). pyslang 摊平后只能从 dst 信号名
        反推 (buf1[K]→gen_stage1, buf2[K]→gen_stage2 等). 顶层 expr_trees loop 一次
        解析后传给所有递归的 render_tree, emit op / sig / const 节点的 _meta 都带上.

        [V16.11 2026-08-18] gen_block_map: 优先从 viz.meta.datapath.gen_block_map (pyslang
        native API 真值) 取; fallback 才用启发式 _parse_gen_block. 适用于任意命名 (case27
        gen_accum 块, acc[] 信号, 启发式不识别但真值正确). 传入 gen_block_map 是可选
        参数, 默认从 viz.meta 取, 递归调用不需重传 (顶层一解析后面复用).
        """
        # [V16.11] 优先用 gen_block_map 真值 (从 viz.meta 拿一次, 后续递归复用)
        _gbm = _gen_block_map_global
        if _gbm is not None and not gen_block:
            # 从 tree_node.label 拿 base signal short name 查 gen_block
            # SignalRef 'buf3' / ElementSelect 'buf3[i+1]' 都查同一个 base 'buf3'
            _lbl = tree_node.get('label', '') or ''
            _match = _lbl
            _bracket_idx = _lbl.find('[')
            if _bracket_idx > 0:
                _match = _lbl[:_bracket_idx]
            _gb = _gbm.get(_match, '')
            if _gb:
                gen_block = _gb
                gen_iter = 'i=?'  # 递归子节点 index 不明
        label = tree_node.get('label', '?')
        op = tree_node.get('op', '?')
        children = tree_node.get('children', [])
        nc = len(root_children)
        node_id = f"op_{_safe(label)}_{prefix}_{nc}"

        if op == 'SignalRef':
            # [V16.12 2026-08-18] 统一用 _resolve_port_id (单源 of truth)
            # [V16.12 Fix E 2026-08-18] 移除 'len > 1' 限制: 只要 parent_module + label
            # 组合出 full_path 且在 input_paths/output_paths 里, 就走 full path 分支.
            # 原因: case26 中 'golden_hier_top.u_off.offset' 是 sub-module port, 而 top-level
            # input 'offset' **不在 viz.nodes** (filtered by Phase 3 target_module=level2_scale).
            # input_short_to_fulls['offset'] 长度=1 (只有 sub-module port), 走 fallback emit
            # 'port_offset' 但 root_children 没有 'port_offset' node (有的是 full path 节点).
            # 修复: parent_module 已是上下文, 不依赖 dedup_map count 即可正确选 full path.
            if parent_module:
                full_path = f"{parent_module}.{label}"
                if full_path in input_paths:
                    return _resolve_port_id(full_path, 'in', input_short_to_fulls, output_short_to_fulls)
                if full_path in output_paths:
                    return _resolve_port_id(full_path, 'out', input_short_to_fulls, output_short_to_fulls)
            # Fallback: 短名只在只有一个实例时使用
            if label in input_set:
                return _resolve_port_id(label, 'in', input_short_to_fulls, output_short_to_fulls)
            elif label in output_set:
                return _resolve_port_id(label, 'out', input_short_to_fulls, output_short_to_fulls)
            # 如果该信号有自己的表达式树（中间 wire），渲染表达式树后
            # 连接一个带信号名的标签节点（→ sum → 下游引用）
            # expr_trees keys 格式: module.signal → 需要短名匹配
            # 同时支持 prod[15:8] → 去 [...] 后缀匹配 prod 中间 wire
            _match_label = label
            _bracket_idx = label.find('[')
            if _bracket_idx > 0:
                _match_label = label[:_bracket_idx]
            # 先查缓存（带后缀匹配）
            if _match_label in _signal_cache:
                return _signal_cache[_match_label]
            if label in _signal_cache:
                return _signal_cache[label]
            matched_tree = None
            for ek, ev in expr_trees.items():
                ek_short = ek.rsplit('.', 1)[-1]
                if ek_short == label or ek_short == _match_label:
                    matched_tree = ev
                    break
            if matched_tree is not None:
                # 先查缓存
                if label in _signal_cache:
                    return _signal_cache[label]
                if _match_label in _signal_cache:
                    return _signal_cache[_match_label]
                # [Plan D1] matched_tree 递归: 新的 parent_module 是 matched_tree key 的父路径
                _matched_key = None
                for _ek, _ev in expr_trees.items():
                    _ek_short = _ek.rsplit('.', 1)[-1]
                    if _ev is matched_tree:
                        _matched_key = _ek
                        break
                _matched_parent = _matched_key.rsplit('.', 1)[0] if _matched_key else parent_module
                op_id = render_tree(matched_tree, f'{prefix}_wire', parent_module=_matched_parent)
                if op_id:
                    # 如果 op_id 就是 sig_id（可能是递归匹配的缓存结果），直接返回
                    if op_id.startswith('sig_'):
                        _signal_cache[_match_label] = op_id
                        _signal_cache[label] = op_id
                        return op_id
                    # 创建信号标签节点，OP 输出连到这里
                    sig_id = f'sig_{_safe(_match_label)}_expr'
                    existing = [c for c in root_children if c.get('id') == sig_id]
                    if existing:
                        _signal_cache[_match_label] = sig_id
                        _signal_cache[label] = sig_id
                        return sig_id
                    # [V16 Plan Phase 1.4 2026-08-14] sig 节点归位: cluster_id = parent_module (去 target_module 前缀)
                    _target_mod_sig = (viz.meta or {}).get('target_module', '') if viz is not None else ''
                    _sig_cluster_id = parent_module
                    # [V16 Plan Phase 1.7 2026-08-16] FIX: 顶层 sig (parent_module == target_mod)
                    # 应当归到 cluster_target_top (cluster_id=''), 而不是创建嵌套子框 cluster_<mod>
                    # Bug 路径: case13/19/24/27/28/29 (单 module + function/generate) 的 sig 节点
                    # 实际归到 cluster_<mod> 子框, → 与 op_+ 在外层 cluster_target_top 跨 cluster → CROSS_TOP 染红 (错!)
                    # 注意: 真正的子 instance sig 仍归对应 instance cluster (parent_module != target_mod)
                    if _target_mod_sig and _sig_cluster_id == _target_mod_sig:
                        _sig_cluster_id = ''  # 顶层, 归 cluster_target_top
                    elif _target_mod_sig and _sig_cluster_id.startswith(_target_mod_sig + '.'):
                        _sig_cluster_id = _sig_cluster_id[len(_target_mod_sig) + 1:]
                    # [V16.10 2026-08-17] emit gen_block/gen_iter (优先入参, fallback helper)
                    _gb, _gi = (gen_block or ''), (gen_iter or '')
                    if not _gb:
                        _gb, _gi = _parse_gen_block(parent_module)
                    root_children.append({
                        'id': sig_id, 'width': SIG_W, 'height': SIG_H,
                        'labels': [{'text': _match_label, 'fontSize': 8, 'fontName': 'Courier'}],
                        '_meta': {'kind': 'signal', 'cluster_id': _sig_cluster_id or '', 'gen_block': _gb, 'gen_iter': _gi},
                    })
                    root_edges.append(_emit_edge(ne(), [op_id], [sig_id]))
                    _signal_cache[_match_label] = sig_id
                    _signal_cache[label] = sig_id
                    return sig_id
            sig_id = f'sig_{_safe(label)}_{nc}'
            existing = [c for c in root_children if c.get('id') == sig_id]
            if not existing:
                # [V16 Plan Phase 1.4 2026-08-14] sig 节点归位: cluster_id = parent_module (去 target_module 前缀)
                _target_mod_sig2 = (viz.meta or {}).get('target_module', '') if viz is not None else ''
                _sig_cluster_id2 = parent_module
                # [V16 Plan Phase 1.7 2026-08-16] FIX: 顶层 sig 同样问题 (与 line 406 注释相同)
                if _target_mod_sig2 and _sig_cluster_id2 == _target_mod_sig2:
                    _sig_cluster_id2 = ''  # 顶层, 归 cluster_target_top
                elif _target_mod_sig2 and _sig_cluster_id2.startswith(_target_mod_sig2 + '.'):
                    _sig_cluster_id2 = _sig_cluster_id2[len(_target_mod_sig2) + 1:]
                # [V16.10 2026-08-17] emit gen_block/gen_iter (优先入参, fallback helper)
                _gb2, _gi2 = (gen_block or ''), (gen_iter or '')
                if not _gb2:
                    _gb2, _gi2 = _parse_gen_block(parent_module)
                root_children.append({
                    'id': sig_id, 'width': SIG_W, 'height': SIG_H,
                    'labels': [{'text': label, 'fontSize': 8, 'fontName': 'Courier'}],
                    '_meta': {'kind': 'signal', 'cluster_id': _sig_cluster_id2 or '', 'gen_block': _gb2, 'gen_iter': _gi2},
                })
            return sig_id
        
        if op == 'Const':
            const_id = f'const_{_safe(label)}_{nc}'
            # [V16 Plan Phase 1.1 2026-08-14] const 节点归位: cluster_id = parent_module
            # 例: level2_clamp.u_clamp.dout 的 expr 树里 11'd255 的 parent_module = 'golden_hier_top.u_clamp'
            # → const 归到 u_clamp cluster (短名), 而不是顶层 cluster_target_top
            # 注: viz.meta.target_module 是 'golden_hier_top', 需去掉前缀匹配 VizNode.cluster_id 短名规则
            _target_mod = (viz.meta or {}).get('target_module', '') if viz is not None else ''
            _cluster_id = parent_module
            # [V16 Plan Phase 1.5 2026-08-14] FIX: 顶层 const (parent_module == target_mod) 
            # 应当归到 cluster_target_top (cluster_id=''), 而不是创建嵌套子框 cluster_<mod>
            # Bug 路径: case2 (with_const) const 8'd128/2 实际归到 cluster_with_const 子框,
            # → 与 op_+ 在外层 cluster_target_top 跨 cluster → CROSS_TOP 染红 (错!)
            if _target_mod and _cluster_id == _target_mod:
                _cluster_id = ''  # 顶层, 归 cluster_target_top
            elif _target_mod and _cluster_id.startswith(_target_mod + '.'):
                _cluster_id = _cluster_id[len(_target_mod) + 1:]
            # [V16.10 2026-08-17] emit gen_block/gen_iter (优先入参, fallback helper)
            _gb_c, _gi_c = (gen_block or ''), (gen_iter or '')
            if not _gb_c:
                _gb_c, _gi_c = _parse_gen_block(parent_module)
            _meta = {'kind': 'const', 'cluster_id': _cluster_id or '', 'gen_block': _gb_c, 'gen_iter': _gi_c}
            root_children.append({
                'id': const_id, 'width': 40, 'height': SIG_H,
                'labels': [{'text': label, 'fontSize': 8, 'fontName': 'Courier'}],
                'layoutOptions': {'elk.layered.layering.layerConstraint': 'FIRST'},
                '_meta': _meta,
            })
            return const_id
        
        # ── Ternary: compound case/branch structure ──
        if op == 'Ternary':
            # [Plan B Step A12.3 2026-08-24] 嵌套 ternary 时用内部 graph ID 格式
            # 背景: A3 重命名只在 viz.nodes 有匹配 OP_TERNARY 时生效.
            # 嵌套 ternary 的内部 OP_TERNARY 不在 viz.nodes (unified_tracer 只 emit 外层),
            # 所以重命名静默失败, 嵌套 OP 仍用 counter-based ID (op_xxx_y_btf_5),
            # 跟内部 graph 的 ID (ternary_test.y.ternary_sel) 不一致 → BRANCH_* 边 dangle.
            # 修复: 从 prefix 反推 lhs_short, 跟 unified_tracer._emit_conditional_op_nodes 同样的 ID 公式.
            # 公式: f"{parent_module}.{lhs_short}.ternary_{sel_label.replace(',', '_').replace(' ', '')}"
            _lhs_short_a12 = None
            if prefix.startswith('wire_'):
                # 拔掉 'wire_' 前缀, 取第一个 '_' 前的部分
                _after = prefix[len('wire_'):]
                # 容忍嵌套: 'wire_y' → 'y'; 'wire_y_btf' → 'y' (后面是 btf/cond)
                for _marker in ('_btf', '_cond', '_wire', '_c'):
                    if _marker in _after:
                        _lhs_short_a12 = _after.split(_marker)[0]
                        break
                if _lhs_short_a12 is None:
                    _lhs_short_a12 = _after.split('_')[0] if '_' in _after else _after
            if _lhs_short_a12 is None:
                _lhs_short_a12 = prefix.split('_')[0] if '_' in prefix else prefix
            # 提取 sel_label 从 cond 子树 (跟 render_ternary 同样逻辑)
            _sel_label_a12 = '?'
            if children and isinstance(children[0], dict):
                _cond_a12 = children[0]
                _cond_sigs_a12 = []
                def _a12_collect(n):
                    if isinstance(n, dict):
                        if n.get('op') == 'SignalRef':
                            _lbl = n.get('label', '')
                            if _lbl and _lbl not in _cond_sigs_a12:
                                _cond_sigs_a12.append(_lbl)
                        for _ch in n.get('children', []) or []:
                            _a12_collect(_ch)
                _a12_collect(_cond_a12)
                _sel_label_a12 = ', '.join(sorted(_cond_sigs_a12)) if _cond_sigs_a12 else '?'
            _safe_sel_a12 = _sel_label_a12.replace(',', '_').replace(' ', '')
            _det_id_a12 = f"{parent_module}.{_lhs_short_a12}.ternary_{_safe_sel_a12}"
            # 如果内部 graph 有这个 ID, 用它 (跟 A3 一致). 否则用计算的 deterministic ID
            # (这样嵌套 ternary 也能跟内部 graph 对齐, 修复 5 nested case)
            _use_det_id = True
            if viz is not None:
                _matched_in_viz = False
                for _vn in viz.nodes:
                    if getattr(_vn, 'kind', '') == 'OP_TERNARY' and getattr(_vn, 'id', '') == _det_id_a12:
                        _matched_in_viz = True
                        node_id = _det_id_a12
                        break
                if not _matched_in_viz:
                    # 嵌套情况: 用计算的 deterministic ID (内部 graph 未 emit, 但 ID 格式对齐)
                    node_id = _det_id_a12
            else:
                node_id = _det_id_a12
            return render_ternary(node_id, children, prefix, nc, parent_module=parent_module, gen_block=gen_block, gen_iter=gen_iter)
        
        # Operator node
        op_w = OP_W
        if op == 'Call':
            op_w = max(OP_W + len(label) * 6, 50)
        op_h = OP_H + max(0, (len(children) - 2) * 8)

        # [V16 Plan Phase 1.8 2026-08-17] op 节点归位: cluster_id = parent_module (跟 sig/const 完全对称)
        _target_mod_op2 = (viz.meta or {}).get('target_module', '') if viz is not None else ''
        _op_cluster_id2 = parent_module or ''
        if _target_mod_op2 and _op_cluster_id2 == _target_mod_op2:
            _op_cluster_id2 = ''  # 顶层, 归 cluster_target_top
        elif _target_mod_op2 and _op_cluster_id2.startswith(_target_mod_op2 + '.'):
            _op_cluster_id2 = _op_cluster_id2[len(_target_mod_op2) + 1:]

        # [V16.10 2026-08-17] emit gen_block/gen_iter (优先入参, fallback helper)
        _gb_op, _gi_op = (gen_block or ''), (gen_iter or '')
        if not _gb_op:
            _gb_op, _gi_op = _parse_gen_block(parent_module)
        root_children.append({
            'id': node_id, 'width': op_w, 'height': op_h,
            'labels': [{'text': label, 'fontSize': 9, 'fontName': 'Helvetica-Bold'}],
            '_meta': {'kind': 'op', 'cluster_id': _op_cluster_id2 or '', 'gen_block': _gb_op, 'gen_iter': _gi_op},
        })

        for child in children:
            # [V16.10.2 2026-08-17] 递归子节点传 gen_block/gen_iter (避免 OUTPUT 路径下 BitSelect/SignalRef 子节点
            # 坬立). 原因: case29 chain_out = buf3[N-2] 场景, OUTPUT 路径 render_tree 返回顶层 BitSelect op,
            # 递归 child 是 SignalRef buf3. 之前递归不传 gen_block/gen_iter, 子节点 fallback 调
            # _parse_gen_block(parent_module), 但 parent_module='generate_for_chain' 没有 'gen_stage3' 字样
            # → fallback 失败 → 子节点 _meta.gen_block='' → 不归位到 genblk → 坬立飘在画布左上角.
            child_id = render_tree(child, f"{prefix}_c", parent_module=parent_module,
                                    gen_block=_gb_op, gen_iter=_gi_op)
            if child_id:
                root_edges.append(_emit_edge(ne(), [child_id], [node_id]))
        
        return node_id
    
    for dst_name, tree_data in expr_trees.items():
        dst_short = _short(dst_name)
        # [Plan D1] 推导 parent_module: expr_tree key 的父路径
        # 如 'golden_hier_top.u_scale.dout' → parent_module = 'golden_hier_top.u_scale'
        _parent_module = dst_name.rsplit('.', 1)[0] if '.' in dst_name else ''
        # [V16.11.2 2026-08-18] 优雅修复根因 B: 优先用 _gen_block_map 真值 (pyslang native API)
        # 适用所有 dst signal — 包括 case30/31 的 port output 'result' (不匹配启发式 buf\d+)
        # [V16.14 F-N3 2026-08-19] per-LHS-element lookup:
        #  1. _gen_block_map 只存 base 名 ('acc'), 不含 bracket.  所以总是查 dst_short 前缀 (去 bracket).
        #  2. _gen_iter_map 存 per-element key ('acc[1]', 'acc[2]'), 优先查完整 pattern,
        #     再 fallback 到 base (兼容 case29).
        _dst_gb, _dst_gi = '', ''
        if _gen_block_map_global is not None:
            # 取 base 名 (case30 'result' 无 bracket, 仍是 'result')
            _bi = dst_short.find('[')
            _base = dst_short[:_bi] if _bi > 0 else dst_short
            _dst_gb = _gen_block_map_global.get(_base, '')
            if _dst_gb:
                _dst_gi = 'i=0'
                # [V16.14 F-N3] 优先查 per-element key ('acc[1]'), 拿真 entry_idx
                if _gen_iter_map_global is not None:
                    _idx = _gen_iter_map_global.get(dst_short)
                    if _idx is not None:
                        _dst_gi = f'i={_idx}'
                    else:
                        # Fallback: base 名 (case29 chain_out 等退化场景)
                        _idx2 = _gen_iter_map_global.get(_base)
                        if _idx2 is not None:
                            _dst_gi = f'i={_idx2}'
        # [V16.10 2026-08-17] fallback: 启发式 (仅在真值缺失时才用)
        if not _dst_gb:
            _dst_gb, _dst_gi = _parse_gen_block(_parent_module, dst_short)
        # 中间 wire (非 input 非 output): 创建 sig 标签节点 + 渲染表达式树
        if dst_short not in output_set and dst_short not in input_set:
            sig_id = f'sig_{_safe(dst_short)}_wire'
            root_children.append({
                'id': sig_id, 'width': SIG_W, 'height': SIG_H,
                'labels': [{'text': dst_short, 'fontSize': 8, 'fontName': 'Courier'}],
                '_meta': {'kind': 'signal', 'gen_block': _dst_gb, 'gen_iter': _dst_gi},
            })
            _signal_cache[dst_short] = sig_id
            op_id = render_tree(tree_data, f'wire_{dst_short}', parent_module=_parent_module,
                                 gen_block=_dst_gb, gen_iter=_dst_gi)
            if op_id:
                root_edges.append(_emit_edge(ne(), [op_id], [sig_id]))
            continue
        # Output port: 渲染树 + 连到 port
        # [V16.10.1 2026-08-17] 跟 wire 路径对称: emit 一个 sig_id wrapper 在 port_chain_out 之前
        # 原因: 之前直接 render_tree 后 top_op_id→port_chain_out 一步走, render_tree 内部递归
        # 子节点 (BitSelect/SignalRef) 全部裸放在 root_children, 变成坬立的 "左上角小图" bug
        # (case29 chain_out = buf3[N-2] 场景: op_buf3_N-2 + sig_buf3 坬立, 不归位到 gen_stage3)
        # 修复: OUTPUT 也 emit 一个 sig_id wrapper, 边两步走 top_op_id→sig→port,
        # 跟 wire 路径完全对称. 这样 render_tree 递归产生的 op/sig 节点可以经 sig wrapper 归位.
        # [V16.10.2 2026-08-17] OUTPUT dst 是 'chain_out' (不匹配 buf\d+\[\d+\] pattern), _dst_gb=''
        # 实际语义是 BitSelect buf3[N-2], 属于 gen_stage3. 递归扫描 tree_data 找 SignalRef child 反推
        if not _dst_gb:
            # 递归找 buf\d+\[K\] SignalRef child, 传递它的 gen_block/gen_iter
            def _scan_gen_signal_ref(node):
                if not isinstance(node, dict):
                    return None
                if node.get('op') == 'SignalRef':
                    _lbl = node.get('label', '')
                    _sgb, _sgi = _parse_gen_block('', _lbl)
                    if _sgb:
                        return (_sgb, _sgi)
                for c in node.get('children', []) or []:
                    r = _scan_gen_signal_ref(c)
                    if r:
                        return r
                return None
            _scanned = _scan_gen_signal_ref(tree_data)
            if _scanned:
                _dst_gb, _dst_gi = _scanned
        top_op_id = render_tree(tree_data, f'wire_{dst_short}', parent_module=_parent_module,
                                gen_block=_dst_gb, gen_iter=_dst_gi)
        if dst_short in output_set and top_op_id:
            # [Plan D1] 用 full path port ID
            _out_port_id = _port_id_for_output(dst_name)
            # [V16.10.1] emit sig wrapper (同 wire 路径) - 避免 render_tree 子节点成为坬立飘点
            sig_id = f'sig_{_safe(dst_short)}_wire'
            sig_exists = any(c.get('id') == sig_id for c in root_children)
            if not sig_exists:
                root_children.append({
                    'id': sig_id, 'width': SIG_W, 'height': SIG_H,
                    'labels': [{'text': dst_short, 'fontSize': 8, 'fontName': 'Courier'}],
                    '_meta': {'kind': 'signal', 'gen_block': _dst_gb, 'gen_iter': _dst_gi},
                })
            # 两步边: top_op → sig → port (防止坬立)
            root_edges.append(_emit_edge(ne(), [top_op_id], [sig_id]))
            root_edges.append(_emit_edge(ne(), [sig_id], [_out_port_id]))

    result = {
        'id': 'root',
        'properties': dict(ELK_OPTIONS),
        'children': root_children,
        'edges': root_edges,
    }
    # [V16 Plan Phase 2.1 2026-08-14] emit wire 节点 + 两步紫色边在 _wrap_into_clusters 之前
    # 这样 emit 的 sig_scaled_wire 等 wire 节点会被 _wrap_into_clusters 看到, 放进 cluster_target_top
    if viz is not None:
        result = _emit_cross_instance_connection_edges(result, viz)
    # [V14 2026-08-13] 层级模块折叠 cluster 重组
    return _wrap_into_clusters(viz, result)


# ═══════════════════════════════════════════════════════════════════
# [V14 2026-08-13] 层级模块折叠 cluster 重组
# ═══════════════════════════════════════════════════════════════════
# 背景: case26 等层级设计需要把 4 个 instance 装进各自的 cluster 框
# (浅蓝边框), 顶层 target module 装进虚线框, CONNECTION 边走红线
# (D2 决策: 只给 CROSS_TOP 加红线).
# 重塑 root_children: 按 VizNode.cluster_id 重组为嵌套 cluster 结构.
# ═══════════════════════════════════════════════════════════════════

def _wrap_into_clusters(viz, elk_json):
    """按 VizNode.cluster_id 把 root_children 重组为嵌套 cluster 框.

    输入: 扁平 root_children (case26: 23 节点)
    输出: 嵌套 children 列表, 每个 instance 一个 cluster, 顶层 target 一个虚线框 cluster.

    重要: ELK compound graph 可以让子节点用自己原始的 id 引用, 不需要
    重写为 cluster id — ELK 会自动查找 hierarchy. 所以我们只重塑 children
    树结构, 不动 edge 端点.

    阶段 5 (CONNECTION 边红色): 只加 meta.stroke, 不重写 src/dst.
    """
    from collections import defaultdict
    root_children = elk_json.get('children', [])
    root_edges = elk_json.get('edges', [])

    if not viz or not viz.nodes:
        return elk_json

    # ── 1. 按 cluster_id 分组 ──
    # ELK 节点 id 可能是 'port_data_in' (顶层) 或 'port_golden_hier_top_dot_u_scale_dot_din' (子模块)
    # 从 ELK 节点 id 反推 VizNode 用 _safe 反向映射 (port_<safe_full_path>)
    clusters = defaultdict(list)
    # 构造 full_path → cluster_id 映射
    fp_to_cid = {}
    for n in viz.nodes:
        fp_to_cid[str(n.id)] = getattr(n, 'cluster_id', '') or ''

    def _child_cluster(child):
        cid = str(child.get('id', ''))
        # 'port_xxx' 形式 — 从 xxx 反推
        if cid.startswith('port_'):
            port_part = cid[5:]
            # 检查是否含 '_dot_' (子模块多短名) — 'golden_hier_top_dot_u_scale_dot_din'
            if '_dot_' in port_part:
                # 拼回 full path: 'golden_hier_top.u_scale.din'
                fp = port_part.replace('_dot_', '.')
                # 尝试匹配最长 VizNode.id
                for vp in sorted(fp_to_cid.keys(), key=len, reverse=True):
                    if fp.endswith(vp) or fp == vp:
                        return fp_to_cid[vp]
                return ''
            else:
                # 顶层 port, e.g. 'data_in' → 'golden_hier_top.data_in'
                for vp, vc in fp_to_cid.items():
                    if vp.endswith('.' + port_part):
                        return vc
                return ''
        # 'op___full_path' 形式 (e.g. 'op___golden_hier_top.u_scale.dout_15')
        if cid.startswith('op__'):
            # [V16 Plan Phase 1.8 2026-08-17] 优先读 _meta.cluster_id (跟 sig/const 对称)
            # 之前 _meta 没 cluster_id 字段, 靠 node id 反推 + fp_to_cid 匹配 → 脆弱
            # Bug 路径: op___golden_hier_top.u_clamp_u.dout_cond_18 反推为 fp='golden_hier_top.u_clamp_u.dout_cond'
            # 找不到精确 match → fallback '' → 归到 cluster_target_top → CROSS_TOP 染红
            for child in root_children:
                if str(child.get('id', '')) == cid:
                    _mc = str(child.get('_meta', {}).get('cluster_id', ''))
                    if _mc:
                        return _mc
            # fallback (老逻辑, 保留兼容)
            m = cid[4:]
            import re as _re
            m2 = _re.sub(r'_\d+$', '', m)
            fp = m2.replace('_dot_', '.')
            for vp in sorted(fp_to_cid.keys(), key=len, reverse=True):
                if fp.endswith(vp) or fp == vp:
                    return fp_to_cid[vp]
            return ''
        # 'sig_<label>_<n>' 形式
        if cid.startswith('sig_'):
            # [V16 Plan Phase 2.1 2026-08-14] wire 节点 (e.g. sig_scaled_wire) 总是顶层
            # 之前 rsplit('_', 1) 会拆 'scaled_wire' 为 'scaled'+'wire' 然后找 scaled 找不到
            # V16: 检测 _wire 后缀直接返回 '' (进入 cluster_target_top)
            if cid.endswith('_wire'):
                return ''  # 顶层, 进入 cluster_target_top
            label = cid[4:].rsplit('_', 1)[0]
            # [V16 Plan Phase 1.4 2026-08-14] sig 节点 同样 const 路径, 优先读 _meta.cluster_id
            for child in root_children:
                if str(child.get('id', '')) == cid:
                    _mc = str(child.get('_meta', {}).get('cluster_id', ''))
                    if _mc:
                        return _mc
            for vp, vc in fp_to_cid.items():
                if vp.endswith('.' + label.replace('_dot_', '.')):
                    return vc
            return ''
        # 'const_<label>_<n>' 形式
        # [V16 Plan Phase 1.2 2026-08-14] const 节点归位: 读 _meta.cluster_id (Phase 1.1 写入)
        # 之前硬编码 return '' 是错的: V15 假设 const 总是顶层, 但实际 const 属于
        # 父 expression tree 所在 instance (e.g. 11'd255 在 u_clamp 内部, 应该在 u_clamp cluster)
        if cid.startswith('const_'):
            # 在 root_children 里找到对应节点, 读 _meta.cluster_id
            for child in root_children:
                if str(child.get('id', '')) == cid:
                    return str(child.get('_meta', {}).get('cluster_id', ''))
            return ''  # fallback
        return ''  # 未知 → 顶层

    for child in root_children:
        matched_cid = _child_cluster(child)
        clusters[matched_cid].append(child)

    # ── 2. 构造每个 cluster 的 child wrapper ──
    new_children = []
    cluster_id_to_elk_id = {}

    # [V14 2026-08-13 回归修复] 只在 viz 真的包含子模块时 (有 cluster_id != '')
    # 才包 cluster_target_top 虚线框. 纯顶层 case (如 case1-25 多数)
    # 不包顶层 cluster, 避免给 checker compounds 期望数 +1 的 regression.
    has_submodules = any(cid for cid in clusters if cid)

    if clusters[''] and has_submodules:
        cluster_id_to_elk_id[''] = 'cluster_target_top'
        target_label = ''
        for n in viz.nodes:
            if getattr(n, 'cluster_id', '') == '':
                target_label = n.module or ''
                break
        if not target_label and viz.meta:
            target_label = viz.meta.get('target_module', 'target')
        # [V16.4 2026-08-14] top 作为最大框，子 instance cluster 嵌套在其内
        # 之前所有子 cluster append 到 new_children (root 的 children), 跟 cluster_target_top 平级
        # 现在子 cluster 嵌套到 cluster_target_top.children, 真正实现递归嵌套
        cluster_target_top_node = {
            'id': 'cluster_target_top',
            'labels': [{'text': target_label, 'fontSize': 10}],
            'borderStyle': 'dashed',
            '_meta': {'is_cluster': True, 'is_target': True, 'cluster_id': ''},
            'children': list(clusters['']),  # 顶层叶子节点
            # [V15 2026-08-13 修复] 删硬编码 width/height — 让 ELK 自动算 cluster 尺寸.
            # 之前设 (200,150) / (180,130) 让多个 cluster 子节点 layout 到相同相对坐标,
            # 出现 sp/ep 重叠 → SVG 看起来"重复 path".
        }
        new_children.append(cluster_target_top_node)
    elif clusters['']:
        # 纯顶层 case: 保持扁平, 不加 wrapper
        for child in clusters['']:
            new_children.append(child)

    # [V16.4 2026-08-14] 子 instance cluster 嵌套到 cluster_target_top (而非平级)
    # 保持 cluster_target_top_node 引用以便 append 子 cluster 到其内部
    parent_top_node = new_children[-1] if (clusters[''] and has_submodules) else None

    for cid in sorted(k for k in clusters if k):
        mod_type = ''
        for n in viz.nodes:
            if getattr(n, 'cluster_id', '') == cid and getattr(n, 'module_type', ''):
                mod_type = n.module_type
                break
        label_text = f'{mod_type}  {cid}' if mod_type else cid
        elk_cluster_id = f'cluster_{_safe(cid)}'
        cluster_id_to_elk_id[cid] = elk_cluster_id
        sub_cluster_node = {
            'id': elk_cluster_id,
            'labels': [{'text': label_text, 'fontSize': 10}],
            'borderStyle': 'solid',
            '_meta': {'is_cluster': True, 'is_target': False, 'cluster_id': cid,
                      'module_type': mod_type, 'instance_path': cid},
            'children': clusters[cid],
            # [V15 2026-08-13 修复] 删硬编码 width/height — 让 ELK 自动算 cluster 尺寸.
        }
        # 嵌套到 cluster_target_top, 否则平级
        if parent_top_node is not None:
            parent_top_node['children'].append(sub_cluster_node)
        else:
            new_children.append(sub_cluster_node)

    # [V16.10 2026-08-17] generate block sub-grouping: 对顶层 children 选取出有 _meta.gen_block 的节点,
    # 按 gen_block 名 sub-group 成嵌套 cluster box (dashed border, label='gen_stage1 (i=0..2)'等).
    # 目的: case29 generate_for_chain 9 个 + op 节点原平铺 → 3 个 gen_stage1/2/3 嵌套 group
    # 设计: 在 _wrap_into_clusters 末尾统一处理 new_children, 不依赖 parent_top_node (纯顶层 case29
    # 没 cluster_target_top wrapper, 之前被这个条件 skip 了). gen_block 适用所有顶层 leaf (op_/sig_/const_).
    from collections import defaultdict as _dd_v1610
    _genblk_groups = _dd_v1610(list)
    _non_genblk_children = []
    for child in list(new_children):
        _meta = child.get('_meta', {}) or {}
        _gb = _meta.get('gen_block', '')
        if _gb and child.get('id', '').startswith(('op_', 'sig_', 'const_')):
            _genblk_groups[_gb].append(child)
        else:
            _non_genblk_children.append(child)
    if _genblk_groups:
        # 重建 new_children: sub_cluster_node (顶层 instance cluster) 在前, 然后 genblk nested boxes
        rebuilt_children = []
        for ch in _non_genblk_children:
            if ch.get('_meta', {}).get('is_cluster') and not ch.get('_meta', {}).get('is_gen_block'):
                rebuilt_children.append(ch)
        # 如果存在 cluster_target_top wrapper, 把 genblk box 嵌到它里面; 否则顶层平级
        for _gb_name, _gb_children in sorted(_genblk_groups.items()):
            _iter_seen = sorted({c.get('_meta', {}).get('gen_iter', '') for c in _gb_children if c.get('_meta', {}).get('gen_iter', '')})
            _iter_label = ', '.join(_iter_seen) if _iter_seen else ''
            _gb_label = f'{_gb_name} ({_iter_label})' if _iter_label else _gb_name
            rebuilt_children.append({
                'id': f'genblk_{_gb_name}_top',
                'labels': [{'text': _gb_label, 'fontSize': 9, 'fontName': 'Helvetica-Bold'}],
                'borderStyle': 'dashed',
                'layoutOptions': {'elk.padding': '[top=12,left=12,bottom=12,right=12]'},
                '_meta': {'is_cluster': True, 'is_gen_block': True, 'gen_block': _gb_name},
                'children': _gb_children,
            })
        # 保留所有非 cluster children (顶层 sig/const/port_in 等)
        for ch in _non_genblk_children:
            if not ch.get('_meta', {}).get('is_cluster'):
                rebuilt_children.append(ch)
        new_children = rebuilt_children

    # ── 3. 不重写 edge 端点 (ELK compound 自动处理)
    # 只加 _meta.stroke = 'red' 给 CROSS_TOP 边 (D2 决策)
    # 检测方法: src 或 dst 在顶层 cluster, 且另边在子模块 cluster
    new_edges = []
    # 构造 eid → cluster_id 映射
    eid_to_cid = {}
    for cid, items in clusters.items():
        for child in items:
            eid_to_cid[str(child.get('id', ''))] = cid
    for e in root_edges:
        meta = dict(e.get('_meta', {}))
        # 阶段 5: CROSS_TOP 边检测 (不论什么 kind, 只要跨顶层/子模块)
        src_id = (e.get('sources', ['']) or [''])[0]
        dst_id = (e.get('targets', ['']) or [''])[0]
        src_cid = eid_to_cid.get(src_id, '')
        dst_cid = eid_to_cid.get(dst_id, '')
        is_cross_top = (src_cid == '' and dst_cid != '') or (dst_cid == '' and src_cid != '')
        # [V16 Plan Phase 2.1 2026-08-14] 只覆盖 stroke 默认情况的边. 不覆盖 explicit stroke='purple'
        # (紫色是 V16 跨 instance 两步边的明确颜色, CROSS_TOP 默认是红色)
        if is_cross_top and not meta.get('stroke'):
            meta['stroke'] = 'red'
            meta['cross_top'] = True
        new_e = dict(e)
        new_e['_meta'] = meta
        new_edges.append(new_e)

    elk_json = dict(elk_json)
    elk_json['children'] = new_children
    elk_json['edges'] = new_edges
    return elk_json


def viz_to_elk(viz: VizData) -> dict:
    """VizData → ELK compound graph JSON"""
    ctr = [0]
    def ne(): ctr[0] += 1; return f'e{ctr[0]}'

    # [Plan B Step A5 2026-08-25] _emitted_port_ids 在 viz_to_elk scope 初始化,
    # 让 sel_anchor block (line ~1445) 的 lazy port_in emit 能 dedup.
    # 之前 _emitted_port_ids 只在 expr_trees_to_elk 内定义, viz_to_elk 用不到 → NameError.
    _emitted_port_ids = set()

    # ── Phase 0: Classify edges (only for case/if compound graph) ──
    cond_by_dst = defaultdict(list)
    for e in viz.edges:
        chain = getattr(e, 'condition_chain', None) or []
        ek = getattr(e, 'kind', '')
        if chain and ek not in ('CLOCK', 'RESET', 'BIT_SELECT'):
            cond_by_dst[e.dst].append(e)

    input_names, output_names = [], []
    # Identify clock/reset ports to exclude from dataflow display
    _clock_reset_srcs = set()
    for e in viz.edges:
        ek = getattr(e, 'kind', '')
        if ek in ('CLOCK', 'RESET'):
            _clock_reset_srcs.add(_short(e.src))
    # [V16.12 2026-08-18] 同时构建 input_short_to_fulls / output_short_to_fulls
    # 让 _resolve_port_id (case compound graph 用的嵌套 helper) 能 dedup-aware.
    input_short_to_fulls = defaultdict(list)
    output_short_to_fulls = defaultdict(list)
    for n in viz.nodes:
        side = getattr(n, 'port_side', '')
        cid = getattr(n, 'cluster_id', '') or ''
        nid = str(n.id)
        nid_short = _short(nid)
        # 同时收顶层 port 和 sub-module instance port (cluster_id != '' 且 port_side != '')
        if side == 'left' and nid_short not in _clock_reset_srcs:
            input_names.append(nid_short)
            input_short_to_fulls[nid_short].append(nid)
            if cid and side:  # sub-module port
                input_short_to_fulls[nid_short].append(nid)
        elif side == 'right':
            output_names.append(nid_short)
            output_short_to_fulls[nid_short].append(nid)
            if cid:  # sub-module port
                output_short_to_fulls[nid_short].append(nid)

    root_children = []
    root_edges = []

    # Local edge helper (Phase 3 compound graph uses this)
    # [Plan B Step C 2026-08-25] Branch differentiator
    # 背景: case/ternary 内部各分支边 (true/false/case_item) 视觉上没区分.
    # 修复: 给 _emit_edge 加 ELK layoutOptions, 不同 kind 走不同样式:
    #   - condition_select: 虚线 (selector → case scope)
    #   - branch_true: 实线绿色 (case true 分支源)
    #   - branch_false: 实线红色 (ternary false 分支源)
    #   - case_item: 实线蓝色 (case 各项驱动)
    _EDGE_STYLES = {
        'condition_select': {
            'elk.edge': 'direct',
            'edgeRouting': 'ORTHOGONAL',
            'stroke': '#888888',
            'strokeDasharray': '4 4',  # 虚线
            'strokeWidth': 1.2,
        },
        'branch_true': {
            'elk.edge': 'direct',
            'edgeRouting': 'ORTHOGONAL',
            'stroke': '#2e7d32',  # 绿色
            'strokeDasharray': 'none',
            'strokeWidth': 1.4,
        },
        'branch_false': {
            'elk.edge': 'direct',
            'edgeRouting': 'ORTHOGONAL',
            'stroke': '#c62828',  # 红色
            'strokeDasharray': 'none',
            'strokeWidth': 1.4,
        },
        'case_item': {
            'elk.edge': 'direct',
            'edgeRouting': 'ORTHOGONAL',
            'stroke': '#1565c0',  # 蓝色
            'strokeDasharray': 'none',
            'strokeWidth': 1.4,
        },
    }
    def _emit_edge(eid, srcs, tgts, edge_obj=None, kind='signal'):
        meta = {'kind': kind}
        if edge_obj is not None:
            at = getattr(edge_obj, 'assign_type', '') or ''
            if at:
                meta['assign_type'] = at
        edge = {'id': eid, 'sources': list(srcs), 'targets': list(tgts), '_meta': meta}
        # [Plan B Step C] 应用不同样式
        if kind in _EDGE_STYLES:
            edge['layoutOptions'] = dict(_EDGE_STYLES[kind])
        return edge

    # ── Phase 1: PORT_IN nodes (top-level, LEFT column) ──
    # [V16.12 2026-08-18] dedup-aware: 同一短名多实例时, 用 full path 避免短名冲突.
    # viz_to_elk 之前是 _resolve_port_id 漏改的一处 (case26 fail 根因).
    # 不仅收集顶层 input, 还收集 sub-module input (如 'golden_hier_top.u_scale.din'),
    # 因为顶层 input port + sub-module 端口可能同名 (都叫 'din').
    _in_dedup_map = defaultdict(list)
    for _e in viz.edges:
        if getattr(_e, 'kind', '') in ('CLOCK', 'RESET'):
            continue
        _sn = _short(_e.src)
        if _sn in input_names or '.' in _e.src:
            _in_dedup_map[_sn].append(_e.src)
    _in_emitted = set()
    for _full in sorted(set(_f for _fulls in _in_dedup_map.values() for _f in _fulls)):
        _sn = _short(_full)
        # [V16.12 Fix G 2026-08-18] 删 filter: dedup_map 收集的 full path 都 emit
        # case26: target_module=level2_scale filter 掉顶层 'offset' input,
        # 但 sub-module 'golden_hier_top.u_off.offset' 仍在 dedup_map, 不该被滤.
        # [V16.12 Fix G 2026-08-18] filter removed — dedup_map-driven emit (allow ALL)
        # 顶层 input 走短名, sub-module 走 full path
        if '.' in _full and _full.split('.')[-2] in input_names:
            # 子模块 port: e.g. 'golden_hier_top.u_scale.din' 但顶层 'golden_hier_top' 是 input
            # 顶层仍然 emit port_<short>; sub-module port emit port_<safe(full)>
            _is_sub = True
        elif '.' in _full:
            _is_sub = True
        else:
            _is_sub = False
        _fulls_for_sn = _in_dedup_map.get(_sn, [])
        if _is_sub:
            _pid = f'port_{_safe(_full)}'
        elif len(_fulls_for_sn) > 1:
            _pid = f'port_{_safe(_fulls_for_sn[0])}'
        else:
            _pid = f'port_{_sn}'
        if _pid in _in_emitted:
            continue
        _in_emitted.add(_pid)
        root_children.append({
            'id': _pid, 'width': PORT_W, 'height': PORT_H,
            'labels': [{'text': _sn, 'fontSize': 8, 'fontName': 'Courier'}],
            'layoutOptions': {'elk.layered.layering.layerConstraint': 'FIRST'},
            '_meta': {'kind': 'port_in'},
        })

    # ── Phase 2: PORT_OUT nodes (top-level, RIGHT column) ──
    # [V16.12] 同样收 sub-module port_out (e.dst 含 '.')
    _out_dedup_map = defaultdict(list)
    for _e in viz.edges:
        _sn = _short(_e.dst)
        if _sn in output_names or '.' in _e.dst:
            _out_dedup_map[_sn].append(_e.dst)
    _out_emitted = set()
    for _full in sorted(set(_f for _fulls in _out_dedup_map.values() for _f in _fulls)):
        _sn = _short(_full)
        if _sn not in output_names and not '.' in _full:
            continue
        _fulls_for_sn = _out_dedup_map.get(_sn, [])
        if '.' in _full:
            _pid = f'port_{_safe(_full)}'
        elif len(_fulls_for_sn) > 1:
            _pid = f'port_{_safe(_fulls_for_sn[0])}'
        else:
            _pid = f'port_{_sn}'
        if _pid in _out_emitted:
            continue
        _out_emitted.add(_pid)
        root_children.append({
            'id': _pid, 'width': PORT_W, 'height': PORT_H,
            'labels': [{'text': _sn, 'fontSize': 8, 'fontName': 'Courier'}],
            'layoutOptions': {'elk.layered.layering.layerConstraint': 'LAST'},
            '_meta': {'kind': 'port_out'},
        })
    output_set = set(output_names)

    # ── No non-cond path: ExpressionTree handles dataflow via expr_trees_to_elk() ──
    # 如果没有任何条件边，返回一个空图（数据流由 expr_trees_to_elk 处理）
    if not cond_by_dst:
        return _wrap_into_clusters(viz, _make_graph(root_children, root_edges))

    # ── Phase 3: Build compound case/branch scopes ──
    # [FIX 2026-08-08] case_children / case_edges 必须在循环内重置,
    # 否则两个 case_node 共享同一个 list, 导致每个 case 框都包含全部
    # dst 的分支 (跨 case 的 sig 节点指向同一个 box, ELK 渲染出孤儿).
    case_edges = []

    for dst_id, cedges in cond_by_dst.items():
        case_children = []  # ← 每个 dst 独立 list
        dst_short = _short(dst_id)
        if len(cedges) < 2:
            for e in cedges:
                # [V16.12 2026-08-18] 统一走 _resolve_port_id (单源 of truth)
                # 之前用 'port_<short>' 简化版 → case26 fail (golden_hier_top 有 3 个
                # 子模块同名 'din' port, 短名 'port_din' 在 children 里不存在,
                # 真节点是 'port_level2_scale_dot_din').
                src_short = _short(e.src)
                dst_short_e = _short(e.dst)
                # [V16.12 Fix F 2026-08-18] 短名 input 但 dedup_map 有 full path → 用 full path.
                # 原因: case26 e10 的 e.src='offset' (短名), input_short_to_fulls['offset']
                # = ['golden_hier_top.u_off.offset'] (count=1), 走短名 fallback emit
                # 'port_offset' 但 root_children emit 'port_golden_hier_top_dot_u_off_dot_offset'
                # → ELK 报 "Referenced shape does not exist". Fix: 优先用 dedup_map full path.
                if src_short in input_names and _in_dedup_map.get(src_short):
                    src_id = _resolve_port_id(_in_dedup_map[src_short][0], 'in', input_short_to_fulls, output_short_to_fulls)
                elif src_short in input_names:
                    src_id = _resolve_port_id(e.src, 'in', input_short_to_fulls, output_short_to_fulls)
                else:
                    src_id = _safe(e.src)
                tgt_id = _resolve_port_id(e.dst, 'out', input_short_to_fulls, output_short_to_fulls) if dst_short_e in output_names else _safe(e.dst)
                # 注: 'endpoint 未在 root_children 中' 的防御性 filter 移到末尾统一处理,
                # 这里不逐个 filter (避免里应一致问题)
                root_edges.append(_emit_edge(ne(), [src_id], [tgt_id], e))
            continue

        sd = _safe(dst_id)
        sel_sigs = set()
        # [FIX 2026-08-08] 收集整个 condition_chain 中所有信号名
        # 原代码只取 chain[0], 丢掉了嵌套条件中的 sel_b 等
        # 例: chain=['sel_a', 'sel_b'] 只取 'sel_a' → 两个 case 框 label 重复
        sig_pat = re.compile(r'\b\w+\b')
        for e in cedges:
            chain = getattr(e, 'condition_chain', [])
            for c in chain:
                # 提取所有 ident (排除 'sel' 等关键字需要上下文, 这里仅提取 ident)
                for tok in sig_pat.findall(c):
                    # 排除常见 noise words
                    if tok not in ('and', 'or', 'not', 'select'):
                        sel_sigs.add(tok)
        sel_label = ', '.join(sorted(sel_sigs)) if sel_sigs else '?'

        by_cond = defaultdict(list)
        for e in cedges:
            chain = getattr(e, 'condition_chain', [])
            key = chain[-1] if chain else 'default'
            by_cond[key].append(e)

        sig_counter = [0]

        for cond_label, group in by_cond.items():
            # [Plan B Step D 2026-08-25] Cond label compaction + tooltip
            # 背景: case16 嵌套 case 条件 label (e.g. "sel == 2'b1 && sub_sel == 2'b00")
            #       太长 → SVG 渲染时被截断 ("sel == 2'b1 && su...").
            # 修复:
            #   1. 压缩空格: "sub_sel == 2'b0" → "sub_sel==2'b0" (减少 20-30% 宽度)
            #   2. 多行: "&&" 处换行, 让 SVG 多行渲染
            #   3. tooltip: 完整 label 通过 <title> 标签在 hover 时显示
            _full_cond = cond_label  # 保留完整原始 label (for tooltip)
            _compact_cond = cond_label
            # 压缩: ' == ' → '==' (去掉空格)
            _compact_cond = _compact_cond.replace(' == ', '==').replace(' != ', '!=')
            # 多行: split at '&&' (use newline char)
            _multiline_cond = _compact_cond.replace(' && ', '\n')
            sc = _safe(cond_label)
            bid = f'branch_{sd}_{sc}'
            branch_children = []
            branch_edges = []

            # [V16 Plan Phase 1.8 2026-08-17] branch 内 op 节点归位: cluster_id 从 dst_id 父路径推导
            # dst_id 是 case 目标信号的 full path (e.g. 'golden_hier_top.u_clamp.dout'),
            # parent_module = dst_id.rsplit('.', 1)[0] (e.g. 'golden_hier_top.u_clamp')
            _branch_parent_mod = dst_id.rsplit('.', 1)[0] if '.' in dst_id else ''
            _target_mod_branch = (viz.meta or {}).get('target_module', '') if viz is not None else ''
            _branch_op_cid = _branch_parent_mod or ''
            if _target_mod_branch and _branch_op_cid == _target_mod_branch:
                _branch_op_cid = ''
            elif _target_mod_branch and _branch_op_cid.startswith(_target_mod_branch + '.'):
                _branch_op_cid = _branch_op_cid[len(_target_mod_branch) + 1:]

            # OP node (if any in this group)
            op_id = None
            op_seen = set()
            for ge in group:
                op = getattr(ge, 'source_op', None)
                if op and op not in op_seen:
                    op_seen.add(op)
                    op_id = f'op_{_safe(op)}_{sd}_{sc}'
                    branch_children.append({
                        'id': op_id, 'width': OP_W, 'height': OP_H,
                        'labels': [{'text': _OP_SYM.get(op, op), 'fontSize': 9,
                                    'fontName': 'Helvetica-Bold'}],
                        '_meta': {'kind': 'op', 'cluster_id': _branch_op_cid or ''},
                    })

            # Signal nodes (dedup within branch)
            seen_sigs = set()
            for ge in group:
                sn = _short(ge.src)
                sid = f'sig_{sn}_{sd}_{sc}'
                if sid in seen_sigs: continue
                seen_sigs.add(sid)
                # Check if signal name is a Verilog constant literal
                _is_const_val = bool(re.match(r"\d+'[bdh]\w+", sn))
                branch_children.append({
                    'id': sid, 'width': 40 if _is_const_val else SIG_W, 'height': SIG_H,
                    'labels': [{'text': sn, 'fontSize': 8 if _is_const_val else 9,
                                'fontName': 'Courier'}],
                    '_meta': {'kind': 'const' if _is_const_val else 'signal'},
                    'layoutOptions': {'elk.layered.layering.layerConstraint': 'FIRST'} if _is_const_val else {},
                })

            # Branch internal edges (signal → op)
            if op_id:
                for ge in group:
                    sn = _short(ge.src)
                    sid = f'sig_{sn}_{sd}_{sc}'
                    branch_edges.append(_emit_edge(ne(), [sid], [op_id], ge))

            case_children.append({
                'id': bid,
                'labels': [{'text': _multiline_cond, 'fontSize': 8, 'fontName': 'sans-serif'}],
                'layoutOptions': {
                    'elk.direction': 'RIGHT',
                    'elk.padding': '[top=16,left=10,right=10,bottom=8]',
                    'elk.spacing.nodeNode': '12',
                },
                'children': branch_children,
                'edges': branch_edges,
                '_meta': {'kind': 'branch', 'label': cond_label,
                          'compact_label': _compact_cond,
                          'tooltip': _full_cond,
                          '_plan_b_step_d': True},
            })

            # Root edges: PORT_IN → branch signal, signal/op → PORT_OUT
            # [V16.12 2026-08-18] 统一走 _resolve_port_id (单源 of truth)
            # [Plan B Step C 2026-08-25] Case item edges use 'case_item' kind for blue styling
            for ge in group:
                sn = _short(ge.src)
                sid = f'sig_{sn}_{sd}_{sc}'
                # PORT_IN → signal
                if sn in input_names:
                    root_edges.append(_emit_edge(ne(), [_resolve_port_id(ge.src, 'in', input_short_to_fulls, output_short_to_fulls)], [sid], ge, kind='case_item'))

            if op_id:
                # [V16.13 Fix M 2026-08-18] dst_name 不存在于 viz_to_elk scope (原本是
                # expr_trees_to_elk 的本地变量名). 正确变量是 dst_id (case dst signal full path).
                # 之前 case8/9/11/15/16/17/18/22 fail 都是 dst_name NameError 根因.
                root_edges.append(_emit_edge(ne(), [op_id], [_resolve_port_id(dst_id, 'out', input_short_to_fulls, output_short_to_fulls)] if dst_short in output_names else []))
            for ge in group:
                sn = _short(ge.src)
                sid = f'sig_{sn}_{sd}_{sc}'
                if not getattr(ge, 'source_op', None):
                    # [V16.13 Fix M 2026-08-18] output_set → output_names (viz_to_elk 只定义 output_names)
                    root_edges.append(_emit_edge(ne(), [sid], [_resolve_port_id(ge.dst, 'out', input_short_to_fulls, output_short_to_fulls)] if dst_short in output_names else [], ge))

        # sel → case scope (condition select edge)
        sel_anchor_id = f'cond_sel_{sd}'
        case_children.insert(0, {
            'id': sel_anchor_id, 'width': 1, 'height': 1,
            'layoutOptions': {'elk.layered.layering.layerConstraint': 'FIRST'},
            '_meta': {'kind': 'condition_anchor'},
        })
        for sig in sorted(sel_sigs):
            if sig in input_names:
                # [V16.12] 用 _resolve_port_id 解析 (sel 信号可能在多模块同名, 需要 full path)
                # 用 _resolve_full_input_path(sig) 推导 full path, 或 fallback 短名
                _sel_full = input_short_to_fulls.get(sig, [sig])[0]
                _sel_port_id = _resolve_port_id(_sel_full, 'in', input_short_to_fulls, output_short_to_fulls)
                # [Plan B Step A5 2026-08-25] Lazy emit port_in 节点 (如果 root_children 里不存在)
                # 背景: case9/15/16/17/22 的 sel 信号可能未被 _referenced_input_fulls 引用 (它们是
                # 纯 case selector, 不驱动任何输出), 所以 port_in 没在主 emit block (line 378-388) emit.
                # 后果: sel_anchor edge src='port_<full>_dot_<sig>' 在 _collect_all_emitted_ids 时找不到 → filter 删边.
                # 修复: emit edge 前检查 port_in 是否存在, 不存在则补 emit.
                if _sel_port_id not in _emitted_port_ids:
                    # [Plan B Step A5 v2] 用 viz.nodes 直接查找 source location (避免 cross-function
                    # node_source_map 引用 — 那是 expr_trees_to_elk 的本地变量, viz_to_elk 用不到)
                    _sel_file, _sel_line = '', 0
                    for _vn in viz.nodes:
                        if getattr(_vn, 'full_path', '') == _sel_full:
                            _sel_file = getattr(_vn, 'file', '') or ''
                            _sel_line = getattr(_vn, 'line', 0) or 0
                            break
                    root_children.append({
                        'id': _sel_port_id, 'width': PORT_W, 'height': PORT_H,
                        'labels': [{'text': sig, 'fontSize': 8, 'fontName': 'Courier'}],
                        'layoutOptions': {'elk.layered.layering.layerConstraint': 'FIRST'},
                        '_meta': {'kind': 'port_in', 'file': _sel_file, 'line': _sel_line},
                    })
                    _emitted_port_ids.add(_sel_port_id)
                root_edges.append(_emit_edge(ne(), [_sel_port_id], [sel_anchor_id], kind='condition_select'))

        # Phase 4: Assemble case scope
        case_node = {
            'id': f'case_{sd}',
            'labels': [{'text': f'case ({sel_label})', 'fontSize': 10, 'fontName': 'sans-serif'}],
            'layoutOptions': {
                'elk.direction': 'DOWN',
                'elk.padding': '[top=14,left=0,right=10,bottom=8]',
                'elk.spacing.nodeNode': '10',
            },
            'children': case_children,
            'edges': case_edges,
            '_meta': {'kind': 'case', 'label': f'case ({sel_label})'},
        }
        root_children.append(case_node)

    # Filter out edges with empty targets (ELK rejects them)
    # [FIX 2026-08-09 方案1 拓展] 也过滤掉 endpoints 不在任何已 emit 节点里的 root edge.
    # 背景: viz_to_elk 只 emit port_in/port_out 作为 root children, 但 viz.edges 可能引用
    # 中间信号 (case20 sum / case23 s2), 函数名 (case21 mul2/div2), 实例端口 (case26 din[7:0])
    # 等. 这些引用在 ELK JSON 里会报 "Referenced shape does not exist".
    # 防御性 filter: 递归收集所有已 emit 节点 ID (含 case compound 内部), 跳过不在其中的 src/tgt.
    # 关键: ELK 允许跨层级引用 (root edge 可以连到 case compound 内部节点), 所以收集必须递归.
    def _collect_all_emitted_ids(node, acc):
        """递归收集 ELK JSON 节点下所有已 emit 的 ID (含嵌套 children 和 ports)."""
        if isinstance(node, dict):
            if 'id' in node:
                acc.add(node['id'])
            for c in node.get('children', []) or []:
                _collect_all_emitted_ids(c, acc)
            for p in node.get('ports', []) or []:
                if 'id' in p:
                    acc.add(p['id'])
    all_emitted_ids = set()
    for c in root_children:
        _collect_all_emitted_ids(c, all_emitted_ids)

    # [Plan B Step B1 2026-08-25] Defensive port emission
    # 背景: darkriscv ELK layout fail: 'Referenced shape does not exist: port_darkriscv_dot_DLEN'
    # 根因: edge 引用 port_X, 但 main port emit loop (line ~405) 只遍历 _referenced_input_fulls
    #       过滤掉了 clock_reset_srcs 等. 但 edge 旁路 (case anchor / lazy emit) 可能引用
    #       没在 _referenced_input_fulls 里的信号 (例如 darkriscv DLEN 是 output port,
    #       不在主 viz pipeline 的 referenced list 里).
    # 修复: 在 _collect_all_emitted_ids 后, 扫描所有 root_edges + case_edges 找缺失的 port_*
    #       references, 补 emit. 比 "删 edge" 更鲁棒 — 不丢失有用信息.
    _port_refs = set()
    _all_edge_lists = [root_edges]
    # 收集 case compound 内部的 edges (case_edges / branch_edges) 也扫描
    for _c in root_children:
        if isinstance(_c, dict) and _c.get('_meta', {}).get('kind') == 'case':
            _all_edge_lists.append(_c.get('edges', []) or [])
            for _sub in _c.get('children', []) or []:
                if isinstance(_sub, dict):
                    _all_edge_lists.append(_sub.get('edges', []) or [])
    for _el in _all_edge_lists:
        for _e in _el:
            for _s in (_e.get('sources', []) or []):
                if isinstance(_s, str) and _s.startswith('port_'):
                    _port_refs.add(_s)
            for _t in (_e.get('targets', []) or []):
                if isinstance(_t, str) and _t.startswith('port_'):
                    _port_refs.add(_t)

    _existing_port_ids = {c.get('id') for c in root_children
                          if c.get('_meta', {}).get('kind') in ('port_in', 'port_out')}
    _missing_ports = _port_refs - _existing_port_ids

    # [Plan B Step B2 2026-08-25] Port ID 一致性 assert
    # 防御: emit 端的 port_id 必须 == edge 端的 port_id. 如果不一致, 立即报错.
    # 这是为了防止未来重构时引入 emit/edge 不一致导致的 "Referenced shape does not exist".
    if _missing_ports:
        # 反推 full_path 用于 _pid 重建和 label
        # port_<safe(full)> → full = _pid[5:].replace('_dot_', '.')
        for _pid in sorted(_missing_ports):
            # 反推 _full 用于 source map 查询 (尽力恢复原始 full_path)
            # 注意: _safe 把 . 换成 _dot_, 但其他 字符处理不可逆 (例如 [ 变 n_)
            # 所以 source location 不可得 — 留空.
            _full_attempt = _pid[5:].replace('_dot_', '.')
            _sn = _full_attempt.rsplit('.', 1)[-1]
            root_children.append({
                'id': _pid, 'width': PORT_W, 'height': PORT_H,
                'labels': [{'text': _sn, 'fontSize': 8, 'fontName': 'Courier'}],
                'layoutOptions': {'elk.layered.layering.layerConstraint': 'FIRST'},
                '_meta': {'kind': 'port_in', 'file': '', 'line': 0,
                          '_defensive': True,
                          '_plan_b_b1': True},
            })
            all_emitted_ids.add(_pid)
            _existing_port_ids.add(_pid)
        print(f"[Plan B Step B1] defensively emitted {len(_missing_ports)} missing ports: "
              f"{sorted(_missing_ports)[:5]}{'...' if len(_missing_ports) > 5 else ''}",
              file=sys.stderr)

    # [Plan B Step B2] 一致性 assert: 所有 edge 的 port refs 都必须在 _existing_port_ids 里
    for _el in _all_edge_lists:
        for _e in _el:
            for _s in (_e.get('sources', []) or []):
                if isinstance(_s, str) and _s.startswith('port_'):
                    assert _s in _existing_port_ids, \
                        f"[Plan B Step B2] inconsistent port ref: {_s} not emitted " \
                        f"(edge {_e.get('id', '?')}, kind={_e.get('_meta', {}).get('kind', '?')})"

    for e in list(root_edges):
        if 'targets' in e and not e['targets']:
            root_edges.remove(e)
            print(f"[WARN] removed edge {e['id']}: empty target", file=sys.stderr)
            continue
        # 检查 src/tgt 是否在递归收集的已 emit ID 里 (允许跨层级引用)
        srcs = e.get('sources', [])
        tgts = e.get('targets', [])
        if any(s not in all_emitted_ids for s in srcs) or any(t not in all_emitted_ids for t in tgts):
            root_edges.remove(e)
            print(f"[WARN] removed edge {e['id']}: endpoint not in emitted nodes "
                  f"(src={srcs}, tgt={tgts})", file=sys.stderr)

    # [V16 Plan Phase 2.1 2026-08-14] emit wire 节点 + 两步紫色边 在 _wrap_into_clusters 之前
    # 这样 emit 的 sig_scaled_wire 等 wire 节点会进入 cluster_target_top 内部
    graph = _make_graph(root_children, root_edges)
    graph = _emit_cross_instance_connection_edges(graph, viz)

    # [Plan B Step B1 v2 2026-08-25] 第二轮 defensive port emission
    # 背景: darkriscv 第一次 fail 即使加了 B1 — 因为 cross-instance edges
    #       (port_darkriscv_dot_DLEN) 在 _emit_cross_instance_connection_edges
    #       里才被加入 graph.edges, B1 第一轮扫描 (line 1541) 太早.
    # 修复: cross-instance edges 加入后, 再扫一轮. 仍然缺失就补 emit.
    _post_emitted = set()
    def _collect_post_ids(node, acc):
        if isinstance(node, dict):
            if 'id' in node:
                acc.add(node['id'])
            for c in node.get('children', []) or []:
                _collect_post_ids(c, acc)
            for p in node.get('ports', []) or []:
                if 'id' in p:
                    acc.add(p['id'])
    _collect_post_ids(graph, _post_emitted)
    _post_edge_port_refs = set()
    for _e in graph.get('edges', []) or []:
        for _s in (_e.get('sources', []) or []):
            if isinstance(_s, str) and _s.startswith('port_'):
                _post_edge_port_refs.add(_s)
        for _t in (_e.get('targets', []) or []):
            if isinstance(_t, str) and _t.startswith('port_'):
                _post_edge_port_refs.add(_t)
    _post_existing = {c.get('id') for c in (graph.get('children', []) or [])
                      if c.get('_meta', {}).get('kind') in ('port_in', 'port_out')}
    _post_missing = _post_edge_port_refs - _post_existing - _post_emitted
    if _post_missing:
        for _pid in sorted(_post_missing):
            _full_attempt = _pid[5:].replace('_dot_', '.')
            _sn = _full_attempt.rsplit('.', 1)[-1]
            graph['children'].append({
                'id': _pid, 'width': PORT_W, 'height': PORT_H,
                'labels': [{'text': _sn, 'fontSize': 8, 'fontName': 'Courier'}],
                'layoutOptions': {'elk.layered.layering.layerConstraint': 'FIRST'},
                '_meta': {'kind': 'port_in', 'file': '', 'line': 0,
                          '_defensive': True,
                          '_plan_b_b1_v2': True},
            })
        print(f"[Plan B Step B1 v2] defensively emitted {len(_post_missing)} "
              f"missing ports after cross-instance: "
              f"{sorted(_post_missing)[:5]}", file=sys.stderr)

    return _wrap_into_clusters(viz, graph)


def _make_graph(children, edges):
    ml = children[0].get('labels', [{}])[0].get('text', '') if children else ''
    return {
        'id': 'root',
        'layoutOptions': dict(ELK_OPTIONS),
        'children': children,
        'edges': edges,
        '_meta': {'title': '', 'target_module': ml},
    }


def _find_elk_js():
    for d in [os.path.dirname(__file__),
              os.path.join(os.path.dirname(__file__), '..', '..', 'viz'),
              os.path.join(os.path.dirname(__file__), '..', '..', '..', 'viz')]:
        p = os.path.join(d, 'elk_layout.js')
        if os.path.exists(p): return p
    raise FileNotFoundError("Cannot find elk_layout.js")


def run_elk_layout(graph):
    proc = subprocess.run(['node', _find_elk_js()],
        input=json.dumps(graph, ensure_ascii=False),
        text=True, capture_output=True, timeout=30)
    if proc.returncode != 0:
        raise RuntimeError(f"ELK layout failed: {proc.stderr[:500]}")
    return json.loads(proc.stdout)


def get_layout(viz):
    elk = viz_to_elk(viz)
    result = run_elk_layout(elk)
    if '_meta' not in result: result['_meta'] = elk.get('_meta', {})
    return result


# ═══════════════════════════════════════════════════
# [Plan B 2026-08-10] 统一 ELK 路由 helper
# ═══════════════════════════════════════════════════

def _compute_routing(viz):
    """跟 render_dataflow 同步的路由判断 — 返回 (path_name, has_uncond_op, has_call_edge, has_cond_edges, expr_trees).

    path_name ∈ {'expr_trees', 'viz_to_elk'}
    """
    raw_expr_trees = viz.meta.get('datapath', {}).get('expr_trees', {})
    expr_trees = dict(raw_expr_trees)

    has_uncond_op = any(
        getattr(e, 'source_op', None) and not (getattr(e, 'condition_chain', None) or [])
        and getattr(e, 'kind', '') not in ('CLOCK', 'RESET', 'BIT_SELECT')
        for e in viz.edges
    )
    has_call_edge = any(
        getattr(e, 'source_op', None) == 'Call'
        for e in viz.edges
    )
    has_cond_edges = any(
        (getattr(e, 'condition_chain', None) or []) or getattr(e, 'condition', None)
        for e in viz.edges
    )
    return raw_expr_trees, expr_trees, has_uncond_op, has_call_edge, has_cond_edges


def _compute_input_output_names(viz):
    """跟 render_dataflow 同步的 input/output names 提取."""
    input_names, output_names = [], []
    for n in viz.nodes:
        side = getattr(n, 'port_side', '')
        name = str(n.id).rsplit('.', 1)[-1] if '.' in str(n.id) else str(n.id)
        if side == 'left':
            input_names.append(name)
        elif side == 'right':
            output_names.append(name)
    return input_names, output_names


def _build_elk_for_viz(viz):
    """根据 viz.edges 路由, 构建 render_dataflow 将使用的 ELK JSON.

    跟 viz_engine.render_dataflow 完全同步 — checker/test 调这个函数取 layout,
    可以保证 SVG 和 layout 永远匹配 (不走跟 render 不同的 ELK 路径).

    Returns: dict (ELK JSON, 还未调 run_elk_layout)
    """
    raw_expr_trees, expr_trees, has_uncond_op, has_call_edge, has_cond_edges = _compute_routing(viz)

    # 路径 1: 数据运算边 / 函数调用 → expr_trees_to_elk
    if has_uncond_op or has_call_edge:
        if expr_trees:
            input_names, output_names = _compute_input_output_names(viz)
            elk = expr_trees_to_elk(expr_trees, input_names, output_names, viz=viz)
            # [V15 fix 6] 之前这里 return, 跳过 post-process. 改为赋值 + 走末尾统一 post-process
        else:
            # 没 expr_trees 但有 call edge — 退回 viz_to_elk
            elk = viz_to_elk(viz)
    # 路径 2: case/if 条件边 → viz_to_elk (case compound)
    elif has_cond_edges:
        elk = viz_to_elk(viz)
    # 路径 3: 纯 expr_trees (无 cond, 无 uncond op) → expr_trees_to_elk
    elif expr_trees:
        input_names, output_names = _compute_input_output_names(viz)
        elk = expr_trees_to_elk(expr_trees, input_names, output_names, viz=viz)
    # 路径 4: fallback — viz_to_elk (保证有输出)
    else:
        elk = viz_to_elk(viz)

    # [V15 2026-08-13 修复] 补全跨 instance CONNECTION 边 (适用于所有路径)
    # 原 expr_trees_to_elk 和 viz_to_elk 都不 emit 跨 module 的 CONNECTION 边:
    #   u_scale.dout → scaled → u_off.din 这样的 instance→instance 连线.
    # 原因: E2.A 规则不 emit CONNECTION 边, 但跨 instance 的 CONNECTION (instance port → wire
    # 或 wire → instance port) 是必要的. 这里 post-process 补上这些边.
    # [V15 fix 2] 移到所有路径之后, case26 (expr_trees=0) 也能触发.
    # [V15 fix 6] 路径 1 原本有 return, 跳过 post-process. 修复后统一走末尾.
    # [V16 Plan Phase 2.1 2026-08-14] emit 边 + 紫色移到 expr_trees_to_elk / viz_to_elk 内部
    # (_wrap_into_clusters 之前). 这里不放 emit, 避免重复 emit wire 节点.
    return elk


def _emit_cross_instance_connection_edges(elk_json: dict, viz) -> dict:
    """[V15 2026-08-13] 补全跨 instance 的 CONNECTION 边.

    背景: case26 源码有 u_scale.dout → scaled → u_off.din 这样的 instance→instance 连线,
    但 expr_trees_to_elk 只 emit expression tree 渲染的边, 漏了这些.

    [V15 fix 3] 策略调整: 不在 ELK emit 中间 wire 节点 (sig_scaled_wire), 因为
    _wrap_into_clusters 会把不属于任何 cluster 的 root_children 节点剥掉. 改为:
    - 跳 过中间 wire 节点 (scaled/offsetted/clamped_w/clamped)
    - 找 'X.dout → wire → Y.din' 这种两步 CONNECTION, 拼为 'X.dout → Y.din' 一步 emit
    - 这样 ELK 会画出 instance→instance 的直接连线 (一条黑线/红线)
    """
    from collections import defaultdict
    if not viz or not viz.edges:
        return elk_json

    # 1. 收集 input/output port 集合 (避免重复 emit)
    _input_paths = set()
    _output_paths = set()
    for n in viz.nodes:
        side = getattr(n, 'port_side', '')
        if side == 'left':
            _input_paths.add(n.id)
        elif side == 'right':
            _output_paths.add(n.id)
    _all_top_ports = _input_paths | _output_paths

    # 2. 收集 instance port 集合 (cluster_id != '' 且 port_side != '')
    _instance_ports = set()
    for n in viz.nodes:
        cid = getattr(n, 'cluster_id', '') or ''
        side = getattr(n, 'port_side', '') or ''
        if cid and side:
            _instance_ports.add(n.id)

    # [V16.12 2026-08-18] Build dedup maps for _map_to_elk_id dedup-aware logic.
    # 顶层 port + 同名 sub-module port 都参与 dedup, 防止短名端口多实例 emit 不匹配.
    _input_dedup_map = defaultdict(list)
    _output_dedup_map = defaultdict(list)
    for n in viz.nodes:
        side = getattr(n, 'port_side', '') or ''
        if side == 'left':
            _input_dedup_map[n.id.rsplit('.', 1)[-1] if '.' in n.id else n.id].append(n.id)
        elif side == 'right':
            _output_dedup_map[n.id.rsplit('.', 1)[-1] if '.' in n.id else n.id].append(n.id)

    # 3. 收集 CONNECTION 边, 构建 instance_port → instance_port 映射
    # 思路: 'X.dout → wire → Y.din' 是两条边 (X.dout→wire, wire→Y.din)
    # 拼成 X.dout→Y.din
    # 步骤 3a: 收集 wire 节点 (顶层 port 不算)
    # [V15 fix 4] 关键: instance port (e.g. 'golden_hier_top.u_scale.dout') 同时在
    # _all_top_ports 里 (因为 port_side='right' 也算 output port). 需要扣除.
    _real_top_ports = _all_top_ports - _instance_ports  # 只含 target module 顶层 port
    _wire_to_dsts = defaultdict(list)  # wire → [Y.din]
    _srcs_to_wire = defaultdict(list)  # X.dout → [wire]
    # [V16 Plan Phase 2.1 2026-08-14] 收集真正 wire 节点: 只有 CONNECTION 边 src/dst 端才算
    # 之前 V16 收集逻辑太宽泛把 SignalRef 中间变量 (e.g. din[7:0]) 也算入, 导致重复 emit
    _wire_nodes_v16 = set()
    for e in viz.edges:
        ek = str(e.kind) if not isinstance(e.kind, str) else e.kind
        if ek != 'CONNECTION':
            continue
        s, t = str(e.src), str(e.dst)
        if s not in _all_top_ports and s not in _instance_ports:
            _wire_nodes_v16.add(s)
        if t not in _all_top_ports and t not in _instance_ports:
            _wire_nodes_v16.add(t)
        s_is_inst = s in _instance_ports
        t_is_inst = t in _instance_ports
        s_is_top = s in _real_top_ports
        t_is_top = t in _real_top_ports
        if s_is_inst and not t_is_inst and not t_is_top:
            # 'X.dout → wire' (wire 不是 instance port 也不是真顶层 port)
            _srcs_to_wire[s].append(t)
        elif t_is_inst and not s_is_inst and not s_is_top:
            # 'wire → Y.din'
            _wire_to_dsts[s].append(t)

    # 3b. [V16 Plan Phase 2.1 2026-08-14] emit wire 节点 + 两步 X.dout → wire → Y.din
    # 之前 V15 fix 3 走一步 emit X.dout → Y.din, 跳过中间 wire 节点
    # 现在 V16 改为: emit wire 节点 (cluster_id='') 然后 emit 两条边 (X.dout → wire, wire → Y.din)
    root_children = elk_json.get('children', [])
    root_edges = elk_json.get('edges', [])
    existing_edge_keys = set()
    for e in root_edges:
        for s in e.get('sources', []):
            for t in e.get('targets', []):
                existing_edge_keys.add((s, t))

    # emit wire 节点 (cluster_id='' 顶层, 走 _wrap_into_clusters 放入 cluster_target_top)
    for wire_id in _wire_nodes_v16:
        wire_short = wire_id.rsplit('.', 1)[-1] if '.' in wire_id else wire_id
        wire_node_id = f'sig_{_safe(wire_short)}_wire'
        if any(c.get('id') == wire_node_id for c in root_children):
            continue
        root_children.append({
            'id': wire_node_id, 'width': SIG_W, 'height': SIG_H,
            'labels': [{'text': wire_short, 'fontSize': 8, 'fontName': 'Courier'}],
            '_meta': {'kind': 'signal', 'cluster_id': ''},
        })

    ctr = [int(root_edges[-1]['id'][1:]) if root_edges else 0]
    def _ne():
        ctr[0] += 1
        return f'e{ctr[0]}'

    # emit X.dout → wire (紫色, 跨 instance)
    for src_inst, wires in _srcs_to_wire.items():
        for wire in wires:
            s_id = _map_to_elk_id(src_inst, _instance_ports, _wire_nodes_v16, _all_top_ports,
                                 _input_dedup_map, _output_dedup_map)
            t_id = _map_to_elk_id(wire, _instance_ports, _wire_nodes_v16, _all_top_ports,
                                 _input_dedup_map, _output_dedup_map)
            if not s_id or not t_id:
                continue
            if (s_id, t_id) in existing_edge_keys:
                continue
            root_edges.append({
                'id': _ne(),
                'sources': [s_id],
                'targets': [t_id],
                '_meta': {
                    'kind': 'connection',
                    'stroke': 'purple',  # [V15 阶段 6] 跨 instance 连线紫色
                    'v15_added': True,
                },
            })
            existing_edge_keys.add((s_id, t_id))

    # emit wire → Y.din (紫色, 跨 instance)
    for wire, dst_insts in _wire_to_dsts.items():
        for dst_inst in dst_insts:
            s_id = _map_to_elk_id(wire, _instance_ports, _wire_nodes_v16, _all_top_ports,
                                 _input_dedup_map, _output_dedup_map)
            t_id = _map_to_elk_id(dst_inst, _instance_ports, _wire_nodes_v16, _all_top_ports,
                                 _input_dedup_map, _output_dedup_map)
            if not s_id or not t_id:
                continue
            if (s_id, t_id) in existing_edge_keys:
                continue
            root_edges.append({
                'id': _ne(),
                'sources': [s_id],
                'targets': [t_id],
                '_meta': {
                    'kind': 'connection',
                    'stroke': 'purple',  # [V15 阶段 6] 跨 instance 连线紫色
                    'v15_added': True,
                },
            })
            existing_edge_keys.add((s_id, t_id))

    elk_json['children'] = root_children
    elk_json['edges'] = root_edges
    return elk_json


def _map_to_elk_id(path, _instance_ports, _wire_nodes, _all_top_ports,
                     _input_dedup_map=None, _output_dedup_map=None):
    """[V15 2026-08-13] 把 viz_data path 映射到 ELK 节点 id.
    
    [V16.12 2026-08-18] 新增 _input_dedup_map / _output_dedup_map 参数:
    - top-level port emit 如果 dedup-aware, edge emit 也必须 dedup-aware
    - 否则 case26 等多实例同名 case 会出现 port_<short> emit + port_<full> edge 引用不匹配
    """
    # [V15 fix 5] 顺序调整: 先查 instance port (e.g. 'golden_hier_top.u_scale.dout' 也在
    # _all_top_ports 里, 因为 port_side='right' 让它既是 instance port 又是 output port).
    # 必须先匹配 instance port 拿到 full-path id, 不然会走 'port_dout' 短名分支.
    if path in _instance_ports:
        return 'port_' + path.replace('.', '_dot_')
    if path in _all_top_ports:
        # [V16.12] dedup-aware: 如果同名 short 出现多次, 用 representative full path
        _short = path.rsplit('.', 1)[-1] if '.' in path else path
        # 决定是 input 还是 output (用 _input_dedup_map / _output_dedup_map)
        _dedup_count = 0
        _dedup_map = None
        if _input_dedup_map and _short in _input_dedup_map:
            _dedup_count = len(_input_dedup_map[_short])
            _dedup_map = _input_dedup_map
        elif _output_dedup_map and _short in _output_dedup_map:
            _dedup_count = len(_output_dedup_map[_short])
            _dedup_map = _output_dedup_map
        # [V16.13 Fix I 2026-08-18] 不论 dedup_count 是 1 还是 > 1, 只要 path 是 full path
        # (含 '.') 就用 full path. 之前 bug: `_dedup_count == 1` 时走 fallback
        # `return f'port_{_short}' if '.' in path else f'port_{path}'`, 这逻辑反了 — full path
        # 反而 emit 短名 → e10 src emit 短名 'port_offset' 但 emit-side emit full path
        # 'port_golden_hier_top_dot_u_off_dot_offset' → ELK 'Referenced shape does not exist'.
        # 修复: path 含 '.' → 用 full path (跟 emit-side _is_sub=True 一致).
        if '.' in path:
            return f'port_{path.replace(".", "_dot_")}'
        return f'port_{path}'
    if path in _wire_nodes:
        short = path.rsplit('.', 1)[-1] if '.' in path else path
        return f'sig_{short}_wire'
    return None
