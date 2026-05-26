# ControlFlow Analyzer - 控制流分析器
# 基于 docs/CONTROL_FLOW_DESIGN.md 设计
# 采用交叉定位方式: 同时指定控制变量和数据变量来定位分析

from typing import List, Dict, Optional, Set, Any, Tuple
from dataclasses import dataclass

from ..controlflow import ControlFlowGraph
from ..controlflow_models import (
    ControlFlowResult,
    ControlBlock,
    ControlFlowNode,
    ControlFlowNodeKind,
    BranchResult,
    LintWarning,
    Contradiction,
    StateMachineAnalysis,
    Z3Result,
    BranchKind,
    Branch,
    Location,
)
from ...graph_builder import GraphBuilder
from ...visitors.signal_expression_visitor import SignalExpressionVisitor
from ...semantic_adapter import SemanticAdapter


class ControlFlowAnalyzer:
    """控制流分析器 - 交叉定位方式"""
    
    def __init__(
        self,
        graph_builder: Optional[GraphBuilder] = None,
        semantic_adapter: Optional[SemanticAdapter] = None,
    ):
        """
        初始化控制流分析器
        
        Args:
            graph_builder: GraphBuilder 实例，用于获取 SignalGraph
            semantic_adapter: 语义适配器
        """
        self.graph_builder = graph_builder
        self.semantic_adapter = semantic_adapter
        
        # SignalExpressionVisitor 用于解析条件表达式
        self._signal_visitor = SignalExpressionVisitor()
        
        # 已构建的控制流图缓存
        self._cfg_cache: Dict[str, ControlFlowGraph] = {}
    
    def analyze(
        self,
        control_var: str,
        data_var: str,
        module: Optional[str] = None,
    ) -> ControlFlowResult:
        """
        分析 control_var 如何控制 data_var 的数据流
        
        Args:
            control_var: 控制变量 (如 "en")
            data_var: 数据变量 (如 "q")
            module: 模块名，不指定则从 graph_builder 获取
        
        Returns:
            ControlFlowResult: 控制流分析结果
        """
        # 1. 获取模块的信号图
        signal_graph = self._get_signal_graph(module)
        if signal_graph is None:
            return ControlFlowResult(control_var=control_var, data_var=data_var)
        
        # 2. 构建控制流图
        module_name = module or signal_graph.module_name
        cfg = self._get_or_build_cfg(module_name)
        
        # 3. 查找同时包含 control_var 和 data_var 的控制块
        blocks = cfg.find_control_blocks(
            control_vars=[control_var],
            data_vars=[data_var],
        )
        
        # 4. 构建结果
        result = ControlFlowResult(
            control_var=control_var,
            data_var=data_var,
        )
        
        if not blocks:
            return result
        
        # 取第一个匹配的控制块进行分析
        block = blocks[0]
        result.control_block = block
        
        # 5. 提取条件信息
        result.condition_expr = block.condition_expr
        result.condition_vars = block.control_vars
        
        # 6. 提取信号来源
        result.condition_sources = self._get_signal_sources(
            block.control_vars, signal_graph
        )
        
        # 7. 分析分支
        result.branches = self._analyze_branches(block)
        
        # 8. 生成数据流条件
        result.data_flow_when = self._generate_data_flow_when(block)
        
        # 9. Lint 检查
        result.warnings = self._check_lint(block)
        
        return result
    
    def find_control_blocks(
        self,
        control_vars: List[str],
        data_vars: List[str],
        module: Optional[str] = None,
    ) -> List[ControlBlock]:
        """
        查找同时包含控制变量和数据变量的代码块
        
        Args:
            control_vars: 控制变量列表 (如 ["en", "valid"])
            data_vars: 数据变量列表 (如 ["q", "data_out"])
            module: 模块名
        
        Returns:
            List[ControlBlock]: 匹配的控制块列表
        """
        signal_graph = self._get_signal_graph(module)
        module_name = module or (signal_graph.module_name if signal_graph else "")
        
        cfg = self._get_or_build_cfg(module_name)
        
        return cfg.find_control_blocks(control_vars, data_vars)
    
    def analyze_module(
        self,
        module: str,
        only_conditions: bool = True,
    ) -> ControlFlowResult:
        """
        分析模块的控制流
        
        Args:
            module: 模块名
            only_conditions: 是否只分析出现在 if/case/三元 条件中的变量
        
        Returns:
            ControlFlowResult: 控制流分析结果
        """
        cfg = self._get_or_build_cfg(module)
        
        result = ControlFlowResult()
        
        # 收集所有条件变量
        condition_vars = list(cfg.get_condition_vars())
        
        if only_conditions:
            # 只分析出现在条件中的变量
            result.condition_vars = condition_vars
        else:
            # 分析所有变量
            pass
        
        # Lint 检查
        missing_else = cfg.check_missing_else()
        missing_default = cfg.check_missing_default()
        
        for block in missing_else:
            result.warnings.append(LintWarning(
                severity="warning",
                rule="INCOMPLETE_IF",
                file=block.file,
                line=block.line,
                column=block.column,
                message="if statement without else branch",
                suggestion="add else branch to avoid latch inference",
            ))
        
        for block in missing_default:
            result.warnings.append(LintWarning(
                severity="warning",
                rule="INCOMPLETE_CASE",
                file=block.file,
                line=block.line,
                column=block.column,
                message="case statement without default branch",
                suggestion="add default branch to handle undefined values",
            ))
        
        return result
    
    def get_state_machine_analysis(
        self,
        state_var: str,
        module: Optional[str] = None,
    ) -> Optional[StateMachineAnalysis]:
        """
        获取状态机的分析结果
        
        Args:
            state_var: 状态变量名 (如 "state")
            module: 模块名
        
        Returns:
            StateMachineAnalysis 或 None
        """
        signal_graph = self._get_signal_graph(module)
        module_name = module or (signal_graph.module_name if signal_graph else "")
        
        cfg = self._get_or_build_cfg(module_name)
        
        return cfg.get_state_machine(state_var)
    
    def _get_or_build_cfg(self, module: str) -> ControlFlowGraph:
        """获取或构建指定模块的控制流图"""
        if module in self._cfg_cache:
            return self._cfg_cache[module]
        
        cfg = self._build_cfg(module)
        self._cfg_cache[module] = cfg
        return cfg
    
    def _build_cfg(self, module: str) -> ControlFlowGraph:
        """从 AST 构建控制流图"""
        cfg = ControlFlowGraph(module_name=module)
        
        if self.graph_builder is None:
            return cfg
        
        # 获取模块的 AST
        compilation = self.graph_builder.compilation
        if compilation is None:
            return cfg
        
        # 查找模块定义
        for unit in compilation.files:
            for node in unit.find_all(kind('always_ff', 'always_comb', 'always_latch', 'always')):
                self._process_procedure(cfg, node)
        
        return cfg
    
    def _process_procedure(self, cfg: ControlFlowGraph, proc_node) -> None:
        """处理过程块"""
        # 遍历语句，查找 if/case/三元
        self._traverse_and_build(cfg, proc_node)
    
    def _traverse_and_build(self, cfg: ControlFlowGraph, node) -> None:
        """遍历 AST 节点并构建控制流"""
        # 这里需要根据 pyslang 的 AST 结构来处理
        # 暂时留空，后续根据实际 AST 结构实现
        
        # 处理 if 语句
        if hasattr(node, 'kind') and self._is_if_statement(node):
            self._process_if(cfg, node)
        
        # 处理 case 语句
        elif hasattr(node, 'kind') and self._is_case_statement(node):
            self._process_case(cfg, node)
        
        # 递归遍历子节点
        for child in self._get_children(node):
            self._traverse_and_build(cfg, child)
    
    def _process_if(self, cfg: ControlFlowGraph, if_node) -> None:
        """处理 if 语句"""
        # 提取条件
        condition = self._extract_condition(if_node)
        condition_vars = self._extract_vars_from_condition(condition)
        
        # 创建控制块
        block = ControlBlock(
            file=self._get_file(if_node),
            line=self._get_line(if_node),
            column=self._get_column(if_node),
            kind="if",
            condition_expr=condition,
            control_vars=condition_vars,
        )
        
        # 提取 then 分支
        if hasattr(if_node, 'true_statement'):
            then_stmt = if_node.true_statement
            block.data_stmts.append(self._get_stmt_text(then_stmt))
            block.data_vars.extend(self._extract_lhs_vars(then_stmt))
            block.branches.append(Branch(
                kind=BranchKind.IF,
                condition=condition,
                action=self._get_stmt_text(then_stmt),
            ))
        
        # 提取 else 分支
        if hasattr(if_node, 'false_statement'):
            else_stmt = if_node.false_statement
            block.data_stmts.append(self._get_stmt_text(else_stmt))
            block.data_vars.extend(self._extract_lhs_vars(else_stmt))
            block.branches.append(Branch(
                kind=BranchKind.IF,
                condition="",
                action=self._get_stmt_text(else_stmt),
            ))
        
        cfg.add_control_block(block)
    
    def _process_case(self, cfg: ControlFlowGraph, case_node) -> None:
        """处理 case 语句"""
        # 提取 case 条件
        condition = self._extract_condition(case_node)
        condition_vars = self._extract_vars_from_condition(condition)
        
        # 创建控制块
        block = ControlBlock(
            file=self._get_file(case_node),
            line=self._get_line(case_node),
            kind="case",
            condition_expr=condition,
            control_vars=condition_vars,
        )
        
        # 提取分支
        if hasattr(case_node, 'items'):
            for item in case_node.items:
                case_value = self._get_case_value(item)
                stmt = self._get_stmt_text(item)
                
                block.branches.append(Branch(
                    kind=BranchKind.CASE,
                    condition=condition,
                    value=case_value,
                    action=stmt,
                ))
                
                block.data_stmts.append(stmt)
                block.data_vars.extend(self._extract_lhs_vars(item))
        
        cfg.add_control_block(block)
    
    def _get_signal_graph(self, module: Optional[str]):
        """获取信号图"""
        if self.graph_builder is None:
            return None
        
        # 尝试从 graph_builder 获取信号图
        if module and module in self.graph_builder.graphs:
            return self.graph_builder.graphs[module]
        
        # 返回第一个
        graphs = getattr(self.graph_builder, 'graphs', {})
        if graphs:
            return list(graphs.values())[0]
        
        return None
    
    def _get_signal_sources(
        self,
        vars: List[str],
        signal_graph,
    ) -> Dict[str, str]:
        """获取变量的信号来源"""
        sources = {}
        
        if signal_graph is None:
            return sources
        
        for var in vars:
            # 查找变量的驱动边
            edges = signal_graph.get_edges(signal=var)
            for edge in edges:
                if hasattr(edge, 'driver') and edge.driver:
                    sources[var] = edge.driver
                    break
        
        return sources
    
    def _analyze_branches(self, block: ControlBlock) -> List[BranchResult]:
        """分析分支"""
        results = []
        
        for branch in block.branches:
            results.append(BranchResult(
                condition=branch.condition,
                action=branch.action,
                covered=branch.covered,
                signal_sources=branch.signal_sources,
            ))
        
        return results
    
    def _generate_data_flow_when(self, block: ControlBlock) -> str:
        """生成数据流条件"""
        if not block.condition_expr:
            return "always"
        
        return f"({block.condition_expr})"
    
    def _check_lint(self, block: ControlBlock) -> List[LintWarning]:
        """Lint 检查"""
        warnings = []
        
        if block.kind == "if" and not block.has_else:
            warnings.append(LintWarning(
                severity="warning",
                rule="LATCH_INFERENCE",
                file=block.file,
                line=block.line,
                column=block.column,
                message="if without else may cause latch",
                suggestion="add else branch with default value",
            ))
        
        if block.kind == "case" and not block.has_else:
            warnings.append(LintWarning(
                severity="warning",
                rule="INCOMPLETE_CASE",
                file=block.file,
                line=block.line,
                column=block.column,
                message="case without default may cause latch",
                suggestion="add default branch",
            ))
        
        return warnings
    
    # === 辅助方法 ===
    
    def _is_if_statement(self, node) -> bool:
        return hasattr(node, 'kind') and str(node.kind) == 'ConditionalStatement'
    
    def _is_case_statement(self, node) -> bool:
        return hasattr(node, 'kind') and str(node.kind) == 'CaseStatement'
    
    def _get_children(self, node) -> List:
        """获取子节点"""
        if hasattr(node, 'children'):
            return node.children
        return []
    
    def _extract_condition(self, node) -> str:
        """提取条件表达式"""
        if hasattr(node, 'condition'):
            return self._node_to_str(node.condition)
        if hasattr(node, 'predicate'):
            return self._node_to_str(node.predicate)
        return ""
    
    def _extract_vars_from_condition(self, condition: str) -> List[str]:
        """从条件表达式中提取变量"""
        if not condition:
            return []
        
        # 使用 SignalExpressionVisitor 解析
        try:
            # 创建一个临时的 AST 节点来解析
            from pyslang import SyntaxTree
            tree = SyntaxTree.from_text(condition)
            result = self._signal_visitor.extract(tree.root)
            return result.all_signals if result else []
        except:
            return []
    
    def _extract_lhs_vars(self, stmt) -> List[str]:
        """提取语句左侧的变量"""
        vars = []
        
        if hasattr(stmt, 'lhs'):
            result = self._signal_visitor.extract(stmt.lhs)
            if result:
                vars.extend(result.all_signals)
        
        return vars
    
    def _get_case_value(self, item) -> str:
        """获取 case 分支的值"""
        if hasattr(item, 'matches'):
            return self._node_to_str(item.matches)
        return "default"
    
    def _node_to_str(self, node) -> str:
        """将 AST 节点转为字符串"""
        if node is None:
            return ""
        return str(node)
    
    def _get_file(self, node) -> str:
        return getattr(node, 'source_file', '') or ''
    
    def _get_line(self, node) -> int:
        return getattr(node, 'source_line', 0) or 0
    
    def _get_column(self, node) -> int:
        return getattr(node, 'source_column', 0) or 0
    
    def _get_stmt_text(self, stmt) -> str:
        """获取语句文本"""
        return self._node_to_str(stmt)