# call_graph_builder.py - 函数调用图构建器
#
# 从 pyslang 语法树提取函数/任务调用关系，构建调用图。
# 独立于 SignalGraph，不修改图结构。
#
# [铁律15] Visitor 模式
# [铁律3] 不可信则不输出

import logging
from typing import Dict, Optional, List

import pyslang

from .compiler import SVCompiler
from .graph.call_graph_models import CallNode, CallGraph

logger = logging.getLogger(__name__)


class CallGraphBuilder:
    """函数调用图构建器

    从指定入口函数/任务出发，递归提取调用关系。
    支持:
    - 串行函数/任务调用
    - fork/join/join_none/join_any
    - randomize() 标记
    - inline constraint 提取
    """

    def __init__(self, sources: Dict[str, str]):
        self._sources = sources
        self._task_defs = {}  # {class_name.task_name: syntax_node}
        self._func_defs = {}
        self._randomize_calls = []
        self._fork_points = []

    def build(self, entry_class: str, entry_method: str) -> CallGraph:
        """构建调用图

        Args:
            entry_class: 入口类名 (如 "my_seq")
            entry_method: 入口方法名 (如 "body")

        Returns:
            CallGraph
        """
        # 1. 使用 Semantic AST 收集函数/任务定义 [铁律1]
        try:
            compiler = SVCompiler(sources=self._sources)
            root = compiler.get_root()
            self._collect_definitions_semantic(root)
        except Exception as e:
            logger.warning(f"Semantic AST 编译失败: {e}")

        # 2. 找到入口
        entry_key = f"{entry_class}.{entry_method}"
        entry_node = self._task_defs.get(entry_key) or self._func_defs.get(entry_key)
        if entry_node is None:
            return CallGraph(
                entry_point=entry_key,
                errors=[f"未找到入口: {entry_key}"]
            )

        # 3. 递归构建调用图
        self._randomize_calls = []
        self._fork_points = []
        root = self._build_call_node(entry_node, entry_class, entry_method)

        # 4. 检测 UVM 行为模式
        root.pattern = self._detect_pattern(root, entry_method)

        return CallGraph(
            entry_point=entry_key,
            root=root,
            randomize_calls=self._randomize_calls,
            fork_points=self._fork_points,
        )

    def _detect_pattern(self, root: CallNode, entry_method: str) -> str:
        """检测 UVM 行为模式

        规则:
        - sequence: body 方法 + 包含 create/start_item/finish_item 中的至少两个
        - driver: run_phase 方法 + 包含 get_next_item/item_done 中的至少一个
        - generic: 其他
        """
        call_names = set()
        self._collect_all_calls(root, call_names)

        # sequence 模式
        seq_indicators = {'create', 'start_item', 'finish_item'}
        seq_matches = call_names & seq_indicators
        if entry_method == 'body' and len(seq_matches) >= 2:
            return 'sequence'
        if len(seq_matches) >= 3:
            return 'sequence'

        # driver 模式
        drv_indicators = {'get_next_item', 'item_done'}
        drv_matches = call_names & drv_indicators
        if 'run_phase' in entry_method and len(drv_matches) >= 1:
            return 'driver'
        if len(drv_matches) >= 2:
            return 'driver'

        return 'generic'

    def _collect_all_calls(self, node: CallNode, names: set):
        """递归收集所有调用名"""
        names.add(node.callee)
        for child in node.children:
            self._collect_all_calls(child, names)

    # =========================================================================
    # 收集定义 (Semantic AST)
    # =========================================================================

    def _collect_definitions_semantic(self, node, class_name: str = ''):
        """使用 Semantic AST 递归收集函数/任务定义 [铁律1]"""
        kind = str(getattr(node, 'kind', ''))

        if 'ClassType' in kind:
            class_name = str(getattr(node, 'name', '')).strip()

        if 'Subroutine' in kind:
            name = str(getattr(node, 'name', '')).strip()
            if name:
                syntax = getattr(node, 'syntax', None)
                key = f"{class_name}.{name}" if class_name else name
                if syntax:
                    self._task_defs[key] = syntax
            return

        try:
            for child in node:
                self._collect_definitions_semantic(child, class_name)
        except TypeError:
            pass

    # =========================================================================
    # 收集定义 (Syntax Tree - legacy)
    # =========================================================================

    def _collect_definitions(self, node, fname: str):
        """递归收集函数/任务定义"""
        kind = str(getattr(node, 'kind', ''))

        if 'TaskDeclaration' in kind or 'FunctionDeclaration' in kind:
            self._collect_subroutine(node)
            return  # 不递归进入子程序体

        if 'Token' not in kind:
            try:
                for child in node:
                    self._collect_definitions(child, fname)
            except TypeError:
                pass

    def _collect_subroutine(self, node):
        """收集单个函数/任务定义"""
        kind = str(getattr(node, 'kind', ''))

        # 获取名称
        name = ''
        keyword = ''
        for child in node:
            ck = str(getattr(child, 'kind', ''))
            if 'FunctionPrototype' in ck:
                name = str(getattr(child, 'name', '')).strip()
                keyword = str(getattr(child, 'keyword', '')).strip()

        if not name:
            return

        # 确定所属类
        class_name = self._find_parent_class(node)
        key = f"{class_name}.{name}" if class_name else name

        if 'Task' in kind:
            self._task_defs[key] = node
        else:
            self._func_defs[key] = node

    def _find_parent_class(self, node) -> str:
        """向上查找父 class 名称"""
        parent = getattr(node, 'parent', None)
        while parent:
            kind = str(getattr(parent, 'kind', ''))
            if 'ClassDeclaration' in kind:
                return str(getattr(parent, 'name', '')).strip()
            parent = getattr(parent, 'parent', None)
        return ''

    # =========================================================================
    # 构建调用节点
    # =========================================================================

    def _build_call_node(self, node, class_name: str, method_name: str) -> CallNode:
        """递归构建调用节点"""
        caller = f"{class_name}.{method_name}" if class_name else method_name

        call_node = CallNode(
            caller=caller,
            callee=method_name,
            kind='call',
        )

        # 遍历函数体，提取调用
        self._extract_calls(node, call_node, class_name)

        return call_node

    def _extract_calls(self, node, parent_node: CallNode, class_name: str):
        """从语句中提取调用"""
        kind = str(getattr(node, 'kind', ''))

        # ParallelBlockStatement → fork
        if 'ParallelBlock' in kind:
            fork_node = self._build_fork_node(node, parent_node.caller, class_name)
            if fork_node:
                parent_node.children.append(fork_node)
            return

        # ExpressionStatement 包含 InvocationExpression 或 ArrayOrRandomizeMethodExpression
        if 'ExpressionStatement' in kind:
            # 先检查是否是 ArrayOrRandomizeMethodExpression (randomize with constraint)
            arr_rand = self._find_node(node, 'ArrayOrRandomize')
            if arr_rand:
                call = self._process_randomize(arr_rand, parent_node.caller)
                if call:
                    parent_node.children.append(call)
                    self._randomize_calls.append(call)
                return
            inv = self._find_invocation(node)
            if inv:
                call = self._process_invocation(inv, parent_node.caller, class_name)
                if call:
                    parent_node.children.append(call)
            return

        # AssignmentExpression 包含 randomize
        if 'Assignment' in kind:
            randomize = self._find_randomize(node)
            if randomize:
                call = self._process_randomize(randomize, parent_node.caller)
                if call:
                    parent_node.children.append(call)
                    self._randomize_calls.append(call)
            return

        # 递归进入子节点
        if 'Token' not in kind:
            try:
                for child in node:
                    self._extract_calls(child, parent_node, class_name)
            except TypeError:
                pass

    def _build_fork_node(self, node, caller: str, class_name: str) -> Optional[CallNode]:
        """构建 fork 节点"""
        # 获取 join 类型
        end_token = getattr(node, 'end', None)
        join_type = 'join'
        if end_token:
            end_str = str(end_token).strip()
            if 'join_none' in end_str:
                join_type = 'join_none'
            elif 'join_any' in end_str:
                join_type = 'join_any'
            elif 'join' in end_str:
                join_type = 'join'

        fork_node = CallNode(
            caller=caller,
            callee='fork',
            kind='fork',
            join_type=join_type,
        )
        self._fork_points.append(fork_node)

        # 遍历 fork 内的语句
        items = getattr(node, 'items', None)
        if items:
            for item in items:
                self._extract_calls(item, fork_node, class_name)

        return fork_node

    def _find_invocation(self, node) -> Optional[object]:
        """在 ExpressionStatement 中找 InvocationExpression"""
        return self._find_node(node, 'Invocation')

    def _find_randomize(self, node) -> Optional[object]:
        """在 AssignmentExpression 中找 ArrayOrRandomizeMethodExpression"""
        return self._find_node(node, 'Randomize') or self._find_node(node, 'ArrayOrRandomize')

    def _find_node(self, node, kind_keyword: str) -> Optional[object]:
        """递归查找包含指定关键词的节点"""
        kind = str(getattr(node, 'kind', ''))
        if kind_keyword in kind:
            return node
        if 'Token' not in kind:
            try:
                for child in node:
                    result = self._find_node(child, kind_keyword)
                    if result:
                        return result
            except TypeError:
                pass
        return None

    def _process_invocation(self, node, caller: str, class_name: str) -> Optional[CallNode]:
        """处理 InvocationExpression"""
        callee = self._extract_call_name(node)
        if not callee:
            return None

        # 检查是否是 randomize 调用
        if 'randomize' in callee.lower():
            call = CallNode(
                caller=caller,
                callee=callee,
                kind='randomize',
            )
            self._randomize_calls.append(call)
            return call

        # 检查是否是已定义的 task/function
        key = f"{class_name}.{callee}"
        if key in self._task_defs or key in self._func_defs:
            sub_node = self._task_defs.get(key) or self._func_defs.get(key)
            return self._build_call_node(sub_node, class_name, callee)

        # 外部调用
        return CallNode(
            caller=caller,
            callee=callee,
            kind='call',
        )

    def _extract_call_name(self, node) -> str:
        """从 InvocationExpression 提取调用名"""
        # 尝试 expression 属性
        expr = getattr(node, 'expression', None) or getattr(node, 'left', None)
        if expr:
            name = str(expr).strip()
            # 去掉参数部分
            if '(' in name:
                name = name[:name.index('(')]
            return name.strip()

        # 尝试从子节点提取
        for child in node:
            ck = str(getattr(child, 'kind', ''))
            if 'Token' not in ck:
                name = str(child).strip()
                if '(' in name:
                    name = name[:name.index('(')]
                return name.strip()

        return ''

    def _process_randomize(self, node, caller: str) -> Optional[CallNode]:
        """处理 randomize 表达式
        
        node 可能是:
        - ArrayOrRandomizeMethodExpression (randomize with constraint)
        - InvocationExpression (randomize without constraint)
        """
        kind = str(getattr(node, 'kind', ''))
        
        callee = 'randomize'
        inline = ''
        
        if 'ArrayOrRandomize' in kind:
            # ArrayOrRandomizeMethodExpression: randomize() with { ... }
            # 提取 InvocationExpression (randomize())
            inv = self._find_node(node, 'Invocation')
            if inv:
                callee = self._extract_call_name(inv) or 'randomize'
            # 提取 ConstraintBlock
            constraint = self._find_node(node, 'ConstraintBlock')
            if constraint:
                inline = str(constraint).strip()
        else:
            # InvocationExpression: randomize()
            callee = self._extract_call_name(node) or 'randomize'
        
        return CallNode(
            caller=caller,
            callee=callee,
            kind='randomize',
            inline_constraint=inline,
        )
