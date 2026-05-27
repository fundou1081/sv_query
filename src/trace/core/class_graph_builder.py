#==============================================================================
# class_graph_builder.py - Class & Constraint 子图构建器
#==============================================================================
# [铁律15] Visitor 模式
# [铁律16] 不动现有 GraphBuilder，独立新建
# [铁律4] 模型即契约 - 每个数据字段必须有对应填充代码
#
# 设计:
#   在 GraphBuilder.build() 后追加 class 子图
#   或独立构建后 merge 到 SignalGraph
#==============================================================================

from typing import List, Dict, Optional, Set
from dataclasses import dataclass, field
import pyslang
from pyslang import SyntaxKind

from .graph.models import SignalGraph, TraceNode, TraceEdge, NodeKind, EdgeKind
from .base import PyslangAdapter
from .class_hierarchy import ClassHierarchy
from .visitors.constraint_visitor import ConstraintVisitor


@dataclass
class ClassBuilderResult:
    """Class 子图构建结果"""
    nodes: List[TraceNode] = field(default_factory=list)
    edges: List[TraceEdge] = field(default_factory=list)
    hierarchy: ClassHierarchy = field(default_factory=ClassHierarchy)
    errors: List[str] = field(default_factory=list)


class ClassGraphBuilder:
    """[铁律15] Class & Constraint 子图构建器

    职责:
    - 遍历所有 ClassDeclaration
    - 创建 CLASS、CLASS_PROPERTY、CONSTRAINT_BLOCK、CONSTRAINT_* 节点
    - 创建 CONSTRAINS、HAS_* 等边
    - 建立 ClassHierarchy（extends 链）

    不职责（分离原则）:
    - 不处理 module 级别信号
    - 不处理 class 实例化（Phase 3）
    - 不处理 p.addr 追踪（Phase 3）
    """

    def __init__(self, adapter: PyslangAdapter):
        self.adapter = adapter
        self.hierarchy = ClassHierarchy()
        self._cv = ConstraintVisitor()

    # =========================================================================
    # [铁律15] 主入口 - 每个语法类型独立处理方法
    # =========================================================================

    def build(self, graph: SignalGraph) -> ClassBuilderResult:
        """构建 class 子图，追加到已有 graph

        Args:
            graph: 已有的 SignalGraph（来自 GraphBuilder）

        Returns:
            ClassBuilderResult: 包含新增节点、边、hierarchy
        """
        result = ClassBuilderResult(hierarchy=self.hierarchy)

        # 1. 获取所有 class
        classes = self.adapter.get_classes()

        # 2. 建立 ClassHierarchy（extends 链）
        for cls in classes:
            cls_name = self._class_name(cls)
            extends = self._class_extends(cls)
            self.hierarchy.add_class(cls_name, extends=extends)

        # 3. 遍历每个 class，建节点和边
        for cls in classes:
            cls_name = self._class_name(cls)
            self._build_class_nodes(graph, cls, cls_name, result)

        # 4. 继承传播：将父类的约束复制到子类
        self._propagate_inherited_constraints(graph, result)

        return result

    def _propagate_inherited_constraints(self, graph: SignalGraph, result: ClassBuilderResult):
        """继承传播：子类继承父类的 CLASS_PROPERTY 和 CONSTRAINT_BLOCK
        
        规则:
        - 子类继承父类的 CLASS_PROPERTY (复制为 child.prop)
        - 子类继承父类的 CONSTRAINT_BLOCK (复制为 child.constraint_name)
        - 约束内部的边 (HAS_LHS, HAS_CONDITION 等) 也复制
        - 同名属性/约束不覆盖（子类优先）
        """
        for cls_name in list(self.hierarchy._parent_map.keys()):
            ancestors = self.hierarchy.get_ancestors(cls_name)
            if not ancestors:
                continue
            
            for ancestor in ancestors:
                # 复制父类的 CLASS_PROPERTY
                for node_id in list(graph.nodes()):
                    node = graph.get_node(node_id)
                    if node is None:
                        continue
                    
                    # 匹配 ancestor.xxx 格式的 CLASS_PROPERTY
                    if node.kind == NodeKind.CLASS_PROPERTY and node_id.startswith(f"{ancestor}."):
                        prop_name = node_id[len(ancestor) + 1:]
                        child_prop_id = f"{cls_name}.{prop_name}"
                        
                        # 跳过：子类已有同名属性
                        if graph.get_node(child_prop_id) is not None:
                            continue
                        
                        # 跳过：如果属性名含 :: 说明是约束子节点，不复制
                        if '::' in prop_name:
                            continue
                        
                        # 创建子类的继承属性节点
                        child_prop = TraceNode(
                            id=child_prop_id,
                            name=prop_name,
                            module=cls_name,
                            kind=NodeKind.CLASS_PROPERTY,
                            width=node.width,
                        )
                        graph.add_trace_node(child_prop)
                        result.nodes.append(child_prop)
                        
                        # CLASS -> CLASS_PROPERTY 边
                        graph.add_trace_edge(TraceEdge(
                            src=cls_name,
                            dst=child_prop_id,
                            kind=EdgeKind.CONSTRAINS,
                        ))
                    
                    # 匹配 ancestor.constraint_name 格式的 CONSTRAINT_BLOCK
                    elif node.kind == NodeKind.CONSTRAINT_BLOCK and node_id.startswith(f"{ancestor}."):
                        constr_name = node_id[len(ancestor) + 1:]
                        child_constr_id = f"{cls_name}.{constr_name}"
                        
                        # 跳过：子类已有同名约束
                        if graph.get_node(child_constr_id) is not None:
                            continue
                        
                        # 复制约束块及其子树
                        self._copy_constraint_subtree(graph, node_id, ancestor, cls_name, result)

    # =========================================================================
    # [铁律15] 每个语法节点类型 → 独立方法
    # =========================================================================

    def _build_class_nodes(self, graph, cls, cls_name: str, result: ClassBuilderResult):
        """处理单个 ClassDeclaration"""
        if cls is None:
            return

        # CLASS 节点
        cls_node = TraceNode(
            id=cls_name,
            name=cls_name,
            module=cls_name,
            kind=NodeKind.CLASS,
            width=(0, 0),
        )
        graph.add_trace_node(cls_node)
        result.nodes.append(cls_node)

        # CLASS_PROPERTY 节点（rand 变量 + 普通成员变量）
        for prop in self._iter_class_properties(cls):
            self._build_class_property(graph, prop, cls_name, result)

        # CONSTRAINT_BLOCK 节点 + 内部结构
        for constr in self._iter_constraints(cls):
            self._build_constraint_block(graph, constr, cls_name, result)

    def _build_class_property(self, graph, prop, cls_name: str, result: ClassBuilderResult):
        """"[铁律15] 处理 ClassPropertyDeclaration → CLASS_PROPERTY 节点

        金标准: bit b1, b2, b3; → 每个变量独立节点
        """
        decl = getattr(prop, 'declaration', None)
        if decl is None:
            return

        # 支持 multi-declarator: bit b1, b2, b3;
        for d in self._iter_declarators(decl):
            prop_name = self._get_declarator_name(d)
            if not prop_name:
                continue

            node_id = f"{cls_name}.{prop_name}"
            width = self._property_width(prop)


            node = TraceNode(
                id=node_id,
                name=prop_name,
                module=cls_name,
                kind=NodeKind.CLASS_PROPERTY,
                width=width,
            )
            graph.add_trace_node(node)
            result.nodes.append(node)

            # CLASS → CLASS_PROPERTY 边（归属关系）
            graph.add_trace_edge(TraceEdge(
                src=cls_name,
                dst=node_id,
                kind=EdgeKind.CONSTRAINS,
            ))

            # 如果是类引用 (NamedType)，添加 IS_INSTANCE_OF 边
            type_node = getattr(decl, 'type', None)
            if type_node and getattr(type_node, 'kind') == SyntaxKind.NamedType:
                # NamedType.name 是 IdentifierNameSyntax，str() 获取类名
                name_attr = getattr(type_node, 'name', None)
                type_name = str(name_attr).strip() if name_attr else ''
                if type_name:
                    graph.add_trace_edge(TraceEdge(
                        src=node_id,
                        dst=type_name,
                        kind=EdgeKind.IS_INSTANCE_OF,
                    ))

    def _build_constraint_block(self, graph, constr, cls_name: str, result: ClassBuilderResult):
        """[铁律15] 处理 ConstraintDeclaration → CONSTRAINT_BLOCK

        金标准节点 ID: "packet.c"（class.constraint_name）
        """
        constr_name = getattr(constr, 'name', None)
        if constr_name is None:
            constr_name = ""
        constr_name = str(constr_name).strip()
        if not constr_name:
            return

        block_id = f"{cls_name}.{constr_name}"
        constraint_block_node = TraceNode(
            id=block_id,
            name=constr_name,
            module=cls_name,
            kind=NodeKind.CONSTRAINT_BLOCK,
            width=(0, 0),
        )
        graph.add_trace_node(constraint_block_node)
        result.nodes.append(constraint_block_node)

        # CLASS → CONSTRAINT_BLOCK 边
        graph.add_trace_edge(TraceEdge(
            src=cls_name,
            dst=block_id,
            kind=EdgeKind.CONSTRAINS,
        ))

        # 处理 constraint block 内的每条表达式
        block = getattr(constr, 'block', None)
        if block is None:
            return

        # 收集此 block 直接引用的 CLASS_PROPERTY（用于 CONSTRAINS 边）
        block_direct_vars: Set[str] = set()

        for idx, item in enumerate(getattr(block, 'items', [])):
            if item is None:
                continue
            self._cv.reset()
            self._cv.visit(item)
            vars = self._cv.variables

            # 变量名 → CLASS_PROPERTY 节点 ID
            for v in vars:
                if v in ['this', 'super']:  # 跳过 this/super 关键字
                    continue
                prop_id = f"{cls_name}.{v}" if not v.startswith(f"{cls_name}.") else v
                block_direct_vars.add(prop_id)

            # 为每条 constraint 表达式建节点
            kind_str = str(getattr(item, 'kind', ''))

            if 'ConditionalConstraint' in kind_str:
                self._build_conditional_constraint(graph, item, block_id, cls_name, idx, block_direct_vars, result)
            elif 'ImplicationConstraint' in kind_str:
                self._build_implication_constraint(graph, item, block_id, cls_name, idx, block_direct_vars, result)
            elif 'UniquenessConstraint' in kind_str:
                self._build_uniqueness_constraint(graph, item, block_id, cls_name, idx, block_direct_vars, result)
            elif 'SolveBeforeConstraint' in kind_str:
                self._build_solve_before_constraint(graph, item, block_id, cls_name, idx, block_direct_vars, result)
            elif 'ForeachConstraint' in kind_str or 'LoopConstraint' in kind_str:
                self._build_foreach_constraint(graph, item, block_id, cls_name, idx, block_direct_vars, result)
            elif 'ExpressionConstraint' in kind_str:
                # 检查是否是 super.<constraint_name> 调用（增量扩展）
                item_str = str(item).strip()
                if item_str.startswith('super.'):
                    # 提取被调用的父类约束名
                    # 格式: "super.c1;" → "c1"
                    super_call_name = item_str.split('.')[1].rstrip(';').strip()
                    # 在父类中查找同名约束
                    parent = self.hierarchy.get_parent(cls_name)
                    if parent:
                        parent_constr_id = f"{parent}.{super_call_name}"
                        graph.add_trace_edge(TraceEdge(
                            src=f"{block_id}::expr_{idx}",
                            dst=parent_constr_id,
                            kind=EdgeKind.SUPER_CALL,
                        ))
                        # super.c1 不引用普通变量，跳过变量处理
                        continue
                self._build_expression_constraint(graph, item, block_id, cls_name, idx, block_direct_vars, result)

        # CONSTRAINT_BLOCK → 直接引用的 CLASS_PROPERTY 边（CONSTRAINS）
        for prop_id in block_direct_vars:
            existing = graph.get_edge(block_id, prop_id)
            if existing is None:
                graph.add_trace_edge(TraceEdge(
                    src=block_id,
                    dst=prop_id,
                    kind=EdgeKind.CONSTRAINS,
                ))

    def _build_conditional_constraint(self, graph, node, block_id, cls_name, idx, direct_vars, result):
        """[铁律15] 处理 ConditionalConstraint → CONSTRAINT_IF + CONSTRAINT_ELSE

        RTL: if (en) addr == 1; else addr == 2;
        创建:
          - CONSTRAINT_IF: block_id::if_0
          - HAS_CONDITION 边 → 条件变量 CLASS_PROPERTY
          - CONSTRAINT_EXPR: block_id::if_0::cons_0 (consequent)
          - CONSTRAINT_EXPR: block_id::if_0::alt_0 (alternate)
          - HAS_CONSEQUENT / HAS_ALTERNATE 边
        """
        if_node_id = f"{block_id}::if_{idx}"
        if_node = TraceNode(
            id=if_node_id,
            name=f"if_{idx}",
            module=cls_name,
            kind=NodeKind.CONSTRAINT_IF,
            width=(0, 0),
        )
        graph.add_trace_node(if_node)
        result.nodes.append(if_node)

        # BLOCK → IF 边
        graph.add_trace_edge(TraceEdge(
            src=block_id,
            dst=if_node_id,
            kind=EdgeKind.CONSTRAINS,
        ))

        # 提取条件变量
        condition = getattr(node, 'condition', None)
        cond_vars = self._cv._extract_vars_from_expr(condition)
        for v in cond_vars:
            if v in ['this', 'super']:
                continue
            cond_prop_id = f"{cls_name}.{v}"
            graph.add_trace_edge(TraceEdge(
                src=if_node_id,
                dst=cond_prop_id,
                kind=EdgeKind.HAS_CONDITION,
            ))
            direct_vars.add(cond_prop_id)

        # consequent: ExpressionConstraint 或 ConstraintBlock（多语句）
        consequent = getattr(node, 'constraints', None)
        if consequent is None:
            return

        consequent_kind = str(getattr(consequent, 'kind', ''))

        if 'ConstraintBlock' in consequent_kind:
            # 多语句 if 块：展平为多个 CONSTRAINT_EXPR
            if hasattr(consequent, 'items'):
                for ci, cons_item in enumerate(consequent.items):
                    cons_node_id = f"{if_node_id}::cons_{ci}"
                    cons_node = TraceNode(
                        id=cons_node_id,
                        name=f"cons_{ci}",
                        module=cls_name,
                        kind=NodeKind.CONSTRAINT_EXPR,
                        width=(0, 0),
                    )
                    graph.add_trace_node(cons_node)
                    result.nodes.append(cons_node)
                    graph.add_trace_edge(TraceEdge(
                        src=if_node_id,
                        dst=cons_node_id,
                        kind=EdgeKind.HAS_CONSEQUENT,
                    ))
                    # 提取变量
                    self._cv.reset()
                    self._cv.visit(cons_item)
                    for v in self._cv.variables:
                        if v in ['this', 'super']:
                            continue
                        prop_id = f"{cls_name}.{v}"
                        direct_vars.add(prop_id)
                        graph.add_trace_edge(TraceEdge(
                            src=cons_node_id,
                            dst=prop_id,
                            kind=EdgeKind.HAS_LHS,
                        ))
        elif 'ExpressionConstraint' in consequent_kind:
            # 单语句
            cons_node_id = f"{if_node_id}::cons_0"
            cons_node = TraceNode(
                id=cons_node_id,
                name=f"cons_0",
                module=cls_name,
                kind=NodeKind.CONSTRAINT_EXPR,
                width=(0, 0),
            )
            graph.add_trace_node(cons_node)
            result.nodes.append(cons_node)
            graph.add_trace_edge(TraceEdge(
                src=if_node_id,
                dst=cons_node_id,
                kind=EdgeKind.HAS_CONSEQUENT,
            ))
            # 提取 consequent 引用的变量
            self._cv.reset()
            self._cv.visit(consequent)
            for v in self._cv.variables:
                if v in ['this', 'super']:
                    continue
                prop_id = f"{cls_name}.{v}"
                direct_vars.add(prop_id)
                graph.add_trace_edge(TraceEdge(
                    src=cons_node_id,
                    dst=prop_id,
                    kind=EdgeKind.HAS_LHS,
                ))

        # else: ElseConstraintClause
        else_clause = getattr(node, 'elseClause', None)
        if else_clause:
            alt_node_id = f"{if_node_id}::alt_0"
            alt_node = TraceNode(
                id=alt_node_id,
                name=f"alt_0",
                module=cls_name,
                kind=NodeKind.CONSTRAINT_ELSE,
                width=(0, 0),
            )
            graph.add_trace_node(alt_node)
            result.nodes.append(alt_node)
            graph.add_trace_edge(TraceEdge(
                src=if_node_id,
                dst=alt_node_id,
                kind=EdgeKind.HAS_ALTERNATE,
            ))
            # else 中的 constraints（ConstraintBlock 多语句或单 ExpressionConstraint）
            alt_constraints = getattr(else_clause, 'constraints', None)
            if alt_constraints is None:
                pass  # No else constraints
            else:
                alt_kind = str(getattr(alt_constraints, 'kind', ''))

            if 'ConstraintBlock' in alt_kind:
                # 多语句 else 块：展平为多个 CONSTRAINT_EXPR
                if hasattr(alt_constraints, 'items'):
                    for ai, alt_item in enumerate(alt_constraints.items):
                        alt_expr_id = f"{alt_node_id}::expr_{ai}"
                        alt_expr_node = TraceNode(
                            id=alt_expr_id,
                            name=f"expr_{ai}",
                            module=cls_name,
                            kind=NodeKind.CONSTRAINT_EXPR,
                            width=(0, 0),
                        )
                        graph.add_trace_node(alt_expr_node)
                        result.nodes.append(alt_expr_node)
                        graph.add_trace_edge(TraceEdge(
                            src=alt_node_id,
                            dst=alt_expr_id,
                            kind=EdgeKind.HAS_CONSEQUENT,
                        ))
                        self._cv.reset()
                        self._cv.visit(alt_item)
                        for v in self._cv.variables:
                            if v in ['this', 'super']:
                                continue
                            prop_id = f"{cls_name}.{v}"
                            direct_vars.add(prop_id)
                            graph.add_trace_edge(TraceEdge(
                                src=alt_expr_id,
                                dst=prop_id,
                                kind=EdgeKind.HAS_LHS,
                            ))
            elif 'ExpressionConstraint' in alt_kind:
                alt_expr_id = f"{alt_node_id}::expr_0"
                alt_expr_node = TraceNode(
                    id=alt_expr_id,
                    name=f"expr_0",
                    module=cls_name,
                    kind=NodeKind.CONSTRAINT_EXPR,
                    width=(0, 0),
                )
                graph.add_trace_node(alt_expr_node)
                result.nodes.append(alt_expr_node)
                graph.add_trace_edge(TraceEdge(
                    src=alt_node_id,
                    dst=alt_expr_id,
                    kind=EdgeKind.HAS_CONSEQUENT,
                ))
                self._cv.reset()
                self._cv.visit(alt_constraints)
                for v in self._cv.variables:
                    if v in ['this', 'super']:
                        continue
                    prop_id = f"{cls_name}.{v}"
                    direct_vars.add(prop_id)
                    graph.add_trace_edge(TraceEdge(
                        src=alt_expr_id,
                        dst=prop_id,
                        kind=EdgeKind.HAS_LHS,
                    ))

    def _build_implication_constraint(self, graph, node, block_id, cls_name, idx, direct_vars, result):
        """"[铁律15] 处理 ImplicationConstraint → CONSTRAINT_IMPLIES + HAS_CONDITION/HAS_CONSEQUENT

        RTL: constraint c { b1 == 5 -> b2 == 10; }
        创建:
          - CONSTRAINT_IMPLIES 节点: block_id::impl_{idx}
          - HAS_CONDITION 边 → 左部变量 (b1)
          - CONSTRAINT_EXPR 节点: block_id::impl_{idx}::result (右部结果)
          - HAS_CONSEQUENT 边 → result 节点
          - HAS_LHS 边 → 右部变量 (b2)
        """
        implies_node_id = f"{block_id}::impl_{idx}"
        implies_node = TraceNode(
            id=implies_node_id,
            name=f"impl_{idx}",
            module=cls_name,
            kind=NodeKind.CONSTRAINT_IMPLIES,
            width=(0, 0),
        )
        graph.add_trace_node(implies_node)
        result.nodes.append(implies_node)
        graph.add_trace_edge(TraceEdge(
            src=block_id,
            dst=implies_node_id,
            kind=EdgeKind.CONSTRAINS,
        ))

        # 提取左部（条件）和右部（结果）
        left = getattr(node, 'left', None)
        right = getattr(node, 'constraints', None)

        # 左部变量 → HAS_CONDITION 边
        if left:
            left_vars = self._cv._extract_vars_from_expr(left)
            for v in left_vars:
                if v in ['this', 'super']:
                    continue
                prop_id = f"{cls_name}.{v}"
                graph.add_trace_edge(TraceEdge(
                    src=implies_node_id,
                    dst=prop_id,
                    kind=EdgeKind.HAS_CONDITION,
                ))
                direct_vars.add(prop_id)

        # 右部：ConstraintBlock（多语句）或单 ExpressionConstraint
        if right:
            right_kind = str(getattr(right, 'kind', ''))

            if 'ConstraintBlock' in right_kind:
                # 多语句 block：展平为多个 CONSTRAINT_EXPR
                if hasattr(right, 'items'):
                    for ri, right_item in enumerate(right.items):
                        right_item_node_id = f"{implies_node_id}::result_{ri}"
                        right_item_node = TraceNode(
                            id=right_item_node_id,
                            name=f"result_{ri}",
                            module=cls_name,
                            kind=NodeKind.CONSTRAINT_EXPR,
                            width=(0, 0),
                        )
                        graph.add_trace_node(right_item_node)
                        result.nodes.append(right_item_node)
                        graph.add_trace_edge(TraceEdge(
                            src=implies_node_id,
                            dst=right_item_node_id,
                            kind=EdgeKind.HAS_CONSEQUENT,
                        ))
                        # 提取变量
                        self._cv.reset()
                        self._cv.visit(right_item)
                        for v in self._cv.variables:
                            if v in ['this', 'super']:
                                continue
                            prop_id = f"{cls_name}.{v}"
                            direct_vars.add(prop_id)
                            graph.add_trace_edge(TraceEdge(
                                src=right_item_node_id,
                                dst=prop_id,
                                kind=EdgeKind.HAS_LHS,
                            ))
            else:
                # 单语句
                result_node_id = f"{implies_node_id}::result"
                result_node = TraceNode(
                    id=result_node_id,
                    name="result",
                    module=cls_name,
                    kind=NodeKind.CONSTRAINT_EXPR,
                    width=(0, 0),
                )
                graph.add_trace_node(result_node)
                result.nodes.append(result_node)
                graph.add_trace_edge(TraceEdge(
                    src=implies_node_id,
                    dst=result_node_id,
                    kind=EdgeKind.HAS_CONSEQUENT,
                ))

                # 右部变量 → HAS_LHS 边
                right_vars = self._cv._extract_vars_from_expr(right)
                for v in right_vars:
                    if v in ['this', 'super']:
                        continue
                    prop_id = f"{cls_name}.{v}"
                    direct_vars.add(prop_id)
                    graph.add_trace_edge(TraceEdge(
                        src=result_node_id,
                        dst=prop_id,
                        kind=EdgeKind.HAS_LHS,
                    ))

    def _build_expression_constraint(self, graph, node, block_id, cls_name, idx, direct_vars, result):
        """[铁律15] 处理 ExpressionConstraint → CONSTRAINT_EXPR"""
        expr_node_id = f"{block_id}::expr_{idx}"
        expr_node = TraceNode(
            id=expr_node_id,
            name=f"expr_{idx}",
            module=cls_name,
            kind=NodeKind.CONSTRAINT_EXPR,
            width=(0, 0),
        )
        graph.add_trace_node(expr_node)
        result.nodes.append(expr_node)
        graph.add_trace_edge(TraceEdge(
            src=block_id,
            dst=expr_node_id,
            kind=EdgeKind.CONSTRAINS,
        ))

        self._cv.reset()
        self._cv.visit(node)
        for v in self._cv.variables:
            if v in ['this', 'super']:
                continue
            prop_id = f"{cls_name}.{v}"
            direct_vars.add(prop_id)
            graph.add_trace_edge(TraceEdge(
                src=expr_node_id,
                dst=prop_id,
                kind=EdgeKind.HAS_LHS,
            ))

    def _build_uniqueness_constraint(self, graph, node, block_id, cls_name, idx, direct_vars, result):
        """[铁律15] 处理 UniquenessConstraint → CONSTRAINT_UNIQUE"""
        unique_node_id = f"{block_id}::unique_{idx}"
        unique_node = TraceNode(
            id=unique_node_id,
            name=f"unique_{idx}",
            module=cls_name,
            kind=NodeKind.CONSTRAINT_UNIQUE,
            width=(0, 0),
        )
        graph.add_trace_node(unique_node)
        result.nodes.append(unique_node)
        graph.add_trace_edge(TraceEdge(
            src=block_id,
            dst=unique_node_id,
            kind=EdgeKind.CONSTRAINS,
        ))

        self._cv.reset()
        self._cv.visit(node)
        for v in self._cv.variables:
            if v in ['this', 'super']:
                continue
            prop_id = f"{cls_name}.{v}"
            direct_vars.add(prop_id)
            graph.add_trace_edge(TraceEdge(
                src=unique_node_id,
                dst=prop_id,
                kind=EdgeKind.HAS_MEMBER,
            ))

    def _build_solve_before_constraint(self, graph, node, block_id, cls_name, idx, direct_vars, result):
        """[铁律15] 处理 SolveBeforeConstraint → CONSTRAINT_SOLVE"""
        solve_node_id = f"{block_id}::solve_{idx}"
        solve_node = TraceNode(
            id=solve_node_id,
            name=f"solve_{idx}",
            module=cls_name,
            kind=NodeKind.CONSTRAINT_SOLVE,
            width=(0, 0),
        )
        graph.add_trace_node(solve_node)
        result.nodes.append(solve_node)
        graph.add_trace_edge(TraceEdge(
            src=block_id,
            dst=solve_node_id,
            kind=EdgeKind.CONSTRAINS,
        ))

        self._cv.reset()
        self._cv.visit(node)
        for v in self._cv.variables:
            if v in ['this', 'super']:
                continue
            prop_id = f"{cls_name}.{v}"
            direct_vars.add(prop_id)
            graph.add_trace_edge(TraceEdge(
                src=solve_node_id,
                dst=prop_id,
                kind=EdgeKind.HAS_BEFORE,
            ))

    def _build_foreach_constraint(self, graph, node, block_id, cls_name, idx, direct_vars, result):
        """[铁律15] 处理 ForeachConstraint → CONSTRAINT_FOREACH
        
        结构: foreach (arr[i]) { ... }
        node.constraints 是 foreach body:
          - ExpressionConstraintSyntax: 单表达式
          - ConstraintBlockSyntax: 多语句块 (含 if/else 等)
        """
        foreach_node_id = f"{block_id}::foreach_{idx}"
        foreach_node = TraceNode(
            id=foreach_node_id,
            name=f"foreach_{idx}",
            module=cls_name,
            kind=NodeKind.CONSTRAINT_FOREACH,
            width=(0, 0),
        )
        graph.add_trace_node(foreach_node)
        result.nodes.append(foreach_node)
        graph.add_trace_edge(TraceEdge(
            src=block_id,
            dst=foreach_node_id,
            kind=EdgeKind.CONSTRAINS,
        ))

        # 提取循环变量（数组名）和循环索引变量
        loop_index_vars = set()  # 循环索引变量 (i, j 等)，不应创建为 CLASS_PROPERTY
        self._cv.reset()
        self._cv.visit(node)
        
        # 从 loopList 提取索引变量名
        loop_list = getattr(node, 'loopList', None)
        if loop_list and hasattr(loop_list, '__iter__'):
            in_bracket = False
            for elem in loop_list:
                elem_kind = str(getattr(elem, 'kind', ''))
                if 'OpenBracket' in elem_kind:
                    in_bracket = True
                elif 'CloseBracket' in elem_kind:
                    in_bracket = False
                elif in_bracket:
                    # 索引变量：IdentifierName 或 SeparatedList (包含简单标识符)
                    if 'Identifier' in elem_kind or 'Name' in elem_kind:
                        ident = getattr(elem, 'identifier', None)
                        if ident and hasattr(ident, 'value'):
                            loop_index_vars.add(str(ident.value).strip())
                    elif 'SeparatedList' in elem_kind:
                        # SeparatedList 包含索引变量名
                        text = str(elem).strip()
                        if text and text.isidentifier():
                            loop_index_vars.add(text)
        
        for v in self._cv.variables:
            if v in ['this', 'super'] or v in loop_index_vars:
                continue
            prop_id = f"{cls_name}.{v}"
            direct_vars.add(prop_id)
            graph.add_trace_edge(TraceEdge(
                src=foreach_node_id,
                dst=prop_id,
                kind=EdgeKind.HAS_LOOP_VAR,
            ))
        
        # 处理 foreach body
        body = getattr(node, 'constraints', None)
        if body is None:
            return
        
        body_kind = str(getattr(body, 'kind', ''))
        
        if 'ConstraintBlock' in body_kind:
            body_items = getattr(body, 'items', None)
            if body_items:
                for bi_idx, body_item in enumerate(body_items):
                    self._build_constraint_item(
                        graph, body_item, foreach_node_id, cls_name,
                        f"body_{bi_idx}", direct_vars, result, loop_index_vars
                    )
        elif 'ExpressionConstraint' in body_kind:
            self._build_constraint_item(
                graph, body, foreach_node_id, cls_name,
                "body_0", direct_vars, result, loop_index_vars
            )
        elif 'ConditionalConstraint' in body_kind:
            self._build_constraint_item(
                graph, body, foreach_node_id, cls_name,
                "body_0", direct_vars, result, loop_index_vars
            )
    
    def _build_constraint_item(self, graph, item, parent_id, cls_name, suffix, direct_vars, result, loop_index_vars=None):
        """通用约束项处理：根据 kind 分发到对应的 _build 方法
        
        用于 foreach body、嵌套约束等需要递归处理的场景。
        
        Args:
            loop_index_vars: 循环索引变量集合 (如 {'i', 'j'})，不创建为 CLASS_PROPERTY
        """
        if loop_index_vars is None:
            loop_index_vars = set()
        kind = str(getattr(item, 'kind', ''))
        
        if 'ConditionalConstraint' in kind:
            # if/else 约束
            if_node_id = f"{parent_id}::{suffix}_if"
            if_node = TraceNode(
                id=if_node_id,
                name=suffix,
                module=cls_name,
                kind=NodeKind.CONSTRAINT_IF,
                width=(0, 0),
            )
            graph.add_trace_node(if_node)
            result.nodes.append(if_node)
            graph.add_trace_edge(TraceEdge(
                src=parent_id,
                dst=if_node_id,
                kind=EdgeKind.CONSTRAINS,
            ))
            
            # 提取条件变量
            condition = getattr(item, 'condition', None)
            if condition:
                cond_vars = self._cv._extract_vars_from_expr(condition)
                for v in cond_vars:
                    if v in ['this', 'super'] or v in loop_index_vars:
                        continue
                    cond_prop_id = f"{cls_name}.{v}"
                    graph.add_trace_edge(TraceEdge(
                        src=if_node_id,
                        dst=cond_prop_id,
                        kind=EdgeKind.HAS_CONDITION,
                    ))
                    if v not in loop_index_vars: direct_vars.add(cond_prop_id)
            
            # consequent
            consequent = getattr(item, 'constraints', None)
            if consequent:
                cons_kind = str(getattr(consequent, 'kind', ''))
                if 'ConstraintBlock' in cons_kind:
                    if hasattr(consequent, 'items'):
                        for ci, cons_item in enumerate(consequent.items):
                            cons_node_id = f"{if_node_id}::cons_{ci}"
                            cons_node = TraceNode(
                                id=cons_node_id,
                                name=f"cons_{ci}",
                                module=cls_name,
                                kind=NodeKind.CONSTRAINT_EXPR,
                                width=(0, 0),
                            )
                            graph.add_trace_node(cons_node)
                            result.nodes.append(cons_node)
                            graph.add_trace_edge(TraceEdge(
                                src=if_node_id,
                                dst=cons_node_id,
                                kind=EdgeKind.HAS_CONSEQUENT,
                            ))
                            self._cv.reset()
                            self._cv.visit(cons_item)
                            for v in self._cv.variables:
                                if v in ['this', 'super'] or v in loop_index_vars:
                                    continue
                                prop_id = f"{cls_name}.{v}"
                                if v not in loop_index_vars: direct_vars.add(prop_id)
                                graph.add_trace_edge(TraceEdge(
                                    src=cons_node_id,
                                    dst=prop_id,
                                    kind=EdgeKind.HAS_LHS,
                                ))
                elif 'ExpressionConstraint' in cons_kind:
                    cons_node_id = f"{if_node_id}::cons_0"
                    cons_node = TraceNode(
                        id=cons_node_id,
                        name="cons_0",
                        module=cls_name,
                        kind=NodeKind.CONSTRAINT_EXPR,
                        width=(0, 0),
                    )
                    graph.add_trace_node(cons_node)
                    result.nodes.append(cons_node)
                    graph.add_trace_edge(TraceEdge(
                        src=if_node_id,
                        dst=cons_node_id,
                        kind=EdgeKind.HAS_CONSEQUENT,
                    ))
                    self._cv.reset()
                    self._cv.visit(consequent)
                    for v in self._cv.variables:
                        if v in ['this', 'super'] or v in loop_index_vars:
                            continue
                        prop_id = f"{cls_name}.{v}"
                        if v not in loop_index_vars: direct_vars.add(prop_id)
                        graph.add_trace_edge(TraceEdge(
                            src=cons_node_id,
                            dst=prop_id,
                            kind=EdgeKind.HAS_LHS,
                        ))
            
            # alternate (else)
            else_clause = getattr(item, 'elseClause', None)
            if else_clause:
                alt_constraints = getattr(else_clause, 'constraints', None)
                alt_node_id = f"{if_node_id}::alt_0"
                alt_node = TraceNode(
                    id=alt_node_id,
                    name="alt_0",
                    module=cls_name,
                    kind=NodeKind.CONSTRAINT_ELSE,
                    width=(0, 0),
                )
                graph.add_trace_node(alt_node)
                result.nodes.append(alt_node)
                graph.add_trace_edge(TraceEdge(
                    src=if_node_id,
                    dst=alt_node_id,
                    kind=EdgeKind.HAS_ALTERNATE,
                ))
                
                alt_constraints = getattr(else_clause, 'constraints', None)
                if alt_constraints:
                    ac_kind = str(getattr(alt_constraints, 'kind', ''))
                    if 'ConstraintBlock' in ac_kind and hasattr(alt_constraints, 'items'):
                        for ai, alt_item in enumerate(alt_constraints.items):
                            a_node_id = f"{alt_node_id}::expr_{ai}"
                            a_node = TraceNode(
                                id=a_node_id,
                                name=f"expr_{ai}",
                                module=cls_name,
                                kind=NodeKind.CONSTRAINT_EXPR,
                                width=(0, 0),
                            )
                            graph.add_trace_node(a_node)
                            result.nodes.append(a_node)
                            graph.add_trace_edge(TraceEdge(
                                src=alt_node_id,
                                dst=a_node_id,
                                kind=EdgeKind.HAS_CONSEQUENT,
                            ))
                            self._cv.reset()
                            self._cv.visit(alt_item)
                            for v in self._cv.variables:
                                if v in ['this', 'super'] or v in loop_index_vars:
                                    continue
                                prop_id = f"{cls_name}.{v}"
                                if v not in loop_index_vars: direct_vars.add(prop_id)
                                graph.add_trace_edge(TraceEdge(
                                    src=a_node_id,
                                    dst=prop_id,
                                    kind=EdgeKind.HAS_LHS,
                                ))
                    elif 'ExpressionConstraint' in ac_kind:
                        a_node_id = f"{alt_node_id}::expr_0"
                        a_node = TraceNode(
                            id=a_node_id,
                            name="expr_0",
                            module=cls_name,
                            kind=NodeKind.CONSTRAINT_EXPR,
                            width=(0, 0),
                        )
                        graph.add_trace_node(a_node)
                        result.nodes.append(a_node)
                        graph.add_trace_edge(TraceEdge(
                            src=alt_node_id,
                            dst=a_node_id,
                            kind=EdgeKind.HAS_CONSEQUENT,
                        ))
                        self._cv.reset()
                        self._cv.visit(alt_constraints)
                        for v in self._cv.variables:
                            if v in ['this', 'super'] or v in loop_index_vars:
                                continue
                            prop_id = f"{cls_name}.{v}"
                            if v not in loop_index_vars: direct_vars.add(prop_id)
                            graph.add_trace_edge(TraceEdge(
                                src=a_node_id,
                                dst=prop_id,
                                kind=EdgeKind.HAS_LHS,
                            ))
        
        elif 'ExpressionConstraint' in kind:
            # 单表达式
            expr_node_id = f"{parent_id}::{suffix}_expr"
            expr_node = TraceNode(
                id=expr_node_id,
                name=f"{suffix}_expr",
                module=cls_name,
                kind=NodeKind.CONSTRAINT_EXPR,
                width=(0, 0),
            )
            graph.add_trace_node(expr_node)
            result.nodes.append(expr_node)
            graph.add_trace_edge(TraceEdge(
                src=parent_id,
                dst=expr_node_id,
                kind=EdgeKind.CONSTRAINS,
            ))
            self._cv.reset()
            self._cv.visit(item)
            for v in self._cv.variables:
                if v in ['this', 'super'] or v in loop_index_vars:
                    continue
                prop_id = f"{cls_name}.{v}"
                if v not in loop_index_vars: direct_vars.add(prop_id)
                graph.add_trace_edge(TraceEdge(
                    src=expr_node_id,
                    dst=prop_id,
                    kind=EdgeKind.HAS_LHS,
                ))

    # =========================================================================
    # 辅助方法
    # =========================================================================

    def _copy_constraint_subtree(self, graph, src_id, src_cls, dst_cls, result):
        """复制约束子树：从 src_cls.constraint 复制到 dst_cls.constraint
        
        递归复制 CONSTRAINT_BLOCK 及其所有子节点和边。
        将节点 ID 中的 src_cls 前缀替换为 dst_cls。
        """
        src_node = graph.get_node(src_id)
        if src_node is None:
            return
        
        suffix = src_id[len(src_cls) + 1:]  # e.g., "c_base" or "c_base::expr_0"
        dst_id = f"{dst_cls}.{suffix}"
        
        # 跳过：目标已存在
        if graph.get_node(dst_id) is not None:
            return
        
        # 创建目标节点
        dst_node = TraceNode(
            id=dst_id,
            name=src_node.name,
            module=dst_cls,
            kind=src_node.kind,
            width=src_node.width,
        )
        graph.add_trace_node(dst_node)
        result.nodes.append(dst_node)
        
        # 复制从父类到此节点的归属边
        # e.g., base_packet --CONSTRAINS--> base_packet.c_base
        # 变为: dst_cls --CONSTRAINS--> dst_cls.c_base
        graph.add_trace_edge(TraceEdge(
            src=dst_cls,
            dst=dst_id,
            kind=EdgeKind.CONSTRAINS,
        ))
        
        # 遍历源节点的所有出边，复制并替换前缀
        for src2, dst2 in list(graph.edges()):
            if src2 != src_id:
                continue
            edge = graph.get_edge(src2, dst2)
            if edge is None:
                continue
            
            # 替换目标节点的前缀
            if dst2.startswith(f"{src_cls}."):
                dst2_suffix = dst2[len(src_cls) + 1:]
                new_dst = f"{dst_cls}.{dst2_suffix}"
                
                # 递归复制目标子树
                dst2_node = graph.get_node(dst2)
                if dst2_node is not None:
                    self._copy_constraint_subtree(graph, dst2, src_cls, dst_cls, result)
                
                # 复制边
                existing = graph.get_edge(dst_id, new_dst)
                if existing is None:
                    graph.add_trace_edge(TraceEdge(
                        src=dst_id,
                        dst=new_dst,
                        kind=edge.kind,
                        condition=edge.condition,
                        effective_condition=edge.effective_condition,
                    ))
            elif dst2.startswith(f"{src_cls}.") is False:
                # 指向父类属性的边，如 HAS_LHS --> base_packet.id
                # 替换为子类属性
                if dst2.startswith(f"{src_cls}."):
                    prop_suffix = dst2[len(src_cls) + 1:]
                    new_dst = f"{dst_cls}.{prop_suffix}"
                    existing = graph.get_edge(dst_id, new_dst)
                    if existing is None:
                        graph.add_trace_edge(TraceEdge(
                            src=dst_id,
                            dst=new_dst,
                            kind=edge.kind,
                            condition=edge.condition,
                            effective_condition=edge.effective_condition,
                        ))
    
    def _class_name(self, cls) -> str:
        """提取 class 名称"""
        name = getattr(cls, 'name', None)
        if name is None:
            return ""
        # name 是 Token 或字符串
        if hasattr(name, 'value'):
            return str(name.value).strip()
        return str(name).strip()

    def _class_extends(self, cls) -> Optional[str]:
        """提取 extends 子句"""
        # 方法1: 语义 AST (ClassType.baseClass)
        base_class = getattr(cls, 'baseClass', None)
        if base_class is not None:
            name = getattr(base_class, 'name', None)
            if name:
                return str(name).strip()
        
        # 方法2: 语法 AST (ClassDeclaration.extendsClause)
        extends_clause = getattr(cls, 'extendsClause', None)
        if extends_clause is None:
            # 尝试 syntax 节点
            syntax = getattr(cls, 'syntax', None)
            if syntax:
                extends_clause = getattr(syntax, 'extendsClause', None)
        if extends_clause is None:
            return None
        # extends 子句格式: "extends ParentName"
        text = str(extends_clause).strip()
        if text.startswith("extends"):
            parent = text[len("extends"):].strip().split()[0]
            return parent
        return None

    def _iter_class_properties(self, cls) -> List:
        """迭代 class 的所有成员变量（包括 rand）
        
        Semantic AST: ClassType 没有 items 属性，需要通过 cls.syntax.items 访问
        """
        # 优先从 syntax 获取（Semantic AST ClassType）
        items = getattr(cls, 'syntax', None) and getattr(cls.syntax, 'items', None)
        if items is None:
            items = getattr(cls, 'items', []) or []
        props = []
        for item in items:
            if item is None:
                continue
            kind = getattr(item, 'kind', None)
            if kind == SyntaxKind.ClassPropertyDeclaration:
                props.append(item)
        return props

    def _iter_constraints(self, cls) -> List:
        """迭代 class 的所有 constraint 块
        
        Semantic AST: ClassType 没有 items 属性，需要通过 cls.syntax.items 访问
        """
        # 优先从 syntax 获取（Semantic AST ClassType）
        items = getattr(cls, 'syntax', None) and getattr(cls.syntax, 'items', None)
        if items is None:
            items = getattr(cls, 'items', []) or []
        constrs = []
        for item in items:
            if item is None:
                continue
            kind = getattr(item, 'kind', None)
            if kind == SyntaxKind.ConstraintDeclaration:
                constrs.append(item)
        return constrs

    def _iter_declarators(self, decl):
        """"安全迭代 declarators，跳过逗号等 token"""
        declarators = getattr(decl, 'declarators', None)
        if not declarators:
            return []
        result = []
        for d in declarators:
            kind = getattr(d, 'kind', None)
            if kind is None or 'Declarator' not in str(kind):
                continue
            result.append(d)
        return result

    def _get_declarator_name(self, d) -> str:
        """"从 Declarator 提取变量名"""
        dn = getattr(d, 'name', None)
        if dn is None:
            return ""
        if hasattr(dn, 'value'):
            return str(dn.value).strip()
        return str(dn).strip()

    def _property_width(self, prop) -> tuple:
        """从 ClassPropertyDeclaration 提取位宽"""
        decl = getattr(prop, 'declaration', None)
        if decl is None:
            return (0, 0)
        data_type = getattr(decl, 'dataType', None) or getattr(decl, 'type', None)
        if data_type is None:
            return (0, 0)
        # 查找 dimensions
        dims = getattr(data_type, 'dimensions', None)
        if dims and hasattr(dims, '__iter__'):
            for dim in dims:
                if hasattr(dim, 'specifier'):
                    spec = dim.specifier
                    if hasattr(spec, 'selector'):
                        sel = spec.selector
                        if hasattr(sel, 'left') and hasattr(sel, 'right'):
                            try:
                                l = int(str(sel.left.literal))
                                r = int(str(sel.right.literal))
                                return (l, r)
                            except (ValueError, AttributeError):
                                pass
        return (0, 0)
