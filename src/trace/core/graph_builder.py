#==============================================================================
# graph_builder.py - Builder Layer
#==============================================================================

from typing import Dict, List, Optional
from dataclasses import dataclass, field
from .graph.models import SignalGraph, TraceNode, TraceEdge, NodeKind, EdgeKind
import pyslang
from .base import PyslangAdapter

@dataclass
class ExtractorResult:
    nodes: List[TraceNode] = field(default_factory=list)
    edges: List[TraceEdge] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    port_to_internal: Dict[str, str] = field(default_factory=dict)  # {inst_port_id: child_signal_id}

class DriverExtractor:
    def __init__(self, adapter: PyslangAdapter):
        self.adapter = adapter


    #==============================================================================
    # [NEW] 语义上下文提取方法 - 从 always_ff/if 语句提取时钟域和条件
    #==============================================================================

    def _extract_clock_from_always(self, n) -> str:
        """从 always_ff @(posedge clk) 提取时钟信号名"""
        s = getattr(n, 'statement', None) or getattr(n, 'body', None)
        if not s: return ""
        tc = getattr(s, 'timingControl', None)
        if tc: return self._extract_clock_from_event_ctrl(tc)
        return ""

    def _extract_clock_from_event_ctrl(self, n) -> str:
        """从 TimingControl 提取时钟,处理 or 连接的多个事件"""
        e = getattr(n, 'expr', None)
        if not e: return ""
        i = getattr(e, 'expr', None) or e
        def find_clock(expr):
            if expr is None: return ""
            if hasattr(expr, 'left') and hasattr(expr, 'right'):
                l = find_clock(expr.left)
                return l if l else find_clock(expr.right)
            edge_str = str(getattr(expr, 'edge', ''))
            if 'posedge' in edge_str or 'negedge' in edge_str:
                ce = getattr(expr, 'expr', None)
                return str(ce).strip() if ce else ""
            return ""
        return find_clock(i)

    def _extract_reset_from_event_ctrl(self, n) -> str:
        """从 TimingControl 提取复位信号(处理 or 连接的多个事件)"""
        e = getattr(n, 'expr', None)
        if not e: return ""
        # Unwrap parenthesized expression
        e = getattr(e, 'expr', None) or e

        def find_reset(expr):
            if expr is None: return ""
            if hasattr(expr, 'left') and hasattr(expr, 'right'):
                left = find_reset(expr.left)
                if left: return left
                return find_reset(expr.right)
            edge_str = str(getattr(expr, 'edge', ''))
            if 'negedge' in edge_str or 'posedge' in edge_str:
                ce = getattr(expr, 'expr', None)
                if ce:
                    name = str(ce).strip()
                    if 'rst' in name.lower():
                        return name
            return ""

        return find_reset(e)

    def _extract_condition_str(self, n) -> str:
        """从 if 语句提取条件表达式"""
        p = getattr(n, "predicate", None)
        if not p: return ""
        cs = getattr(p, "conditions", None)
        return str(cs).strip() if cs else str(p).strip()

    def _collect_stmts_with_context(self, n, ctx=None, d=0, _s=None):
        """递归收集语句,同时携带语义上下文 (clock_domain, condition)"""
        if _s is None: _s = set()
        if ctx is None: ctx = {"clock": "", "condition": ""}
        nid = id(n)
        if nid in _s: return []
        _s.add(nid)
        if n is None or d > 30: return []
        k = getattr(n, "kind", None)
        ks = str(k) if k else ""
        if ".TokenKind." in ks or "Trivia" in ks:
            return []
        r = []

        # InitialBlock
        if "InitialBlock" in ks:
            stmt = getattr(n, "statement", None) or getattr(n, "body", None)
            if stmt: r.extend(self._collect_stmts_with_context(stmt, ctx, d+1, _s))
            return r

        if any(x in ks for x in ["AlwaysFF", "AlwaysComb", "AlwaysLatch"]):
            cl = ""
            rst = ""
            if "AlwaysFF" in ks:
                cl = self._extract_clock_from_always(n)
                # Extract reset from timing control
                s = getattr(n, 'statement', None) or getattr(n, 'body', None)
                if s:
                    tc = getattr(s, 'timingControl', None)
                    if tc: rst = self._extract_reset_from_event_ctrl(tc)
            c2 = {**ctx, "clock": cl, "reset": rst}
            s = getattr(n, "statement", None) or getattr(n, "body", None)
            if s: r.extend(self._collect_stmts_with_context(s, c2, d+1, _s))
            return r

        if "TimingControl" in ks:
            tc = getattr(n, "timingControl", None)
            cl = self._extract_clock_from_event_ctrl(tc) if tc else ""
            c2 = {**ctx, "clock": cl}
            s = getattr(n, "statement", None)
            if s: r.extend(self._collect_stmts_with_context(s, c2, d+1, _s))
            return r

        if "Conditional" in ks and "Statement" in ks:
            cond = self._extract_condition_str(n)
            ts = getattr(n, "statement", None)
            if ts:
                c2 = cond
                if ctx["condition"]: c2 = ctx["condition"] + " && " + cond
                r.extend(self._collect_stmts_with_context(ts, {**ctx, "condition": c2}, d+1, _s))
            ec = getattr(n, "elseClause", None)
            if ec:
                ae = getattr(ec, "clause", None) or ec
                c2 = "!" + cond
                if ctx["condition"]: c2 = ctx["condition"] + " && !" + cond
                r.extend(self._collect_stmts_with_context(ae, {**ctx, "condition": c2}, d+1, _s))
            return r

        if "ElseClause" in ks:
            s = getattr(n, "clause", None)
            if s: r.extend(self._collect_stmts_with_context(s, ctx, d+1, _s))
            return r

        if "SequentialBlock" in ks:
            for a in ["body", "statements", "items"]:
                b = getattr(n, a, None)
                if b and hasattr(b, "__iter__") and not isinstance(b, str):
                    for i in b: r.extend(self._collect_stmts_with_context(i, ctx, d+1, _s))
            return r

        if "ExpressionStatement" in ks:
            e = getattr(n, "expr", None)
            if e: r.extend(self._collect_stmts_with_context(e, ctx, d+1, _s))
            return r

        # [NEW] 处理 task/function 调用
        if "InvocationExpression" in ks:
            # 收集这个调用表达式和上下文
            r.append((n, ctx, "invocation"))  # (node, ctx, type)
            return r

        if "Assignment" in ks:
            r.append((n, ctx))
            return r

        for a in dir(n):
            if a.startswith("_") or a in ["parent", "sourceRange", "attributes", "kind", "keyword", "items"]: continue
            if a in ["tokens", "trivia", "leadingTrivia", "trailingTrivia"]: continue
            try:
                ch = getattr(n, a)
                if callable(ch): continue
                if hasattr(ch, "__iter__") and not isinstance(ch, str):
                    for c in ch:
                        if hasattr(c, "kind"): r.extend(self._collect_stmts_with_context(c, ctx, d+1, _s))
                elif hasattr(ch, "kind"): r.extend(self._collect_stmts_with_context(ch, ctx, d+1, _s))
            except: pass
        return r

    def extract(self) -> ExtractorResult:
        result = ExtractorResult()

        # [FIX Issue 21] 初始化当前模块上下文
        self._current_module = None

        for module in self.adapter.get_modules():
            module_name = self.adapter.get_module_name(module)
            # [FIX Issue 21] 设置当前模块上下文，供 _get_signal 获取参数映射
            self._current_module = module

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
                    if 'inout' in direction.lower():
                        kind = NodeKind.PORT_INOUT
                    elif 'output' in direction.lower():
                        kind = NodeKind.PORT_OUT
                    else:
                        kind = NodeKind.PORT_IN
                    # 提取端口位宽 (传入 module 作为 scope 以解析参数)
                    port_width = self.adapter.extract_port_width(port_decl, scope=module)
                    # extract_port_width with scope returns dict, convert to tuple for compatibility
                    if isinstance(port_width, dict):
                        msb = port_width.get('msb_eval', port_width.get('msb_raw', 0))
                        lsb = port_width.get('lsb_eval', port_width.get('lsb_raw', 0))
                        try:
                            msb = int(msb) if msb is not None else 0
                        except (ValueError, TypeError):
                            msb = 0
                        try:
                            lsb = int(lsb) if lsb is not None else 0
                        except (ValueError, TypeError):
                            lsb = 0
                        port_width = (msb, lsb)
                    result.nodes.append(TraceNode(
                        id=port_id,
                        name=port_name,
                        module=module_name,
                        kind=kind,
                        width=port_width,
                        is_port=True
                    ))

            # [铁律4] 为每个信号创建 TraceNode
            # assign 语句
            for assign in self.adapter.get_assignments(module):
                # [系统化改造] 先提取原始 RHS，检查是否是 InvocationExpression
                raw_rhs = None
                if hasattr(assign, 'assignments') and assign.assignments:
                    raw_rhs = assign.assignments[0].right
                elif hasattr(assign, 'right'):
                    raw_rhs = assign.right
                
                # 检测 InvocationExpression，走专用路径
                if raw_rhs and hasattr(raw_rhs, 'kind') and 'Invocation' in str(raw_rhs.kind):
                    # 提取 LHS 信号名
                    raw_lhs = None
                    if hasattr(assign, 'assignments') and assign.assignments:
                        raw_lhs = assign.assignments[0].left
                    
                    # 先创建 LHS 节点（函数调用的目标）
                    if raw_lhs:
                        lhs_name = self._get_signal(raw_lhs)
                        if lhs_name:
                            dst_node_id = f"{module_name}.{lhs_name}"
                            if dst_node_id not in [n.id for n in result.nodes]:
                                result.nodes.append(TraceNode(
                                    id=dst_node_id, name=lhs_name, module=module_name,
                                    kind=NodeKind.SIGNAL, width=(1, 0)
                                ))
                    else:
                        lhs_name = None
                    
                    # 调用 _handle_invocation，传入 lhs_name 作为目标
                    self._handle_invocation(raw_rhs, {}, module, module_name, result, lhs_name)
                    continue
                
                # 正常解析
                lhs, rhs, rhs_expr = self._parse_assign(assign)
                if lhs and rhs:
                    # [FIX BUG] ScopedName: tb.data → 创建父子节点和 BIT_SELECT 边
                    # 支持嵌套 ScopedName: tb.data.sub → 创建 tb, tb.data, tb.data.sub
                    # 所有层级都连接到其直接父节点 (BIT_SELECT 边)
                    if '.' in lhs:
                        lhs_parts = lhs.split('.')
                        # 首先:确保所有中间父节点存在
                        for i in range(1, len(lhs_parts)):
                            parent_name = '.'.join(lhs_parts[:i])
                            parent_id = f"{module_name}.{parent_name}"
                            if parent_id not in [n.id for n in result.nodes]:
                                result.nodes.append(TraceNode(
                                    id=parent_id, name=parent_name, module=module_name,
                                    kind=NodeKind.PORT_IN, width=(1, 0)
                                ))
                        # 其次:为每个层级创建 BIT_SELECT 边 (child → parent)
                        # 即使父节点已存在,也要创建边
                        for i in range(len(lhs_parts) - 1):
                            child_name = '.'.join(lhs_parts[:i+2])  # ['p'] + ['sub', 'data'] = ['p','sub','data'], index 1 -> 'p.sub'
                            parent_name = '.'.join(lhs_parts[:i+1])
                            child_id = f"{module_name}.{child_name}"
                            parent_id = f"{module_name}.{parent_name}"
                            if child_id != parent_id:
                                # 检查边是否已存在
                                existing = next(((e.src, e.dst) for e in result.edges
                                    if e.src == child_id and e.dst == parent_id), None)
                                if not existing:
                                    result.edges.append(TraceEdge(
                                        src=child_id, dst=parent_id,
                                        kind=EdgeKind.BIT_SELECT, assign_type="internal"
                                    ))

                    # 创建 dst 节点
                    dst_node_id = f"{module_name}.{lhs}"
                    if dst_node_id not in [n.id for n in result.nodes]:
                        result.nodes.append(TraceNode(
                            id=dst_node_id, name=lhs, module=module_name,
                            kind=NodeKind.SIGNAL, width=(1, 0)
                        ))
                    # [NEW] 使用 rhs_expr (来自 _parse_assign) 提取所有驱动源
                    rhs_signals = self._get_all_signals(rhs_expr) if rhs_expr else [rhs]
                    if not rhs_signals:
                        rhs_signals = [rhs]
                    for rhs_name in rhs_signals:
                        if not rhs_name:
                            continue
                        # [FIX] 字面量常量(如 "1"、"A5A5A5A5")不拼接 top. 前缀,不创建节点,只创建边
                        if rhs_name and not rhs_name[0].isalpha() and not rhs_name.startswith('_'):
                            # 字面量:直接用作 edge src,不创建节点
                            result.edges.append(TraceEdge(
                                src=rhs_name, dst=dst_node_id,
                                kind=EdgeKind.DRIVER, assign_type="continuous"
                            ))
                        else:
                            src_node_id = f"{module_name}.{rhs_name}"
                            if src_node_id not in [n.id for n in result.nodes]:
                                result.nodes.append(TraceNode(
                                    id=src_node_id, name=rhs_name, module=module_name,
                                    kind=NodeKind.SIGNAL, width=(1, 0)
                                ))
                            result.edges.append(TraceEdge(
                                src=src_node_id, dst=dst_node_id,
                                kind=EdgeKind.DRIVER, assign_type="continuous"
                            ))

            # always 块 - [铁律7金标准] + 语义上下文
            for always in self.adapter.get_always_blocks(module):
                # 使用语义上下文方法收集语句
                stmts_ctx = self._collect_stmts_with_context(always)
                for item in stmts_ctx:
                    # 支持两种格式: (stmt, ctx) 或 (stmt, ctx, type)
                    if len(item) == 3:
                        stmt, ctx, item_type = item
                    else:
                        stmt, ctx = item
                        item_type = "assignment"

                    # 如果是 invocation,暂不处理赋值
                    if item_type == "invocation":
                        # [NEW] 处理 task/function 调用
                        self._handle_invocation(stmt, ctx, module, module_name, result)
                        continue

                    lhs, rhs, rhs_expr = self._parse_assign(stmt)
                    if lhs and rhs:
                        dst_node_id = f"{module_name}.{lhs}"
                        # Only upgrade to REG if there's a clock context (always_ff)
                        is_always_ff = bool(ctx.get('clock'))
                        existing = next((n for n in result.nodes if n.id == dst_node_id), None)
                        if existing:
                            if is_always_ff:
                                if existing.kind == NodeKind.SIGNAL:
                                    existing.kind = NodeKind.REG
                                elif existing.kind in (NodeKind.PORT_OUT, NodeKind.PORT_IN):
                                    was_port = existing.is_port
                                    existing.kind = NodeKind.REG
                                    existing.is_port = was_port
                        else:
                            kind = NodeKind.REG if is_always_ff else NodeKind.SIGNAL
                            result.nodes.append(TraceNode(
                                id=dst_node_id, name=lhs, module=module_name,
                                kind=kind, width=(1, 0)
                            ))
                        # [NEW] 使用 rhs_expr (来自 _parse_assign) 提取所有驱动源
                        rhs_signals = self._get_all_signals(rhs_expr) if rhs_expr else [rhs]
                        if not rhs_signals:
                            rhs_signals = [rhs]
                        for rhs_name in rhs_signals:
                            if not rhs_name:
                                continue
                            # [FIX] 字面量常量(如 "1"、"A5A5A5A5")不拼接 top. 前缀,不创建节点,只创建边
                            if rhs_name and not rhs_name[0].isalpha() and not rhs_name.startswith('_'):
                                # 字面量:直接用作 edge src,不创建节点
                                result.edges.append(TraceEdge(
                                    src=rhs_name, dst=dst_node_id,
                                    kind=EdgeKind.DRIVER, assign_type="nonblocking",
                                    clock_domain=ctx.get("clock", ""),
                                    condition=ctx.get("condition", "")
                                ))
                            else:
                                src_node_id = f"{module_name}.{rhs_name}"
                                if src_node_id not in [n.id for n in result.nodes]:
                                    result.nodes.append(TraceNode(
                                        id=src_node_id, name=rhs_name, module=module_name,
                                        kind=NodeKind.SIGNAL, width=(1, 0)
                                    ))
                                result.edges.append(TraceEdge(
                                    src=src_node_id, dst=dst_node_id,
                                    kind=EdgeKind.DRIVER, assign_type="nonblocking",
                                    clock_domain=ctx.get("clock", ""),
                                    condition=ctx.get("condition", "")
                                ))

                            # [NEW] CLOCK 边: always_ff 块内创建 clk -> dst (CLOCK) 边
                            clock_signal = ctx.get("clock", "")
                            if clock_signal:
                                clock_node_id = f"{module_name}.{clock_signal}"
                                if clock_node_id not in [n.id for n in result.nodes]:
                                    result.nodes.append(TraceNode(
                                        id=clock_node_id, name=clock_signal, module=module_name,
                                        kind=NodeKind.SIGNAL, width=(1, 0)
                                    ))
                                result.edges.append(TraceEdge(
                                    src=clock_node_id, dst=dst_node_id,
                                    kind=EdgeKind.CLOCK, assign_type="nonblocking",
                                    clock_domain=clock_signal,
                                    condition=ctx.get("condition", "")
                                ))

                            # [NEW] RESET 边: always_ff 块内创建 rst -> dst (RESET) 边
                            reset_signal = ctx.get("reset", "")
                            if reset_signal:
                                reset_node_id = f"{module_name}.{reset_signal}"
                                if reset_node_id not in [n.id for n in result.nodes]:
                                    result.nodes.append(TraceNode(
                                        id=reset_node_id, name=reset_signal, module=module_name,
                                        kind=NodeKind.SIGNAL, width=(1, 0)
                                    ))
                                result.edges.append(TraceEdge(
                                    src=reset_node_id, dst=dst_node_id,
                                    kind=EdgeKind.RESET, assign_type="nonblocking",
                                    clock_domain=clock_signal,
                                    condition=ctx.get("condition", "")
                                ))

        return result


    def _collect_assignments_from_stmt(self, node, statements: list, depth=0):
        if node is None or depth > 30:
            return

        # [P0] 处理 always_comb 的 statement 属性 (不是 body)
        kind = getattr(node, 'kind', None)

        # 递归进入 always_comb 的 statement
        if kind and 'AlwaysCombBlock' in str(kind):
            if hasattr(node, 'statement'):
                stmt = node.statement
                if stmt:
                    self._collect_assignments_from_stmt(stmt, statements, depth+1)
                    return

        # [P2] 处理 InitialBlock (initial 块) - 在 statement 中
        if kind and 'InitialBlock' in str(kind):
            #statement = getattr(node, 'statement', None)
            #if statement:
            #    self._collect_assignments_from_stmt(statement, statements, depth+1)
            pass

        # [P2] 处理 ProceduralBlockSyntax (initial/always_comb/always_ff)
        if kind and 'ProceduralBlock' in str(kind):
            if hasattr(node, 'statement') or hasattr(node, 'body'):
                stmt = getattr(node, 'statement', None) or getattr(node, 'body', None)
                if stmt:
                    self._collect_assignments_from_stmt(stmt, statements, depth+1)
            return
        # [P2] 处理 EventControlWithExpression (@posedge clk 等)
        if kind and 'EventControl' in str(kind):
            if hasattr(node, 'statement'):
                self._collect_assignments_from_stmt(node.statement, statements, depth+1)
            return

        # [P2] 处理 SequentialBlockStatement (begin...end 块)
        if kind and 'SequentialBlock' in str(kind):
            for attr in ['body', 'statements', 'items']:
                if hasattr(node, attr):
                    block = getattr(node, attr)
                    if block and hasattr(block, '__iter__') and not isinstance(block, str):
                        for item in block:
                            self._collect_assignments_from_stmt(item, statements, depth+1)
            return

        # [P2] 处理 LoopStatement (while/for/repeat 循环)
        if kind and 'LoopStatement' in str(kind):
            # while 循环体在 statement 属性中
            if hasattr(node, 'statement'):
                self._collect_assignments_from_stmt(node.statement, statements, depth+1)
            return

        # [铁律2] 支持所有赋值类型
        kind_str = str(kind) if kind else ''
        # [P1] 支持 case 语句内的赋值 - 需同时提取 condition
        if kind and 'Case' in kind_str:
            for item in node.items:
                if not item:
                    continue
                # 获取赋值 statement (y = 1 或 y = 0)
                stmt = getattr(item, 'clause', None) or getattr(item, 'statement', None)
                if stmt:
                    self._collect_assignments_from_stmt(stmt, statements, depth+1)

                # [NEW] 获取 case condition (a 或 b) 作为驱动
                condition = getattr(item, 'condition', None)
                if condition:
                    # 将 condition 作为驱动源添加
                    statements.append(condition)
            return
            if hasattr(node, 'items') and node.items:
                print(f'[DEBUG case] items count={len(list(node.items))}')
                for idx, item in enumerate(node.items):
                    print(f'[DEBUG case] item[{idx}]: {type(item).__name__}')
                    if hasattr(item, 'statement'):
                        print(f'  statement: {item.statement}')

            for item in node.items:
                if item:
                    stmt = getattr(item, 'statement', None)
                    if stmt:
                        self._collect_assignments_from_stmt(stmt, statements, depth+1)
            return
        if kind and ('Assignment' in kind_str):
            statements.append(node)
            return
        if kind and 'Nonblocking' in kind_str:
            pass  # 继续遍历
        # [P0] 支持 always_comb 阻塞赋值
        #pyslang 10.0: always_comb 用 AssignmentExpression
        if kind and ('Blocking' in kind_str or 'AssignmentExpression' == kind_str):
            statements.append(node)
            return
        # [P0] 支持 always_ff 内部 ExpressionStatement
        if kind and 'ExpressionStatement' in kind_str:
            statements.append(node)
            return

        for attr in dir(node):
            if attr.startswith('_'):
                continue
            if attr in ['parent', 'kind', 'sourceRange', 'attributes']:
                continue

            try:
                child = getattr(node, attr)
                if callable(child):
                    continue
                if hasattr(child, '__iter__') and not isinstance(child, str):
                    for c in child:
                        self._collect_assignments_from_stmt(c, statements, depth+1)
                elif hasattr(child, 'kind'):
                    self._collect_assignments_from_stmt(child, statements, depth+1)
            except:
                pass

    def _parse_assign(self, assign) -> tuple:
        """
        解析赋值语句，返回 (lhs_name, rhs_name, rhs_expr)
        - lhs_name: 左操作数信号名
        - rhs_name: 右操作数信号名 (简单信号，用于简单赋值)
        - rhs_expr: 原始 RHS 表达式 (用于复杂类型判断和_get_all_signals)
        """
        # [P0] 处理 ExpressionStatement (always_ff/always_comb 内部)
        if hasattr(assign, 'expr'):
            assign = assign.expr

        try:
            # [P1] DataDeclaration 处理 (class 实例化等)
            # 格式: my_cls obj = new();
            if hasattr(assign, 'declarators') and assign.declarators:
                decl = assign.declarators[0]
                lhs = getattr(decl, 'name', None)
                rhs = getattr(decl, 'initializer', None)
                lhs_name = self._get_signal(lhs)
                # RHS 是构造函数调用,提取函数名
                rhs_name = self._get_constructor_call(rhs) if rhs else None
                return lhs_name, rhs_name, rhs

            if hasattr(assign, 'assignments') and assign.assignments:
                a = assign.assignments[0]
                lhs = a.left if hasattr(a, 'left') else None
                rhs = a.right if hasattr(a, 'right') else None
            else:
                lhs = getattr(assign, 'left', None) or getattr(assign, 'lhs', None)
                rhs = getattr(assign, 'right', None) or getattr(assign, 'rhs', None)

            lhs_name = self._get_signal(lhs)
            rhs_name = self._get_signal(rhs)

            return lhs_name, rhs_name, rhs
        except:
            return None, None, None

    def _get_constructor_call(self, initializer) -> Optional[str]:
        """提取构造函数调用名 (new())"""
        if initializer is None:
            return None
        # initializer 结构: = new()
        # 提取函数调用名
        if hasattr(initializer, 'name'):
            name = initializer.name
            return name.value if hasattr(name, 'value') else str(name)
        return 'new'  # 默认返回 new

    def _find_func_assignment_rhs(self, stmt, func_name):
        """
        在语句中查找函数赋值语句的 RHS
        例如: gray_conv = {a[7], a[6:0] ^ a[7:1]} 返回 ConcatenationExpression AST
        """
        if stmt is None:
            return None
        
        kind = str(getattr(stmt, 'kind', ''))
        
        # ExpressionStatement
        if 'ExpressionStatement' in kind:
            expr = getattr(stmt, 'expr', None)
            if expr:
                left = getattr(expr, 'left', None)
                right = getattr(expr, 'right', None)
                if left and right:
                    # 检查是否是函数名的赋值
                    left_name = None
                    if hasattr(left, 'identifier'):
                        ident = left.identifier
                        left_name = getattr(ident, 'value', None) or str(ident).strip()
                    elif hasattr(left, 'value'):
                        left_name = str(left.value).strip()
                    
                    if left_name == func_name:
                        return right
            return None
        
        # SequentialBlock
        if 'SequentialBlock' in kind:
            # SequentialBlockStatement 的 children 结构:
            # [0]: SyntaxList (可能是空的或包含 begin/end 标记)
            # [1]: BeginKeyword
            # [2]: SyntaxList (包含实际的 statements)
            # [3]: EndKeyword
            # 所以需要找 children[2] 作为 statements 列表
            statements = None
            for i, child in enumerate(stmt):
                child_kind = str(getattr(child, 'kind', ''))
                if 'SyntaxList' in child_kind and i == 2:
                    # This is the statements list
                    statements = child
                    break
            
            if statements is None:
                # Fallback to iterating over stmt itself
                for item in stmt:
                    item_kind = str(getattr(item, 'kind', ''))
                    if 'ExpressionStatement' in item_kind:
                        result = self._find_func_assignment_rhs(item, func_name)
                        if result:
                            return result
            else:
                for item in statements:
                    item_kind = str(getattr(item, 'kind', ''))
                    if 'ExpressionStatement' in item_kind:
                        result = self._find_func_assignment_rhs(item, func_name)
                        if result:
                            return result
        
        return None

    def _handle_invocation(self, invocation, ctx, module, module_name, result, lhs_name=None):
        """
        处理 task/function 调用
        建立参数映射并添加边
        
        Args:
            invocation: InvocationExpression AST 节点
            ctx: 上下文（时钟、复位等）
            module: 模块 AST 节点
            module_name: 模块名
            result: TraceResult 用于收集节点和边
            lhs_name: 可选，函数调用的目标信号名（ContinuousAssign 的 LHS）
        """
        try:
            # 获取调用名称
            callee = getattr(invocation, 'left', None)
            if not callee:
                return
            call_name = str(callee).strip()

            # 获取调用参数 (OrderedArgument 或 NamedArgument 列表)
            args_node = getattr(invocation, 'arguments', None)
            if not args_node:
                return

            call_args = []  # 位置参数列表
            named_args = {}  # 命名参数字典 {name: signal}
            params = getattr(args_node, 'parameters', [])
            for arg in params:
                arg_kind = str(getattr(arg, 'kind', ''))
                # 跳过逗号等 token
                if 'OrderedArgument' in arg_kind:
                    expr = getattr(arg, 'expr', None)
                    if expr:
                        arg_name = self._get_signal(expr)
                        if arg_name:
                            call_args.append(arg_name.strip())
                elif 'NamedArgument' in arg_kind:
                    # 命名参数: .name(expr)
                    name = getattr(arg, 'name', None)
                    expr = getattr(arg, 'expr', None)
                    if name and expr:
                        name_str = str(name).strip()
                        arg_name = self._get_signal(expr)
                        if arg_name:
                            named_args[name_str] = arg_name.strip()

            # 查找 task 定义 - 在 module 中查找
            task_def = None
            for task in self.adapter.get_task_declarations(module):
                if self.adapter.get_task_name(task) == call_name:
                    task_def = task
                    break

            if not task_def:
                # 查找 function 定义
                for func in self.adapter.get_function_declarations(module):
                    if self.adapter.get_function_name(func) == call_name:
                        task_def = func
                        break

            if not task_def:
                return

            # 获取定义参数
            if 'Task' in str(getattr(task_def, 'kind', '')):
                def_params = self.adapter.get_task_params(task_def)
            else:
                def_params = self.adapter.get_function_params(task_def)

            # 建立映射: def_params[i] -> call_args[i] 或 named_args[name]
            param_map = {}  # def_param_name -> call_arg_name
            for i, (direction, param_name) in enumerate(def_params):
                # 首先尝试从命名参数获取
                if param_name in named_args:
                    param_map[param_name] = named_args[param_name]
                # 否则从位置参数获取
                elif i < len(call_args):
                    param_map[param_name] = call_args[i]

            # 分析 task/function 内部的驱动关系
            internal_drivers = self.adapter.analyze_task_internal_drivers(task_def)

            # [FIX] 对于函数，还需要处理隐式返回值（函数名本身作为output）
            # 函数调用: gray_conv(in) -> 返回值驱动内部 expression
            # 需要映射 call_args -> def_params，然后从 internal_drivers 获取返回值驱动源
            is_function = 'Function' in str(getattr(task_def, 'kind', ''))
            
            # 建立映射: def_param_name -> call_arg_name (反向映射，用于查找调用参数)
            reverse_param_map = {}  # call_arg_name -> def_param_name
            for def_param_name, call_arg_name in param_map.items():
                reverse_param_map[call_arg_name] = def_param_name
            
            if is_function and internal_drivers:
                # 函数返回值的驱动源可能是拼接表达式或二元表达式
                # 例如: gray_conv = {a[7], a[6:0] ^ a[7:1]}
                # internal_drivers['gray_conv'] = ['{a[7], a[6:0] ^ a[7:1]}']
                func_name = self.adapter.get_function_name(task_def)
                if func_name in internal_drivers and lhs_name:
                    # [NEW] 直接从函数体提取 RHS AST，而不是用字符串
                    # 遍历函数的 items 找到函数名赋值语句
                    rhs_ast = None
                    for item in getattr(task_def, 'items', []):
                        kind = str(getattr(item, 'kind', ''))
                        # SequentialBlock
                        if 'SequentialBlock' in kind:
                            for attr in ['items', 'statements', 'body']:
                                block_items = getattr(item, attr, None)
                                if block_items and hasattr(block_items, '__iter__'):
                                    for bi in block_items:
                                        rhs_ast = self._find_func_assignment_rhs(bi, func_name)
                                        if rhs_ast:
                                            break
                        # 直接是 ExpressionStatement
                        elif 'ExpressionStatement' in kind:
                            rhs_ast = self._find_func_assignment_rhs(item, func_name)
                            if rhs_ast:
                                break
                        if rhs_ast:
                            break
                    
                    if rhs_ast:
                        # 用 _get_all_signals 提取所有信号
                        all_signals = self._get_all_signals(rhs_ast)
                        for sig in all_signals:
                            if not sig or sig.startswith('{') or not sig[0].isalpha():
                                continue
                            # Map signal to call_arg
                            base_sig = sig.split('[')[0] if '[' in sig else sig
                            call_arg = param_map.get(base_sig)
                            if call_arg and lhs_name:
                                src_node_id = f"{module_name}.{call_arg}"
                                dst_node_id = f"{module_name}.{lhs_name}"
                                
                                if src_node_id not in [n.id for n in result.nodes]:
                                    result.nodes.append(TraceNode(
                                        id=src_node_id, name=call_arg, module=module_name,
                                        kind=NodeKind.SIGNAL, width=(1, 0)
                                    ))
                                if dst_node_id not in [n.id for n in result.nodes]:
                                    result.nodes.append(TraceNode(
                                        id=dst_node_id, name=lhs_name, module=module_name,
                                        kind=NodeKind.SIGNAL, width=(1, 0)
                                    ))
                                
                                result.edges.append(TraceEdge(
                                    src=src_node_id, dst=dst_node_id,
                                    kind=EdgeKind.DRIVER, assign_type="continuous",
                                    clock_domain=ctx.get("clock", ""),
                                    condition=ctx.get("condition", "")
                                ))
                        
                        # [FIX] For function calls, also create edge from function return value to lhs_name
                        # Function return value is the function name itself (implicit in SystemVerilog)
                        # e.g., assign out = gray_conv(in); should have: gray_conv -> out
                        if is_function and lhs_name:
                            func_return_id = f"{module_name}.{func_name}"
                            dst_id = f"{module_name}.{lhs_name}"
                            if func_return_id != dst_id:  # Avoid self-loop
                                if func_return_id not in [n.id for n in result.nodes]:
                                    result.nodes.append(TraceNode(
                                        id=func_return_id, name=func_name, module=module_name,
                                        kind=NodeKind.SIGNAL, width=(1, 0)
                                    ))
                                if dst_id not in [n.id for n in result.nodes]:
                                    result.nodes.append(TraceNode(
                                        id=dst_id, name=lhs_name, module=module_name,
                                        kind=NodeKind.SIGNAL, width=(1, 0)
                                    ))
                                result.edges.append(TraceEdge(
                                    src=func_return_id, dst=dst_id,
                                    kind=EdgeKind.DRIVER, assign_type="continuous",
                                    clock_domain=ctx.get("clock", ""),
                                    condition=ctx.get("condition", "")
                                ))
                    else:
                        # 兜底: 使用字符串方式
                        rhs_exprs = internal_drivers[func_name]
                        for rhs_expr in rhs_exprs:
                            if not rhs_expr.startswith('{'):
                                base_signal = rhs_expr.split('[')[0] if '[' in rhs_expr else rhs_expr
                                call_arg_name = param_map.get(base_signal)
                                if call_arg_name and lhs_name:
                                    src_node_id = f"{module_name}.{call_arg_name}"
                                    dst_node_id = f"{module_name}.{lhs_name}"
                                    
                                    if src_node_id not in [n.id for n in result.nodes]:
                                        result.nodes.append(TraceNode(
                                            id=src_node_id, name=call_arg_name, module=module_name,
                                            kind=NodeKind.SIGNAL, width=(1, 0)
                                        ))
                                    if dst_node_id not in [n.id for n in result.nodes]:
                                        result.nodes.append(TraceNode(
                                            id=dst_node_id, name=lhs_name, module=module_name,
                                            kind=NodeKind.SIGNAL, width=(1, 0)
                                        ))
                                    
                                    result.edges.append(TraceEdge(
                                        src=src_node_id, dst=dst_node_id,
                                        kind=EdgeKind.DRIVER, assign_type="continuous",
                                        clock_domain=ctx.get("clock", ""),
                                        condition=ctx.get("condition", "")
                                    ))
            
            # 对于每个 output 参数,如果它被赋值,建立驱动边
            for direction, param_name in def_params:
                if direction == 'output' and param_name in internal_drivers:
                    # output 参数被赋值
                    rhs_sources = internal_drivers[param_name]
                    for rhs_src in rhs_sources:
                        # 跳过字面量(如数字常量),只处理信号
                        # rhs_src 是内部变量,找到它映射到哪个调用参数
                        # [NEW] 剥离位选择后缀:v[i] -> v, data[3] -> data
                        base_signal = rhs_src.split('[')[0] if '[' in rhs_src else rhs_src
                        rhs_call_arg = param_map.get(base_signal)
                        if not rhs_call_arg:
                            continue
                        # 跳过数字字面量(简单判断:如果 rhs_src 是纯数字)
                        if rhs_src.isdigit():
                            continue
                        # 跳过 task 参数的自环 (r = r | ...)
                        # 如果 rhs_call_arg 等于目标 output 参数本身,则是自环
                        if rhs_call_arg == param_map.get(param_name):
                            continue  # 跳过 output 参数到自身的驱动

                        # 建立边: rhs_call_arg -> param_map[param_name] (output 参数)
                        src_node_id = f"{module_name}.{rhs_call_arg}"
                        dst_node_id = f"{module_name}.{param_map[param_name]}"

                        # 确保节点存在
                        if src_node_id not in [n.id for n in result.nodes]:
                            result.nodes.append(TraceNode(
                                id=src_node_id, name=rhs_call_arg, module=module_name,
                                kind=NodeKind.SIGNAL, width=(1, 0)
                            ))
                        if dst_node_id not in [n.id for n in result.nodes]:
                            result.nodes.append(TraceNode(
                                id=dst_node_id, name=param_map[param_name], module=module_name,
                                kind=NodeKind.REG, width=(1, 0)
                            ))

                        result.edges.append(TraceEdge(
                            src=src_node_id, dst=dst_node_id,
                            kind=EdgeKind.DRIVER, assign_type="nonblocking",
                            clock_domain=ctx.get("clock", ""),
                            condition=ctx.get("condition", "")
                        ))
        except Exception as e:
            # 忽略处理错误,继续
            pass

    def _get_all_signals(self, signal) -> List[str]:
        """提取表达式中的所有信号名(三元、拼接等返回多个)"""
        if signal is None:
            return []

        kind = getattr(signal, 'kind', None)
        kind_str = str(kind) if kind else ''

        # 三元运算符: sel ? a : b → [sel, a, b]
        if 'ConditionalExpression' in kind_str:
            signals = []
            # predicate (condition)
            pred = getattr(signal, 'predicate', None)
            if pred:
                signals.extend(self._get_all_signals(pred))
            # left (true branch)
            left = getattr(signal, 'left', None)
            if left:
                signals.extend(self._get_all_signals(left))
            # right (false branch)
            right = getattr(signal, 'right', None)
            if right:
                signals.extend(self._get_all_signals(right))
            return [s for s in signals if s]

        # [FIX] 处理 ParenthesizedExpression: (expr) → 展开内部表达式
        if 'ParenthesizedExpression' in kind_str:
            expr = getattr(signal, 'expression', None)
            if expr:
                return self._get_all_signals(expr)
            return []

        # ConditionalPredicate → 递归进入 conditions
        if 'ConditionalPredicate' in kind_str or 'ConditionalPattern' in kind_str:
            signals = []
            # conditions 是一个 SeparatedList，需要迭代提取
            conditions = getattr(signal, 'conditions', None)
            if conditions:
                # SeparatedList 是容器，需要迭代
                if hasattr(conditions, '__iter__') and not isinstance(conditions, str):
                    for item in conditions:
                        item_kind = getattr(item, 'kind', None)
                        # 跳过 Token 和 SyntaxList
                        if item_kind and 'Token' not in str(item_kind) and 'SyntaxList' not in str(item_kind):
                            signals.extend(self._get_all_signals(item))
                else:
                    signals.extend(self._get_all_signals(conditions))
            return [s for s in signals if s]

        # TimingControlExpression: a = repeat(3) @(posedge clk) b;
        # 实际 RHS 是 expr 属性
        if 'TimingControlExpression' in kind_str:
            tc_expr = getattr(signal, 'expr', None)
            if tc_expr:
                return self._get_all_signals(tc_expr)
            return []

        # 拼接: {a, b, c} → [a, b, c]
        if 'Concatenation' in kind_str and 'Multiple' not in kind_str:
            signals = []
            if hasattr(signal, 'expressions'):
                for expr in signal.expressions:
                    expr_kind = getattr(expr, 'kind', None)
                    if expr_kind and 'Token' not in str(expr_kind):
                        signals.extend(self._get_all_signals(expr))
            return [s for s in signals if s]

        # 二元表达式: a + b, a ^ b, a == b, a < b 等 → 递归提取两边
        # 使用 hasattr 检查而非 'Binary' in kind_str
        # 因为 EqualityExpression, AddExpression 等不包含 "Binary" 关键词
        if hasattr(signal, 'left') and hasattr(signal, 'right'):
            signals = []
            left = getattr(signal, 'left', None)
            if left:
                signals.extend(self._get_all_signals(left))
            right = getattr(signal, 'right', None)
            if right:
                signals.extend(self._get_all_signals(right))
            return [s for s in signals if s]

        # 默认: 单个信号
        name = self._get_signal(signal)
        return [name] if name else []

    def _get_signal(self, signal) -> Optional[str]:
        if signal is None:
            return None

        # [FIX BUG] ScopedName: Recursively handle nested ScopedNames (p.sub.data is ScopedName(ScopedName(p, sub), data))
        # In special_attrs loop to extract left.identifier.value + '.' + right.identifier.value
        if hasattr(signal, 'kind') and str(signal.kind) == 'SyntaxKind.ScopedName':
            def _get_scoped_parts(node, parts=None):
                if parts is None:
                    parts = []
                kind = getattr(node, 'kind', None)
                if not kind:
                    return parts
                kind_str = str(kind)
                if 'ScopedName' in kind_str:
                    left = getattr(node, 'left', None)
                    if left:
                        _get_scoped_parts(left, parts)
                    right = getattr(node, 'right', None)
                    if right:
                        ri = getattr(right, 'identifier', None)
                        if ri:
                            rv = getattr(ri, 'value', None)
                            if rv:
                                parts.append(str(rv).strip())
                elif 'IdentifierName' in kind_str:
                    ident = getattr(node, 'identifier', None)
                    if ident:
                        val = getattr(ident, 'value', None)
                        if val:
                            parts.append(str(val).strip())
                return parts

            parts = _get_scoped_parts(signal)
            if len(parts) >= 2:
                combined = '.'.join(parts)
                return self.adapter.clean_name(combined)

        # [FIX] IntegerVectorExpression 字面量: 8'hAA, 16'd123, etc.
        # → 返回完整字面量字符串 (str(signal)),不拼接 top.
        if hasattr(signal, 'kind') and 'IntegerVector' in str(signal.kind):
            val = getattr(signal, 'value', None)
            if isinstance(val, pyslang.Token) and val.kind == pyslang.TokenKind.IntegerLiteral:
                # 关键修复: 使用 str(signal) 获取完整字面量 (如 "8'hAA"),
                # 而不是 str(val) (只有 "AA")
                return str(signal).strip()

        # [FIX] IntegerLiteralExpression 处理: 8b0, 4'b1000 等简单字面量
        # SyntaxKind.IntegerLiteralExpression 直接返回 str(signal)
        if hasattr(signal, 'kind') and 'IntegerLiteralExpression' in str(signal.kind):
            return str(signal).strip()

        # [FIX] IntegerLiteral Token 直接处理: 8b0, 4'b1000 等
        # 注意: 这些是 Token 类型,不是 SyntaxKind,所以用 isinstance 检查
        if isinstance(signal, pyslang.Token) and signal.kind == pyslang.TokenKind.IntegerLiteral:
            # 返回完整 token 字符串 (如 "8b0" 或 "4'b1000")
            return str(signal).strip()

        # [FIX] TimingControlExpression: a = repeat(3) @(posedge clk) b;
        # _get_signal 被直接调用时处理,否则 _get_all_signals 已处理
        kind = getattr(signal, 'kind', None)
        if kind and 'TimingControlExpression' in str(kind):
            tc_expr = getattr(signal, 'expr', None)
            if tc_expr:
                return self._get_signal(tc_expr)
            return None

        # [FIX BUG] MultipleConcatenationExpression: {N{signal}} → 返回内部信号
        # 结构: signal.concatenation.expressions,内部是 {signal} 拼接
        if hasattr(signal, 'kind') and 'MultipleConcatenation' in str(signal.kind):
            if hasattr(signal, 'concatenation'):
                concat = signal.concatenation
                if concat and hasattr(concat, 'expressions'):
                    exprs = concat.expressions
                    # exprs 是内部拼接表达式,迭代提取第一个信号
                    if hasattr(exprs, '__iter__') and not isinstance(exprs, str):
                        for expr_item in exprs:
                            if hasattr(expr_item, 'kind'):
                                result = self._get_signal(expr_item)
                                if result:
                                    return result
                    else:
                        result = self._get_signal(exprs)
                        if result:
                            return result
            return None

        # [NEW] 处理 IdentifierSelectName: data[3] → 保留完整名 data[3]
        # 位选择信息在 build() 中处理为父子节点
        kind = getattr(signal, 'kind', None)
        if kind and 'IdentifierSelect' in str(kind):
            # 提取基础信号名
            base_name = None
            if hasattr(signal, 'identifier'):
                ident = signal.identifier
                if hasattr(ident, 'value'):
                    base_name = str(ident.value).strip()
                else:
                    base_name = str(ident).strip()
            if not base_name:
                base_name = str(signal).strip().split('[')[0]
            
            # 获取位选择索引，可能包含参数表达式
            selectors = getattr(signal, 'selectors', None)
            if selectors and hasattr(selectors, '__iter__'):
                for i in range(len(selectors)):
                    sel = selectors[i]
                    sel_kind = str(getattr(sel, 'kind', ''))
                    if 'ElementSelect' in sel_kind:
                        # ElementSelect.selector can be:
                        # - BitSelectSyntax (e.g., in[3]) → has .expr attribute
                        # - SimpleRangeSelectSyntax (e.g., in[3:2]) → has .left/.right attributes
                        bit_select = getattr(sel, 'selector', None)
                        if bit_select:
                            bit_select_kind = str(getattr(bit_select, 'kind', ''))
                            
                            if 'SimpleRange' in bit_select_kind:
                                # SimpleRangeSelect: in[ADDR_WIDTH-2:0] format
                                left_expr = getattr(bit_select, 'left', None)
                                right_expr = getattr(bit_select, 'right', None)
                                
                                if left_expr or right_expr:
                                    param_map = {}
                                    try:
                                        params = self.adapter.get_module_parameters(self._current_module)
                                        for p in params:
                                            name = p.get('name')
                                            value = p.get('value')
                                            if name and value is not None:
                                                try:
                                                    param_map[name] = int(value)
                                                except (ValueError, TypeError):
                                                    pass
                                    except:
                                        pass
                                    
                                    left_val = self.adapter._evaluate_expression(left_expr, param_map) if left_expr else None
                                    right_val = self.adapter._evaluate_expression(right_expr, param_map) if right_expr else None
                                    
                                    if left_val is not None or right_val is not None:
                                        left_str = str(left_val) if left_val is not None else '?'
                                        right_str = str(right_val) if right_val is not None else '?'
                                        return self.adapter.clean_name(f"{base_name}[{left_str}:{right_str}]")
                            else:
                                # BitSelect: has .expr attribute
                                selector_expr = getattr(bit_select, 'expr', None)
                                if selector_expr:
                                    # 尝试解析参数表达式
                                    param_map = {}
                                    try:
                                        params = self.adapter.get_module_parameters(self._current_module)
                                        for p in params:
                                            name = p.get('name')
                                            value = p.get('value')
                                            if name and value is not None:
                                                try:
                                                    param_map[name] = int(value)
                                                except (ValueError, TypeError):
                                                    pass
                                    except:
                                        pass
                                    
                                    # 评估索引表达式
                                    evaluated = self.adapter._evaluate_expression(selector_expr, param_map)
                                    if evaluated is not None:
                                        return self.adapter.clean_name(f"{base_name}[{evaluated}]")
                    elif 'SimpleRangeSelect' in sel_kind:
                        # SimpleRangeSelect: in[ADDR_WIDTH-2:0] 格式
                        # 结构: range.left 和 range.right (都是表达式)
                        range_sel = getattr(sel, 'selector', None) or sel
                        left_expr = getattr(range_sel, 'left', None)
                        right_expr = getattr(range_sel, 'right', None)
                        
                        if left_expr or right_expr:
                            # 尝试解析参数表达式
                            param_map = {}
                            try:
                                params = self.adapter.get_module_parameters(self._current_module)
                                for p in params:
                                    name = p.get('name')
                                    value = p.get('value')
                                    if name and value is not None:
                                        try:
                                            param_map[name] = int(value)
                                        except (ValueError, TypeError):
                                            pass
                            except:
                                pass
                            
                            # 评估左右边界
                            left_val = self.adapter._evaluate_expression(left_expr, param_map) if left_expr else None
                            right_val = self.adapter._evaluate_expression(right_expr, param_map) if right_expr else None
                            
                            if left_val is not None or right_val is not None:
                                left_str = str(left_val) if left_val is not None else '?'
                                right_str = str(right_val) if right_val is not None else '?'
                                return self.adapter.clean_name(f"{base_name}[{left_str}:{right_str}]")
            
            # Fallback: 返回原始字符串（已清理）
            name = str(signal).strip()
            name = self.adapter.clean_name(name) if name else None
            if name:
                return name

        # [FIX] IdentifierName: 必须提取 identifier.value，禁止 fallback
        # IdentifierName 有 identifier 属性，value 在 identifier.value 中
        # str(signal) 会包含 leading trivia (注释、换行)，所以必须显式提取
        if kind and 'IdentifierName' in str(kind):
            ident = getattr(signal, 'identifier', None)
            if ident is None:
                raise ValueError(
                    f"[铁律3] IdentifierName missing 'identifier' attribute. "
                    f"signal={signal}, kind={kind}"
                )
            val = getattr(ident, 'value', None)
            if val is None:
                raise ValueError(
                    f"[铁律3] IdentifierName.identifier missing 'value' attribute. "
                    f"signal={signal}, kind={kind}"
                )
            return self.adapter.clean_name(str(val).strip())

        # [FIX] 处理 ParenthesizedExpression: (expr) → 递归提取内部表达式
        if kind and 'ParenthesizedExpression' in str(kind):
            expr = getattr(signal, 'expression', None)
            if expr:
                return self._get_signal(expr)
            return None
        
        # [兜底] 如果走到这里，说明遇到了未处理的节点类型
        # 递归处理复合表达式（与 _get_all_signals 互补）
        # 这样 _parse_assign 可以对 BinaryExpression 等调用 _get_signal
        
        # 二元表达式: a + b, a & b, a == b, a < b 等 → 递归提取左边
        # 使用 hasattr 检查而非 'Binary' 关键词
        # 因为 EqualityExpression, AddExpression 等不包含 "Binary" 关键词
        if hasattr(signal, 'left') and hasattr(signal, 'right'):
            left = getattr(signal, 'left', None)
            if left:
                return self._get_signal(left)
            return None
        
        # 三元表达式: sel ? a : b → 递归提取条件
        if kind and 'Conditional' in str(kind):
            pred = getattr(signal, 'predicate', None)
            if pred:
                return self._get_signal(pred)
            return None
        
        # 拼接表达式: {a, b, c} → 递归提取第一个
        if kind and 'Concatenation' in str(kind):
            if hasattr(signal, 'expressions'):
                exprs = signal.expressions
                if hasattr(exprs, '__iter__') and not isinstance(exprs, str):
                    for expr in exprs:
                        if hasattr(expr, 'kind') and 'Token' not in str(getattr(expr, 'kind', '')):
                            result = self._get_signal(expr)
                            if result:
                                return result
            return None
        
        # 一元表达式: ~a, -a 等 → 递归提取 operand
        if kind and ('Unary' in str(kind) or 'NegateExpression' in str(kind)):
            operand = getattr(signal, 'operand', None) or getattr(signal, 'expression', None)
            if operand:
                return self._get_signal(operand)
            return None
        
        # [NEW] SimplePropertyExpr: gray_conv(in) 中的参数 in
        # 结构: SimplePropertyExpr.expr = SimpleSequenceExpr (实际信号名)
        if kind and 'SimplePropertyExpr' in str(kind):
            expr = getattr(signal, 'expr', None)
            if expr:
                return self._get_signal(expr)
            return None
        
        # [NEW] SimpleSequenceExpr: gray_conv(in) 中 in 的实际类型
        # 结构: SimpleSequenceExpr.expr = IdentifierName
        if kind and 'SimpleSequenceExpr' in str(kind):
            expr = getattr(signal, 'expr', None)
            if expr:
                return self._get_signal(expr)
            return None
        
        # 强制报错而非静默 fallback（铁律3）
        raise ValueError(
            f"[铁律3] Unsupported signal type in _get_signal: "
            f"kind={kind}, signal={signal}"
        )

        # [P2增强] 递归提取复合表达式的操作数
        # 处理三元、拼接、一元、移位等复杂运算符
        special_attrs = ['left', 'right', 'operand', 'ifTrue', 'ifFalse',
                       'target', 'increment', 'left', 'right']
        for attr in special_attrs:
            if hasattr(signal, attr):
                try:
                    child = getattr(signal, attr)
                    if child and not callable(child):
                        result = self._get_signal(child)
                        if result:
                            return result
                except:
                    pass

        # [P0 Fix] 复合表达式处理
        if name:
            # 处理 & | + - 等运算符
            return self.adapter.clean_name(name) if name else None

        # [兜底] 如果走到这里，说明遇到了未处理的节点类型
        # 根据铁律3，必须报错而非静默 fallback
        raise ValueError(
            f"[铁律3] Unsupported signal type in _get_signal: "
            f"kind={kind}, signal={signal}"
        )

        # [P2增强] 递归提取复合表达式的操作数
        # 处理三元、拼接、一元、移位等复杂运算符
        special_attrs = ['left', 'right', 'operand', 'ifTrue', 'ifFalse',
                       'target', 'increment', 'left', 'right']
        for attr in special_attrs:
            if hasattr(signal, attr):
                try:
                    child = getattr(signal, attr)
                    if child and not callable(child):
                        result = self._get_signal(child)
                        if result:
                            return result
                except:
                    pass

        # [P0 Fix] 复合表达式处理
        if name:
            # 处理 & | + - 等运算符
            has_binary_op = any(op in name for op in ['&', '|', '+', '-', '^', '<<', '>>'])
            if has_binary_op and hasattr(signal, 'left') and hasattr(signal, 'right'):
                left_name = self._get_signal(signal.left)
                if left_name:
                    return left_name
                right_name = self._get_signal(signal.right)
                if right_name:
                    return right_name
                return None

        # [P1增强] 处理拼接: {a,b} -> 提取所有 values
        if hasattr(signal, 'kind'):
            kind_str = str(signal.kind)
            if 'Replication' in kind_str or 'Concat' in kind_str:
                # 使用 expressions 或 values 列表构建返回
                items = None
                if hasattr(signal, 'expressions'):
                    items = signal.expressions
                elif hasattr(signal, 'values'):
                    items = signal.values
                if items:
                    all_names = []
                    for v in items:
                        v_kind = getattr(v, 'kind', None)
                        if v_kind and 'Token' in str(v_kind):
                            continue
                        vn = self._get_signal(v)
                        if vn: all_names.append(vn)
                    if all_names:
                        # 返回第一个 (主driver)
                        return all_names[0]


        # [P2] Clean 特殊语法格式: {a,b} -> a
        if name and name.startswith("{") and name.endswith("}"):
            # 提取内部第一个标识符
            inner = name[1:-1].strip()  # 去掉 {}
            first = inner.split(",")[0].strip().split()[-1]  # 取第一个
            if first:
                return first

        return name

class LoadExtractor:
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
                    if 'inout' in direction.lower():
                        kind = NodeKind.PORT_INOUT
                    elif 'output' in direction.lower():
                        kind = NodeKind.PORT_OUT
                    else:
                        kind = NodeKind.PORT_IN
                    # 提取端口位宽 (传入 module 作为 scope 以解析参数)
                    port_width = self.adapter.extract_port_width(port_decl, scope=module)
                    # convert dict to tuple for compatibility
                    if isinstance(port_width, dict):
                        msb = port_width.get('msb_eval', port_width.get('msb_raw', 0))
                        lsb = port_width.get('lsb_eval', port_width.get('lsb_raw', 0))
                        try:
                            msb = int(msb) if msb is not None else 0
                        except (ValueError, TypeError):
                            msb = 0
                        try:
                            lsb = int(lsb) if lsb is not None else 0
                        except (ValueError, TypeError):
                            lsb = 0
                        port_width = (msb, lsb)
                    result.nodes.append(TraceNode(
                        id=port_id,
                        name=port_name,
                        module=module_name,
                        kind=kind,
                        width=port_width,
                        is_port=True
                    ))

            # [P0-3] Build interface port map for this module
            interface_ports = {}  # port_name -> (interface_name, modport_name)
            try:
                if hasattr(module, 'header') and module.header:
                    header = module.header
                    if hasattr(header, 'ports') and hasattr(header.ports, 'ports'):
                        for item in header.ports.ports:
                            if not hasattr(item, 'kind') or item.kind != pyslang.SyntaxKind.ImplicitAnsiPort:
                                continue
                            try:
                                h = getattr(item, 'header', None)
                                decl = getattr(item, 'declarator', None)
                            except AttributeError:
                                continue
                            if h is None or decl is None:
                                continue
                            if hasattr(h, 'kind') and 'InterfacePortHeader' in str(h.kind):
                                port_name = decl.name.value if hasattr(decl.name, 'value') else str(decl.name)
                                interface_name = None
                                if hasattr(h, 'nameOrKeyword'):
                                    nk = h.nameOrKeyword
                                    interface_name = nk.rawText if hasattr(nk, 'rawText') else str(nk)
                                modport_name = None
                                if hasattr(h, 'modport') and hasattr(h.modport, 'member'):
                                    member_val = h.modport.member
                                    modport_name = member_val.name if hasattr(member_val, 'name') else str(member_val)
                                if port_name and interface_name:
                                    interface_ports[port_name.strip()] = (interface_name, modport_name)
                            elif hasattr(h, 'kind') and 'VariablePortHeader' in str(h.kind):
                                port_name = decl.name.value if hasattr(decl.name, 'value') else str(decl.name)
            except (ValueError, AttributeError, TypeError):
                pass

        return result

    def _parse_assign(self, assign) -> tuple:
        """
        解析赋值语句，返回 (lhs_name, rhs_name, rhs_expr)
        - lhs_name: 左操作数信号名
        - rhs_name: 右操作数信号名 (简单信号，用于简单赋值)
        - rhs_expr: 原始 RHS 表达式 (用于复杂类型判断和_get_all_signals)
        """
        # [铁律2] 支持所有赋值语法结构
        try:
            # [P2] 支持 ContinuousAssign 嵌套结构: assign.assignments[0]
            if hasattr(assign, 'assignments') and assign.assignments:
                a = assign.assignments[0]
                lhs = a.left if hasattr(a, 'left') else None
                rhs = a.right if hasattr(a, 'right') else None
            elif hasattr(assign, 'left') and hasattr(assign, 'right'):
                # NonblockingAssignmentExpression / BlockingAssignmentExpression
                lhs = getattr(assign, 'left', None)
                rhs = getattr(assign, 'right', None)
            else:
                # 兜底: 直接尝试 lhs/rhs
                lhs = getattr(assign, 'lhs', None)
                rhs = getattr(assign, 'rhs', None)

            lhs_name = self._get_signal(lhs)
            rhs_name = self._get_signal(rhs)

            return lhs_name, rhs_name, rhs
        except:
            return None, None, None

    def _get_signal(self, signal) -> Optional[str]:
        if signal is None:
            return None

        # [FIX] TimingControlExpression: a = repeat(3) @(posedge clk) b;
        # _get_signal 被直接调用时处理,否则 _get_all_signals 已处理
        kind = getattr(signal, 'kind', None)
        if kind and 'TimingControlExpression' in str(kind):
            tc_expr = getattr(signal, 'expr', None)
            if tc_expr:
                return self._get_signal(tc_expr)
            return None

        # [P0 Fix] 处理 MultipleConcatenationExpression: {N{signal}}
        # MultipleConcatenationExpressionSyntax has 'concatenation' attribute, not 'values'
        # This must be checked BEFORE the Replication/Concat block
        if hasattr(signal, 'kind') and 'MultipleConcatenation' in str(signal.kind):
            if hasattr(signal, 'concatenation'):
                concat = signal.concatenation
                if concat and hasattr(concat, 'expressions'):
                    exprs = concat.expressions
                    # exprs is the internal concatenation like {a}, need to iterate
                    if hasattr(exprs, '__iter__') and not isinstance(exprs, str):
                        for expr_item in exprs:
                            if hasattr(expr_item, 'kind'):
                                result = self._get_signal(expr_item)
                                if result:
                                    return result
                    else:
                        result = self._get_signal(exprs)
                        if result:
                            return result
            return None

        # [FIX] 处理 ParenthesizedExpression: (expr) → 展开内部表达式
        kind = getattr(signal, 'kind', None)
        if kind and 'ParenthesizedExpression' in str(kind):
            expr = getattr(signal, 'expression', None)
            if expr:
                return self._get_signal(expr)
            return None

        # [FIX] 处理 ConditionalExpression (三元运算符 sel ? a : b)
        # 递归提取第一个操作数(与 _get_all_signals 互补)
        if kind and 'ConditionalExpression' in str(kind):
            pred = getattr(signal, 'predicate', None)
            if pred:
                result = self._get_signal(pred)
                if result:
                    return result
            left = getattr(signal, 'left', None)
            if left:
                result = self._get_signal(left)
                if result:
                    return result
            right = getattr(signal, 'right', None)
            if right:
                result = self._get_signal(right)
                if result:
                    return result
            return None

        # [P0] 检测字面量常量: IntegerVectorExpression + IntegerLiteral Token
        # → 返回字面量字符串(不拼接 top.),让边创建继续但节点跳过
        if hasattr(signal, 'kind') and 'IntegerVector' in str(signal.kind):
            val = getattr(signal, 'value', None)
            if isinstance(val, pyslang.Token) and val.kind == pyslang.TokenKind.IntegerLiteral:
                return str(val).strip()

        # [P2] 处理 Replication: {N{signal}} -> 递归获取 values
        if hasattr(signal, 'kind') and 'Replication' in str(signal.kind):
            if hasattr(signal, 'values'):
                vals = signal.values
                if vals and len(vals) > 0:
                    first_val = vals[0]
                    # 递归调用获取内部信号名
                    return self._get_signal(first_val)
            return None

        # [FIX] IdentifierSelectName: data[3] → 保留完整名
        # 在 IdentifierName 之前处理，因为 IdentifierSelect 包含 IdentifierName
        if kind and 'IdentifierSelect' in str(kind):
            # 提取基础信号名
            base_name = None
            if hasattr(signal, 'identifier'):
                ident = signal.identifier
                if hasattr(ident, 'value'):
                    base_name = str(ident.value).strip()
                else:
                    base_name = str(ident).strip()
            if not base_name:
                base_name = str(signal).strip().split('[')[0]
            
            # 获取位选择索引，可能包含参数表达式
            selectors = getattr(signal, 'selectors', None)
            if selectors and hasattr(selectors, '__iter__'):
                for i in range(len(selectors)):
                    sel = selectors[i]
                    sel_kind = str(getattr(sel, 'kind', ''))
                    # ElementSelect: selector.selector is BitSelectSyntax, BitSelectSyntax.expr is the actual expression
                    if 'ElementSelect' in sel_kind:
                        # ElementSelect.selector can be:
                        # - BitSelectSyntax (e.g., in[3]) → has .expr attribute
                        # - SimpleRangeSelectSyntax (e.g., in[3:2]) → has .left/.right attributes
                        bit_select = getattr(sel, 'selector', None)
                        if bit_select:
                            bit_select_kind = str(getattr(bit_select, 'kind', ''))
                            
                            if 'SimpleRange' in bit_select_kind:
                                # SimpleRangeSelect: in[ADDR_WIDTH-2:0] format
                                left_expr = getattr(bit_select, 'left', None)
                                right_expr = getattr(bit_select, 'right', None)
                                
                                if left_expr or right_expr:
                                    param_map = {}
                                    try:
                                        params = self.adapter.get_module_parameters(self._current_module)
                                        for p in params:
                                            name = p.get('name')
                                            value = p.get('value')
                                            if name and value is not None:
                                                try:
                                                    param_map[name] = int(value)
                                                except (ValueError, TypeError):
                                                    pass
                                    except:
                                        pass
                                    
                                    left_val = self.adapter._evaluate_expression(left_expr, param_map) if left_expr else None
                                    right_val = self.adapter._evaluate_expression(right_expr, param_map) if right_expr else None
                                    
                                    if left_val is not None or right_val is not None:
                                        left_str = str(left_val) if left_val is not None else '?'
                                        right_str = str(right_val) if right_val is not None else '?'
                                        return self.adapter.clean_name(f"{base_name}[{left_str}:{right_str}]")
                            else:
                                # BitSelect: has .expr attribute
                                selector_expr = getattr(bit_select, 'expr', None)
                                if selector_expr:
                                    try:
                                        params = self.adapter.get_module_parameters(self._current_module)
                                        for p in params:
                                            name = p.get('name')
                                            value = p.get('value')
                                            if name and value is not None:
                                                try:
                                                    param_map[name] = int(value)
                                                except (ValueError, TypeError):
                                                    pass
                                    except:
                                        pass
                                    
                                    evaluated = self.adapter._evaluate_expression(selector_expr, param_map)
                                    if evaluated is not None:
                                        return self.adapter.clean_name(f"{base_name}[{evaluated}]")
                    if 'SimpleRangeSelect' in sel_kind:
                        # SimpleRangeSelect: standalone in[ADDR_WIDTH-2:0] format
                        range_sel = getattr(sel, 'selector', None) or sel
                        left_expr = getattr(range_sel, 'left', None)
                        right_expr = getattr(range_sel, 'right', None)
                        
                        if left_expr or right_expr:
                            param_map = {}
                            try:
                                params = self.adapter.get_module_parameters(self._current_module)
                                for p in params:
                                    name = p.get('name')
                                    value = p.get('value')
                                    if name and value is not None:
                                        try:
                                            param_map[name] = int(value)
                                        except (ValueError, TypeError):
                                            pass
                            except:
                                pass
                            
                            left_val = self.adapter._evaluate_expression(left_expr, param_map) if left_expr else None
                            right_val = self.adapter._evaluate_expression(right_expr, param_map) if right_expr else None
                            
                            if left_val is not None or right_val is not None:
                                left_str = str(left_val) if left_val is not None else '?'
                                right_str = str(right_val) if right_val is not None else '?'
                                return self.adapter.clean_name(f"{base_name}[{left_str}:{right_str}]")
            
            # Fallback: 返回原始字符串（已清理）
            name = str(signal).strip()
            return self.adapter.clean_name(name) if name else None

        # [FIX] IdentifierName: 必须提取 identifier.value，禁止 fallback
        # IdentifierName 有 identifier 属性，value 在 identifier.value 中
        # str(signal) 会包含 leading trivia (注释、换行)，所以必须显式提取
        if kind and 'IdentifierName' in str(kind):
            ident = getattr(signal, 'identifier', None)
            if ident is None:
                raise ValueError(
                    f"[铁律3] IdentifierName missing 'identifier' attribute. "
                    f"signal={signal}, kind={kind}"
                )
            val = getattr(ident, 'value', None)
            if val is None:
                raise ValueError(
                    f"[铁律3] IdentifierName.identifier missing 'value' attribute. "
                    f"signal={signal}, kind={kind}"
                )
            return self.adapter.clean_name(str(val).strip())

        # [兜底] 如果走到这里，说明遇到了未处理的节点类型
        # 递归处理复合表达式（与 _get_all_signals 互补）
        
        # 二元表达式: a + b, a & b, a == b, a < b 等 → 递归提取左边
        # 使用 hasattr 检查而非 'Binary' 关键词
        if hasattr(signal, 'left') and hasattr(signal, 'right'):
            left = getattr(signal, 'left', None)
            if left:
                return self._get_signal(left)
            return None
        
        # 三元表达式: sel ? a : b → 递归提取条件
        if kind and 'Conditional' in str(kind):
            pred = getattr(signal, 'predicate', None)
            if pred:
                return self._get_signal(pred)
            return None
        
        # 拼接表达式: {a, b, c} → 递归提取第一个
        if kind and 'Concatenation' in str(kind):
            if hasattr(signal, 'expressions'):
                exprs = signal.expressions
                if hasattr(exprs, '__iter__') and not isinstance(exprs, str):
                    for expr in exprs:
                        if hasattr(expr, 'kind') and 'Token' not in str(getattr(expr, 'kind', '')):
                            result = self._get_signal(expr)
                            if result:
                                return result
            return None
        
        # 一元表达式: ~a, -a 等 → 递归提取 operand
        if kind and ('Unary' in str(kind) or 'NegateExpression' in str(kind)):
            operand = getattr(signal, 'operand', None) or getattr(signal, 'expression', None)
            if operand:
                return self._get_signal(operand)
            return None
        
        # [NEW] SimplePropertyExpr: gray_conv(in) 中的参数 in
        # 结构: SimplePropertyExpr.expr = SimpleSequenceExpr (实际信号名)
        if kind and 'SimplePropertyExpr' in str(kind):
            expr = getattr(signal, 'expr', None)
            if expr:
                return self._get_signal(expr)
            return None
        
        # [NEW] SimpleSequenceExpr: gray_conv(in) 中 in 的实际类型
        # 结构: SimpleSequenceExpr.expr = IdentifierName
        if kind and 'SimpleSequenceExpr' in str(kind):
            expr = getattr(signal, 'expr', None)
            if expr:
                return self._get_signal(expr)
            return None
        
        # 强制报错而非静默 fallback（铁律3）
        raise ValueError(
            f"[铁律3] Unsupported signal type in _get_signal: "
            f"kind={kind}, signal={signal}"
        )

        name = None
        if hasattr(signal, 'name'):
            name = signal.name.value if hasattr(signal.name, 'value') else str(signal.name)
        else:
            name = str(signal)


class ConnectionExtractor:
    def __init__(self, adapter: PyslangAdapter):
        self.adapter = adapter
        self.root_module_name = None

    def _get_parent_module_name(self, inst) -> str:
        """Safely get parent module name from instance (handles generate blocks)."""
        node = inst
        for _ in range(5):
            if not hasattr(node, 'parent') or node.parent is None:
                break
            node = node.parent
            if type(node).__name__ == 'ModuleDeclarationSyntax':
                if hasattr(node, 'header') and hasattr(node.header, 'name'):
                    return node.header.name.rawText.strip()
                elif hasattr(node, 'name'):
                    return node.name.rawText.strip()
        return 'unknown'

    def _get_generate_block_name(self, inst) -> str:
        """Get the generate block label if instance is inside a generate block."""
        node = inst
        for _ in range(5):
            if not hasattr(node, 'parent') or node.parent is None:
                break
            node = node.parent
            if type(node).__name__ == 'GenerateBlockSyntax':
                if hasattr(node, 'beginName') and node.beginName:
                    bn = node.beginName
                    if hasattr(bn, 'name') and hasattr(bn.name, 'value'):
                        return bn.name.value.strip()
        return None

    def _missing_module_warning(self, inst_module_name: str, inst_name: str):
        """输出可能缺少文件的警告信息"""
        import logging
        logger = logging.getLogger('sv_query')
        msg = (
            f"[sv_query] 可能缺少文件: 实例 '{inst_name}' 的模块 '{inst_module_name}' "
            f"没有找到端口定义。\n"
            f"  → 可能原因: 解析的文件范围不完整,缺少 '{inst_module_name}' 的定义文件\n"
            f"  → 建议: 确保传入所有相关的 Verilog 文件,或使用 glob 模式匹配整个目录\n"
            f"  → 例如: sv_query 'path/to/**/*.v' (递归) 或 sv_query 'file1.v file2.v' (多文件)"
        )
        logger.warning(msg)
        # 同时记录到 ExtractorResult.warnings 中
        if not hasattr(self, '_warnings'):
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
            trees = getattr(self.adapter.parser, 'trees', {})
            if trees:
                # trees 的键是 tree 文件的键,不一定等于实际模块名
                # 需要验证该键是否对应实际模块,否则使用实际模块名
                tree_key = list(trees.keys())[0]
                actual_modules = [self.adapter.get_module_name(m) for m in self.adapter.get_modules()]
                if tree_key in actual_modules:
                    self.root_module_name = tree_key
                else:
                    # tree key 与实际模块名不匹配,查找包含实例的模块
                    # 通过检查 get_module_instances 返回的实例来确定哪个模块包含实例
                    instances = self.adapter.get_module_instances(trees) + self.adapter.get_generate_instances(trees)
                    if instances:
                        # 实例存在,说明某些模块包含实例
                        # 找到第一个包含实例的模块
                        for mod in self.adapter.get_modules():
                            mod_name = self.adapter.get_module_name(mod)
                            # 检查这个模块是否有 members (实例会在 members 中)
                            members = getattr(mod, 'members', None)
                            if members:
                                for item in members:
                                    if 'HierarchyInstantiation' in str(getattr(item, 'kind', '')):
                                        self.root_module_name = mod_name
                                        break
                            if self.root_module_name == mod_name:
                                break
                        # 如果还没找到,使用第一个包含实例的模块
                        if self.root_module_name not in actual_modules:
                            self.root_module_name = actual_modules[0] if actual_modules else tree_key
                    else:
                        # 没有实例,使用第一个模块
                        self.root_module_name = actual_modules[0] if actual_modules else tree_key
            else:
                for mod in self.adapter.get_modules():
                    self.root_module_name = self.adapter.get_module_name(mod)
                    break

        trees = getattr(self.adapter.parser, 'trees', {})
        instances = self.adapter.get_module_instances(trees) + self.adapter.get_generate_instances(trees)

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
                    msb = width.get('msb_eval', width.get('msb_raw', 0))
                    lsb = width.get('lsb_eval', width.get('lsb_raw', 0))
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
            inst_name = inst.instances[0].decl.name.value.strip() if hasattr(inst.instances[0], 'decl') and hasattr(inst.instances[0].decl, 'name') and inst.instances[0].decl.name.value else str(inst).split('(')[0].strip()

            inst_type_value = inst.type.value.strip() if hasattr(inst.type, 'value') and inst.type.value else ''
            inst_module_name = inst_type_value if inst_type_value and inst_type_value != inst_name else self._get_parent_module_name(inst)
            parent_module = self._get_parent_module_name(inst)

            gen_block = self._get_generate_block_name(inst)
            instances_info.append({
                'inst_module_name': inst_module_name,
                'inst_name': inst_name,
                'parent_module': parent_module,
                'gen_block': gen_block
            })

        # [FIX] 第二阶段:构建模块 -> 实例路径的映射
        module_to_path = {}  # (inst_module_name, inst_name) -> full_path

        # 递归确定路径
        def get_path(info, depth=0):
            """递归获取实例的完整路径"""
            if depth > 20:
                return f"{self.root_module_name}.{info['inst_name']}"
            parent_mod = info['parent_module']
            gen_block = info.get('gen_block')
            if parent_mod == 'top':
                if gen_block:
                    return f"{self.root_module_name}.{gen_block}.{info['inst_name']}"
                return f"{self.root_module_name}.{info['inst_name']}"
            else:
                for other_info in instances_info:
                    if other_info['inst_module_name'] == parent_mod:
                        parent_path = get_path(other_info, depth+1)
                        if gen_block:
                            return f"{parent_path}.{gen_block}.{info['inst_name']}"
                        return f"{parent_path}.{info['inst_name']}"
                if gen_block:
                    return f"{self.root_module_name}.{gen_block}.{info['inst_name']}"
                return f"{self.root_module_name}.{info['inst_name']}"

        for info in instances_info:
            path = get_path(info)
            gen_block = info.get('gen_block')
            if gen_block:
                key = (info['inst_module_name'], info['inst_name'], gen_block)
            else:
                key = (info['inst_module_name'], info['inst_name'])
            module_to_path[key] = path

        # [FIX] 第三阶段:使用正确路径创建节点和边
        for inst in instances:
            inst_name = inst.instances[0].decl.name.value.strip() if hasattr(inst.instances[0], 'decl') and hasattr(inst.instances[0].decl, 'name') and inst.instances[0].decl.name.value else str(inst).split('(')[0].strip()

            inst_type_value = inst.type.value.strip() if hasattr(inst.type, 'value') and inst.type.value else ''
            inst_module_name = inst_type_value if inst_type_value and inst_type_value != inst_name else self._get_parent_module_name(inst)

            gen_block = self._get_generate_block_name(inst)
            if gen_block:
                key = (inst_module_name, inst_name, gen_block)
                inst_path = module_to_path.get(key, f"{self.root_module_name}.{gen_block}.{inst_name}")
            else:
                key = (inst_module_name, inst_name)
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
                if port_key.startswith('_pos_'):
                    idx = int(port_key.replace('_pos_', ''))
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
                gen_path = inst_path.rsplit('.', 1)[0]  # e.g., top.GEN from top.GEN.g
                gen_module = '.'.join(gen_path.rsplit('.', 1)[:-1]) or gen_path.rsplit('.', 1)[0]  # e.g., top from top.GEN
                # 检查是否已经存在
                if not any(n.id == gen_path for n in result.nodes):
                    result.nodes.append(TraceNode(
                        id=gen_path,
                        name=gen_block,
                        module=gen_module,
                        kind=NodeKind.GENERATE_BLOCK if hasattr(NodeKind, 'GENERATE_BLOCK') else NodeKind.INSTANTIATED_MODULE,
                        width=(1, 0),
                        is_port=False
                    ))

            # 创建实例父节点
            result.nodes.append(TraceNode(
                id=inst_path,
                name=inst_name,
                module=inst_path.rsplit('.', 1)[0] if '.' in inst_path else 'top',
                kind=NodeKind.INSTANTIATED_MODULE,
                width=(1, 0),
                is_port=False
            ))

            # 为每个端口创建节点和边
            for port_name, signal_name in named_conns.items():
                port_name = self.adapter.clean_name(port_name)
                signal_name = self.adapter.clean_name(signal_name)

                direction = module_ports.get(port_name, 'unknown').strip()

                inst_port_id = f"{inst_path}.{port_name}"
                if 'inout' in direction.lower():
                    kind = NodeKind.PORT_INOUT
                elif 'output' in direction.lower():
                    kind = NodeKind.PORT_OUT
                else:
                    kind = NodeKind.PORT_IN
                # 获取端口位宽
                port_widths = all_module_widths.get(inst_module_name, {})
                width = port_widths.get(port_name, (1, 0))

                # [NEW] 如果位宽为 (0,0),尝试从父模块的信号宽度推断
                if width == (0, 0) and signal_name:
                    parent_path = inst_path.rsplit('.', 1)[0] if '.' in inst_path else 'top'
                    parent_widths = all_module_widths.get(parent_path, {})
                    if signal_name in parent_widths:
                        width = parent_widths[signal_name]

                result.nodes.append(TraceNode(
                    id=inst_port_id,
                    name=port_name,
                    module=inst_path,
                    kind=kind,
                    width=width if width != (0, 0) else (1, 0),
                    is_port=True
                ))

                direction_clean = direction.strip()
                parent_path = inst_path.rsplit('.', 1)[0] if '.' in inst_path else 'top'

                if direction_clean == 'input':
                    result.edges.append(TraceEdge(
                        src=f"{parent_path}.{signal_name}",
                        dst=inst_port_id,
                        kind=EdgeKind.CONNECTION,
                        assign_type="connection"
                    ))
                    child_signal_id = f"{inst_module_name}.{port_name}"
                    result.edges.append(TraceEdge(
                        src=inst_port_id,
                        dst=child_signal_id,
                        kind=EdgeKind.CONNECTION,
                        assign_type="internal"
                    ))
                    # 同步构建 port_to_internal 映射
                    result.port_to_internal[inst_port_id] = child_signal_id
                elif direction_clean == 'output':
                    # 输出端口: inst_port_id 接收来自 child_module.port 的驱动
                    # 连接关系: child.y → parent_signal (DRIVER 边)
                    # 同时 inst_port_id 是 child_signal_id 的别名
                    parent_signal = f"{parent_path}.{signal_name}"
                    result.edges.append(TraceEdge(
                        src=child_signal_id,
                        dst=parent_signal,
                        kind=EdgeKind.DRIVER,
                        assign_type="connection"
                    ))
                    result.edges.append(TraceEdge(
                        src=inst_port_id,
                        dst=child_signal_id,
                        kind=EdgeKind.DRIVER,
                        assign_type="internal"
                    ))
                    # 同步构建 port_to_internal 映射
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
                parts = dst_node.id.split('.')
                if len(parts) >= 3 and dst_node.kind.name.startswith('PORT_'):
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
                                    is_port=n.is_port
                                )
                                break

        # [FIX Issue 20] 将警告信息添加到 result
        if hasattr(self, '_warnings') and self._warnings:
            result.warnings = self._warnings
        
        return result


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
                    if 'inout' in direction.lower():
                        kind = NodeKind.PORT_INOUT
                    elif 'output' in direction.lower():
                        kind = NodeKind.PORT_OUT
                    else:
                        kind = NodeKind.PORT_IN
                    # 提取端口位宽 (传入 module 作为 scope 以解析参数)
                    port_width = self.adapter.extract_port_width(port_decl, scope=module)
                    # convert dict to tuple for compatibility
                    if isinstance(port_width, dict):
                        msb = port_width.get('msb_eval', port_width.get('msb_raw', 0))
                        lsb = port_width.get('lsb_eval', port_width.get('lsb_raw', 0))
                        try:
                            msb = int(msb) if msb is not None else 0
                        except (ValueError, TypeError):
                            msb = 0
                        try:
                            lsb = int(lsb) if lsb is not None else 0
                        except (ValueError, TypeError):
                            lsb = 0
                        port_width = (msb, lsb)
                    result.nodes.append(TraceNode(
                        id=port_id,
                        name=port_name,
                        module=module_name,
                        kind=kind,
                        width=port_width,
                        is_port=True
                    ))

            for port in self.adapter.get_port_names(module):
                port_name, direction = self.adapter.get_port_name_and_direction(port)
                if not port_name:
                    continue

                port_name = self.adapter.clean_name(port_name)

                is_clock = 'clk' in port_name.lower()
                is_reset = 'rst' in port_name.lower()

                if is_clock or is_reset:
                    result.nodes.append(TraceNode(
                        id=f"{module_name}.{port_name}",
                        name=port_name,
                        module=module_name,
                        kind=NodeKind.PORT_IN,
                        width=(1, 0),
                        is_clock=is_clock,
                        is_reset=is_reset
                    ))

        return result

class GraphBuilder:
    def __init__(self, adapter: PyslangAdapter):
        self.adapter = adapter
        self.graph = SignalGraph()
        self._extractors = {
            'driver': DriverExtractor(adapter),
            'load': LoadExtractor(adapter),
            'connection': ConnectionExtractor(adapter),
            'clock': ClockDomainExtractor(adapter),
        }

    def build(self) -> SignalGraph:
        self._extract_all_nodes()
        self._extract_all_edges()
        self._mark_special_signals()
        self._create_hierarchical_bit_nodes()
        self._upgrade_reg_nodes()  # Must be after _create_hierarchical_bit_nodes

        return self.graph

    def _create_hierarchical_bit_nodes(self):
        """方案C: 为位选择节点创建父子关系
        - 识别 data[3] 形式的节点
        - 创建/找到父节点 data
        - 设置 child.parent = data
        - 创建聚合边 data[3] → data (BIT_SELECT)
        - 重命名边: 所有引用 data[3] 的边保持不变
        """
        import re

        child_ids = [nid for nid in list(self.graph.nodes()) if '[' in nid and ']' in nid]

        for child_id in child_ids:
            # 提取父节点名: top.data[3] → top.data
            parent_id = re.sub(r'\[.*?\]', '', child_id)

            if not parent_id or parent_id == child_id:
                continue

            # 确保父节点存在
            if parent_id not in self.graph.nodes():
                # 从子节点推断父节点属性
                child_node = self.graph.get_node(child_id)
                if child_node:
                    parent_name = re.sub(r'\[.*?\]', '', child_node.name)
                    parent_node = TraceNode(
                        id=parent_id,
                        name=parent_name,
                        module=child_node.module,
                        kind=child_node.kind,
                        width=child_node.width,
                    )
                    self.graph.add_trace_node(parent_node)

            # 设置子节点的 parent
            child_node = self.graph.get_node(child_id)
            if child_node:
                child_node.parent = parent_id
                # Don't change kind here - it was set during DriverExtractor based on always_ff assignment
                # Just ensure it has a kind
                if child_node.kind is None:
                    child_node.kind = NodeKind.SIGNAL

            # 创建聚合边: child → parent (BIT_SELECT)
            agg_edge = TraceEdge(
                src=child_id,
                dst=parent_id,
                kind=EdgeKind.BIT_SELECT,
            )
            self.graph.add_trace_edge(agg_edge)

    def get_extractor(self, name):
        return self._extractors.get(name)

    def _extract_all_nodes(self):
        for name, extractor in self._extractors.items():
            result = extractor.extract()
            for node in result.nodes:
                self.graph.add_trace_node(node)

    def _extract_all_edges(self):
        for name, extractor in self._extractors.items():
            result = extractor.extract()
            for edge in result.edges:
                self.graph.add_trace_edge(edge)
            # 收集 port_to_internal 映射
            if hasattr(result, 'port_to_internal') and result.port_to_internal:
                self.graph._port_to_internal.update(result.port_to_internal)

        # [P0-3] 设置 interface 信号的 modport_dir
        self._set_interface_modport_dirs()

    def _set_interface_modport_dirs(self):
        """设置 interface 信号的 modport_dir 属性"""
        # Build interface_ports map for each module
        for module in self.adapter.get_modules():
            module_name = self.adapter.get_module_name(module)

            interface_ports = {}  # port_name -> (interface_name, modport_name)
            try:
                if hasattr(module, 'header') and module.header:
                    header = module.header
                    if hasattr(header, 'ports') and hasattr(header.ports, 'ports'):
                        for item in header.ports.ports:
                            if not hasattr(item, 'kind') or item.kind != pyslang.SyntaxKind.ImplicitAnsiPort:
                                continue
                            try:
                                h = getattr(item, 'header', None)
                                decl = getattr(item, 'declarator', None)
                            except AttributeError:
                                continue
                            if h is None or decl is None:
                                continue
                            if hasattr(h, 'kind') and 'InterfacePortHeader' in str(h.kind):
                                port_name = decl.name.value if hasattr(decl.name, 'value') else str(decl.name)
                                interface_name = None
                                if hasattr(h, 'nameOrKeyword'):
                                    nk = h.nameOrKeyword
                                    interface_name = nk.rawText if hasattr(nk, 'rawText') else str(nk)
                                modport_name = None
                                if hasattr(h, 'modport') and hasattr(h.modport, 'member'):
                                    member_val = h.modport.member
                                    modport_name = member_val.name if hasattr(member_val, 'name') else str(member_val)
                                if port_name and interface_name:
                                    interface_ports[port_name.strip()] = (interface_name, modport_name)
            except (ValueError, AttributeError, TypeError):
                pass

            # For each node in the graph that's in this module
            for node_id, node in self.graph._node_data.items():
                if node.module != module_name:
                    continue

                # Check if node is an interface signal (e.g., "top.m.data")
                # node_id format: module.port.signal
                if '.' in node_id:
                    parts = node_id.split('.')
                    # port is the second part (index 1): e.g., 'm' from 'top.m.data'
                    if len(parts) >= 2 and parts[1] in interface_ports:
                        port_name = parts[1]
                        # signal is the third part (index 2): e.g., 'data' from 'top.m.data'
                        signal_name = parts[2] if len(parts) >= 3 else parts[1]
                        interface_name, modport_name = interface_ports[port_name]

                        # Get signal direction from interface
                        signal_dir = self.adapter.get_interface_modport_signals(interface_name, modport_name).get(signal_name)
                        if signal_dir:
                            node.modport_dir = signal_dir

    def _upgrade_reg_nodes(self):
        """Upgrade node kind to REG if it's driven by a CLOCK edge.
        Only upgrade the direct target, NOT bit-select parents."""
        for (src, dst), edge in self.graph._edge_data.items():
            if edge.kind == EdgeKind.CLOCK:
                # Only upgrade the direct target
                if '[' not in dst:  # Not a bit-select
                    node = self.graph._node_data.get(dst)
                    if node and node.kind != NodeKind.REG:
                        was_port = getattr(node, 'is_port', False)
                        node.kind = NodeKind.REG
                        if was_port:
                            node.is_port = True

    def _mark_special_signals(self):
        for node_id, node in self.graph._node_data.items():
            name_lower = node.name.lower()

            if 'clk' in name_lower or 'clock' in name_lower:
                node.is_clock = True

            if 'rst' in name_lower or 'reset' in name_lower:
                node.is_reset = True

    def stats(self) -> Dict:
        return {
            "nodes": self.graph.number_of_nodes(),
            "edges": self.graph.number_of_edges(),
            **self.graph.stats()
        }

#==============================================================================
# [补丁] 修复多事件敏感信号列表的时钟提取 (2026-05-09)
# 原因: 27690eb commit 删除了 _extract_reset_from_event_ctrl,导致
#       @(posedge clk_a or negedge rst_a_n) 只能提取到 clk_a
#==============================================================================
