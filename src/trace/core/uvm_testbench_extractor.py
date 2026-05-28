# uvm_testbench_extractor.py - UVM Testbench 静态骨架提取器
#
# 从 pyslang 语法树提取 UVM testbench 组件结构。
#
# [铁律15] Visitor 模式
# [铁律3] 不可信则不输出

import re
import logging
from typing import Dict, List, Optional, Tuple

import pyslang

from .graph.uvm_models import (
    UVMComponent, TLMConnection, SequenceBinding, UVMTestbench,
    FactoryOverride, ConfigDBEntry
)

logger = logging.getLogger(__name__)

# UVM 基类 → 组件类型映射
UVM_BASE_TYPE_MAP = {
    'uvm_driver': 'driver',
    'uvm_monitor': 'monitor',
    'uvm_sequencer': 'sequencer',
    'uvm_agent': 'agent',
    'uvm_env': 'env',
    'uvm_test': 'test',
    'uvm_scoreboard': 'scoreboard',
    'uvm_subscriber': 'subscriber',
    'uvm_sequence': 'sequence',
    'uvm_sequence_item': 'sequence_item',
}


class UVMTestbenchExtractor:
    """UVM Testbench 静态骨架提取器

    提取:
    - 组件层次 (type_id::create / new)
    - TLM 连接 (.connect)
    - Sequence → Sequencer 绑定
    - 继承关系
    """

    def __init__(self, sources: Dict[str, str]):
        self._sources = sources
        self._components: Dict[str, UVMComponent] = {}
        self._connections: List[TLMConnection] = []
        self._sequence_bindings: List[SequenceBinding] = []
        self._overrides: List[FactoryOverride] = []
        self._config_entries: List[ConfigDBEntry] = []
        self._class_hierarchy: Dict[str, str] = {}
        self._class_defs: Dict[str, object] = {}  # class_name → syntax node

    def extract(self) -> UVMTestbench:
        """提取 UVM testbench 结构"""
        for fname, source in self._sources.items():
            try:
                tree = pyslang.SyntaxTree.fromText(source)
                # Pass 1: 收集 class 定义和继承关系
                self._collect_class_defs(tree.root)
                # Pass 2: 提取组件创建和 TLM 连接
                self._extract_components(tree.root)
            except Exception as e:
                logger.warning(f"解析 {fname} 失败: {e}")

        return UVMTestbench(
            components=self._components,
            connections=self._connections,
            sequence_bindings=self._sequence_bindings,
            overrides=self._overrides,
            config_entries=self._config_entries,
            class_hierarchy=self._class_hierarchy,
        )

    # =========================================================================
    # Pass 1: 收集 class 定义
    # =========================================================================

    def _collect_class_defs(self, node):
        """收集 class 定义和继承关系"""
        kind = str(getattr(node, 'kind', ''))

        if 'ClassDeclaration' in kind:
            class_name = str(getattr(node, 'name', '')).strip()
            if class_name:
                self._class_defs[class_name] = node
                # 提取 extends
                extends = self._get_extends(node)
                if extends:
                    self._class_hierarchy[class_name] = extends

                # 推断组件类型
                base_class = extends or ''
                comp_type = self._infer_type(base_class)

                # 如果是 UVM 组件类型，创建一个"定义级"组件记录
                if comp_type and comp_type not in ('sequence', 'sequence_item'):
                    self._components[class_name] = UVMComponent(
                        name=class_name,
                        class_name=class_name,
                        base_class=base_class,
                        component_type=comp_type,
                    )
            return

        if 'Token' not in kind:
            try:
                for child in node:
                    self._collect_class_defs(child)
            except TypeError:
                pass

    def _get_extends(self, node) -> str:
        """提取 extends 父类名"""
        extends_clause = getattr(node, 'extendsClause', None)
        if extends_clause:
            text = str(extends_clause).strip()
            if text.startswith('extends'):
                parent = text[len('extends'):].strip().split()[0]
                return parent
        return ''

    def _infer_type(self, base_class: str) -> str:
        """从基类推断组件类型"""
        # 去掉参数化部分 uvm_driver#(xxx) → uvm_driver
        base = base_class.split('#')[0].strip() if base_class else ''
        return UVM_BASE_TYPE_MAP.get(base, '')

    # =========================================================================
    # Pass 2: 提取组件创建和 TLM 连接
    # =========================================================================

    def _extract_components(self, node):
        """提取组件创建和 TLM 连接"""
        kind = str(getattr(node, 'kind', ''))

        if 'ClassDeclaration' in kind:
            class_name = str(getattr(node, 'name', '')).strip()
            self._process_class(node, class_name)
            return

        if 'Token' not in kind:
            try:
                for child in node:
                    self._extract_components(child)
            except TypeError:
                pass

    def _process_class(self, node, class_name: str):
        """处理单个 class 的 build_phase 和 connect_phase"""
        # 递归查找 function/task 定义
        self._find_methods(node, class_name)

    def _find_methods(self, node, class_name: str):
        """递归查找 function/task 定义"""
        kind = str(getattr(node, 'kind', ''))

        if 'ClassMethod' in kind or 'FunctionDeclaration' in kind or 'TaskDeclaration' in kind:
            method_name = self._get_method_name(node)
            if method_name in ('build_phase', 'new'):
                self._process_build_phase(node, class_name)
            if method_name in ('connect_phase', 'new'):
                self._process_connect_phase(node, class_name)
            return

        if 'Token' not in kind:
            try:
                for child in node:
                    self._find_methods(child, class_name)
            except TypeError:
                pass

    def _get_method_name(self, node) -> str:
        """获取方法名"""
        for child in node:
            ck = str(getattr(child, 'kind', ''))
            if 'FunctionPrototype' in ck:
                return str(getattr(child, 'name', '')).strip()
            # FunctionDeclaration 包含 FunctionPrototype
            if 'Function' in ck or 'Task' in ck:
                name = self._get_method_name(child)
                if name:
                    return name
        return ''

    # =========================================================================
    # build_phase 处理
    # =========================================================================

    def _process_build_phase(self, node, class_name: str):
        """处理 build_phase 中的组件创建"""
        # 递归查找 create() 和 new() 调用
        self._find_creates(node, class_name)

    def _find_creates(self, node, class_name: str):
        """递归查找 create/new/uvm_config_db 调用"""
        kind = str(getattr(node, 'kind', ''))

        # AssignmentExpression: xxx = yyy::type_id::create("name", this)
        if 'Assignment' in kind:
            self._process_assignment(node, class_name)
            return

        # InvocationExpression: uvm_config_db#(...)::set(...)
        if 'Invocation' in kind:
            node_str = str(node)
            if 'set_type_override' in node_str:
                self._process_factory_override(node, class_name, 'type')
                return
            if 'set_inst_override' in node_str:
                self._process_factory_override(node, class_name, 'inst')
                return
            if 'uvm_config_db' in node_str:
                self._process_config_db(node, class_name)
                return

        if 'Token' not in kind:
            try:
                for child in node:
                    self._find_creates(child, class_name)
            except TypeError:
                pass

    def _process_assignment(self, node, class_name: str):
        """处理赋值语句中的 create/new/override/config_db"""
        node_str = str(node)

        # 检查 type_id::create
        if 'type_id::create' in node_str:
            self._process_type_id_create(node, class_name)
        # 检查 new(...)
        elif '.new(' in node_str or '= new(' in node_str:
            self._process_new_creation(node, class_name)
        # 检查 factory override
        elif 'set_type_override' in node_str:
            self._process_factory_override(node, class_name, 'type')
        elif 'set_inst_override' in node_str:
            self._process_factory_override(node, class_name, 'inst')
        # 检查 uvm_config_db::set
        elif 'uvm_config_db' in node_str:
            self._process_config_db(node, class_name)

    def _process_type_id_create(self, node, class_name: str):
        """处理 type_id::create 调用"""
        node_str = str(node)

        # 提取类名: xxx::type_id::create
        match = re.search(r'(\w+)::type_id::create\s*\(', node_str)
        if not match:
            return
        created_class = match.group(1)

        # 提取实例名: create("name", ...)
        name_match = re.search(r'create\s*\(\s*"(\w+)"', node_str)
        if not name_match:
            return
        instance_name = name_match.group(1)

        # 检查 parent 参数: create("name", this)
        parent = ''
        if 'this' in node_str:
            parent = class_name

        # 推断组件类型
        base_class = self._class_hierarchy.get(created_class, '')
        comp_type = self._infer_type(base_class) or self._infer_type(created_class)

        # 创建或更新组件
        if instance_name in self._components:
            comp = self._components[instance_name]
            comp.parent = parent
        else:
            self._components[instance_name] = UVMComponent(
                name=instance_name,
                class_name=created_class,
                base_class=base_class,
                component_type=comp_type,
                parent=parent,
            )

        # 更新父组件的 children
        if parent and parent in self._components:
            if instance_name not in self._components[parent].children:
                self._components[parent].children.append(instance_name)

    def _process_new_creation(self, node, class_name: str):
        """处理 new() 创建"""
        node_str = str(node)

        # 提取 new("name", ...) 参数
        match = re.search(r'new\s*\(\s*"(\w+)"', node_str)
        if not match:
            return
        instance_name = match.group(1)

        # 检查 parent 参数
        parent = ''
        if 'this' in node_str:
            parent = class_name

        # 提取赋值左侧变量名
        left_match = re.match(r'\s*(\w+)\s*=', node_str)
        var_name = left_match.group(1).strip() if left_match else instance_name

        # 从 class 定义中查找变量的声明类型
        var_type = self._find_var_type(class_name, var_name)

        # 创建或更新组件
        if instance_name in self._components:
            self._components[instance_name].parent = parent
            if var_type:
                self._components[instance_name].class_name = var_type
        else:
            self._components[instance_name] = UVMComponent(
                name=instance_name,
                class_name=var_type or var_name,
                base_class='',
                component_type=self._infer_type(var_type) if var_type else '',
                parent=parent,
            )

        if parent and parent in self._components:
            if instance_name not in self._components[parent].children:
                self._components[parent].children.append(instance_name)

    def _find_var_type(self, class_name: str, var_name: str) -> str:
        """从 class 定义中查找变量的声明类型

        例如: class top { producer #(packet) p1; } → p1 的类型是 producer
        """
        cls_node = self._class_defs.get(class_name)
        if cls_node is None:
            return ''

        # 递归查找 ClassPropertyDeclaration
        return self._search_var_type(cls_node, var_name)

    def _search_var_type(self, node, var_name: str) -> str:
        """递归搜索变量的声明类型"""
        kind = str(getattr(node, 'kind', ''))

        if 'ClassProperty' in kind or 'PropertyDeclaration' in kind:
            decl_str = str(node)
            # 模式: type varname;
            type_match = re.search(r'(\w+(?:\s*#\s*\([^)]+\))?)\s+(\w+)', decl_str)
            if type_match:
                vtype = type_match.group(1).strip().split()[0]
                vname = type_match.group(2).strip()
                if vname == var_name:
                    return vtype

        if 'Token' not in kind:
            try:
                for child in node:
                    result = self._search_var_type(child, var_name)
                    if result:
                        return result
            except TypeError:
                pass

        return ''

    # =========================================================================
    # connect_phase 处理
    # =========================================================================

    def _process_connect_phase(self, node, class_name: str):
        """处理 connect_phase 中的 .connect() 调用"""
        self._find_connects(node, class_name)

    def _process_sequence_config(self, node, class_name: str):
        """处理 uvm_config_db#(...)::set(..., "default_sequence", seq::get_type())"""
        node_str = str(node)

        # 提取 sequencer 路径: set(this, "path", ...)
        path_match = re.search(r'set\s*\([^,]+,\s*"([^"]+)"', node_str)
        if not path_match:
            return
        sequencer_path = path_match.group(1)

        # 提取 sequence 类名: xxx::get_type()
        seq_match = re.search(r'(\w+)::get_type\s*\(', node_str)
        if not seq_match:
            return
        sequence_class = seq_match.group(1)

        self._sequence_bindings.append(SequenceBinding(
            sequencer_path=sequencer_path,
            sequence_class=sequence_class,
        ))

    def _process_factory_override(self, node, class_name: str, override_type: str):
        """处理 factory override

        type: xxx::type_id::set_type_override(yyy::get_type())
        inst: xxx::type_id::set_inst_override(yyy::get_type(), "scope")
        """
        node_str = str(node)

        # 提取原始类型: xxx::type_id::set_type_override
        orig_match = re.search(r'(\w+)::type_id::set_(?:type|inst)_override', node_str)
        if not orig_match:
            return
        original = orig_match.group(1)

        # 提取覆盖类型: yyy::get_type()
        override_match = re.search(r'(\w+)::get_type\s*\(', node_str)
        if not override_match:
            return
        override_cls = override_match.group(1)

        # 提取 scope (inst override)
        scope = ''
        if override_type == 'inst':
            scope_match = re.search(r'"([^"]+)"\s*\)', node_str)
            if scope_match:
                scope = scope_match.group(1)

        self._overrides.append(FactoryOverride(
            original=original,
            override_type=override_cls,
            scope=scope,
        ))

    def _process_config_db(self, node, class_name: str):
        """处理 uvm_config_db#(...)::set(...) 条目"""
        node_str = str(node)

        # 提取值类型: uvm_config_db#(T)
        type_match = re.search(r'uvm_config_db#\(([^)]+)\)', node_str)
        value_type = type_match.group(1).strip() if type_match else ''

        # 提取 target path: set(this, "path", ...)
        path_match = re.search(r'set\s*\([^,]+,\s*"([^"]+)"', node_str)
        target_path = path_match.group(1) if path_match else ''

        # 提取 field name: set(this, "path", "field", ...)
        field_match = re.search(r'set\s*\([^,]+,\s*"[^"]+",\s*"([^"]+)"', node_str)
        field_name = field_match.group(1) if field_match else ''

        # 检查是否是 default_sequence (已有专门处理)
        if field_name == 'default_sequence':
            self._process_sequence_config(node, class_name)
            return

        if field_name:
            self._config_entries.append(ConfigDBEntry(
                context=class_name,
                target_path=target_path,
                field_name=field_name,
                value_type=value_type,
            ))

    def _find_connects(self, node, class_name: str):
        """递归查找 .connect() 调用"""
        kind = str(getattr(node, 'kind', ''))

        # ExpressionStatement 包含 .connect()
        if 'ExpressionStatement' in kind:
            node_str = str(node)
            if '.connect(' in node_str:
                self._process_connect_call(node, class_name)
                return  # ExpressionStatement 是叶子，处理完就返回

        if 'Token' not in kind:
            try:
                for child in node:
                    self._find_connects(child, class_name)
            except TypeError:
                pass

    def _process_connect_call(self, node, class_name: str):
        """处理 .connect(target) 调用"""
        node_str = str(node)

        # 提取 source.connect(target)
        match = re.search(r'(\w+(?:\.\w+)*)\.connect\s*\(\s*(\w+(?:\.\w+)*)', node_str)
        if not match:
            return

        source = match.group(1)
        target = match.group(2)

        # 解析完整路径
        source_path = self._resolve_path(source, class_name)
        target_path = self._resolve_path(target, class_name)

        # 推断端口类型
        port_type = self._infer_port_type(source_path, target_path)

        self._connections.append(TLMConnection(
            source_port=source_path,
            target_port=target_path,
            port_type=port_type,
        ))

    def _resolve_path(self, path: str, class_name: str) -> str:
        """解析端口完整路径

        agent.monitor.ap → 如果在 my_env 的 connect_phase 中，
        且 agent 是 my_env 的子组件，则完整路径为 agent.monitor.ap
        """
        # 当前实现: 直接返回路径（已经是相对于当前 class 的路径）
        return path

    def _infer_port_type(self, source: str, target: str) -> str:
        """推断端口类型"""
        source_lower = source.lower()
        target_lower = target.lower()

        if 'analysis' in source_lower or 'analysis' in target_lower:
            return 'analysis'
        if 'put' in source_lower or 'put' in target_lower:
            return 'put'
        if 'get' in source_lower or 'get' in target_lower:
            return 'get'
        if 'master' in source_lower or 'master' in target_lower:
            return 'master'
        if 'slave' in source_lower or 'slave' in target_lower:
            return 'slave'

        return ''
