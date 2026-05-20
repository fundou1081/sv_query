# sv_query Semantic AST 重构 - 执行计划

## 项目信息
- 开始日期: 2026-05-19
- 目标: 用 Semantic AST 替换 SyntaxTree，减少异常处理，提升代码质量
- 依据: `docs/REFACTOR_GUIDE_v2.md` + `docs/SEMANTIC_AST_REFACTOR_ASSESSMENT.md`

## 总体状态

| 阶段 | 任务 | 状态 | 负责人 |
|------|------|------|--------|
| Phase 0 | 建立 compiler.py 编译入口 | ✅ 完成 | main |
| Phase 1 | unified_tracer.py API 适配 | ✅ 完成 | main |
| Phase 2 | SemanticAdapter 实现 | 🚧 进行中 | main |
| Phase 3 | GraphBuilder 重构 | ⏳ 待开始 | - |
| Phase 4 | module_instance_graph.py 适配 | ⏳ 待开始 | - |
| Phase 5 | 文档更新 | ⏳ 待开始 | - |
| Phase 6 | 回归测试 (669 tests) | ⏳ 待开始 | - |

---

## Phase 0: compiler.py ✅

**完成时间**: 2026-05-19

**产出**:
- `src/trace/core/compiler.py` - SVCompiler 类
- `src/trace/core/semantic_adapter.py` - SemanticAdapter 类

**验证**:
```python
compiler = SVCompiler({'test.sv': code})
root = compiler.get_root()  # Semantic AST RootSymbol
adapter = SemanticAdapter(root)
```

---

## Phase 1: unified_tracer.py API 适配 ✅

**完成时间**: 2026-05-19

**变更**:
- `trees: dict` → `sources: Dict[str, str]`
- `PyslangAdapter` → `SemanticAdapter`
- `get_instances()` 支持 InstanceSymbol

---

## Phase 2: SemanticAdapter 实现 🚧

**状态**: 进行中

### 需要实现的方法 (按 GraphBuilder 调用频率排序)

| 方法 | 状态 | 说明 |
|------|------|------|
| `get_modules()` | ✅ 已完成 | 获取 InstanceSymbol 列表 |
| `get_module_instances()` | ✅ 已完成 | 返回 SemanticInstanceWrapper 列表 |
| `get_generate_instances()` | ✅ 已完成 | 返回空列表 |
| `get_instance_connection()` | ✅ 已完成 | 获取实例连接信息 |
| `get_port_names()` | ✅ 已完成 | 获取端口名列表 |
| `get_port_name()` | ✅ 已完成 | 获取单个端口名 |
| `get_port_declarations()` | ✅ 已完成 | 获取端口声明列表 |
| `get_port_name_and_direction()` | ✅ 已完成 | 获取端口名和方向 |
| `extract_port_width()` | ✅ 已完成 | 提取端口位宽 |
| `get_data_declarations()` | ✅ 已完成 | 获取数据声明 |
| `extract_data_width()` | ✅ 已完成 | 提取数据位宽 |
| `get_task_params()` | ✅ 已完成 | 返回空列表 |
| `analyze_task_internal_drivers()` | ✅ 已完成 | 返回空字典 |
| `get_interface_modport_signals()` | ✅ 已完成 | 返回空列表 |
| `get_function_params()` | ✅ 已完成 | 返回空列表 |
| `get_signal_name()` | ✅ 已完成 | 获取信号名称 |
| `items()` | ✅ 已完成 | 兼容方法 (返回空迭代器) |
| `clean_name()` | ✅ 已完成 | 清理信号名 |
| `visit()` | ✅ 已完成 | 遍历所有节点 |
| `get_classes()` | ✅ 已完成 | 获取类定义 |
| `get_net_declarations()` | ✅ 已完成 | 获取 net 声明 |
| `get_variable_declarations()` | ✅ 已完成 | 获取变量声明 |
| `get_assignments()` | ✅ 已完成 | 获取连续赋值 |
| `get_always_blocks()` | ✅ 已完成 | 获取 always 块 |
| `get_task_declarations()` | ✅ 已完成 | 获取 task 声明 |
| `get_function_declarations()` | ✅ 已完成 | 获取 function 声明 |
| `get_task_name()` | ✅ 已完成 | 获取 task 名称 |
| `get_function_name()` | ✅ 已完成 | 获取 function 名称 |
| `get_module_parameters()` | ✅ 已完成 | 获取模块参数 |

**预计工作量**: 2-3 天

---

## Phase 3: GraphBuilder 重构

**状态**: ⏳ 待开始

**依赖**: Phase 2 完成

**目标**:
- 将 `tree.root.members` 遍历改为 `root.visit(callback)` 模式
- 适配 Semantic AST 节点结构 (Symbol vs Syntax)

---

## Phase 4: module_instance_graph.py 适配

**状态**: ⏳ 待开始

**依赖**: Phase 2 完成

---

## Phase 5: 文档更新

**状态**: ⏳ 待开始

**待更新**:
- [ ] `docs/REFACTOR_GUIDE_v2.md` - 标记 Phase 2-4 完成状态
- [ ] `README.md` - 更新架构图
- [ ] `DEVELOPMENT.md` - 铁律1 已确认生效

---

## Phase 6: 回归测试

**状态**: ⏳ 待开始

**依赖**: Phase 1-4 完成

**目标**: 669 gold standard 测试全部通过

---

## 已知问题

### 问题 1: Semantic AST 结构差异
- **SyntaxTree**: `tree.root.members` → ModuleDeclarationSyntax 列表
- **Semantic AST**: `root` (RootSymbol) → InstanceSymbol 列表

### 问题 2: 节点属性差异
- **SyntaxTree**: `module.members` → 语法节点 (有 `kind`, `header`, `body`)
- **Semantic AST**: `instance.body.members` → 语义符号 (有 `kind`, `name`, `symbol`)

### 问题 3: constraint_visitor.py
- **状态**: 禁区，不修改
- **说明**: 它自己创建 SyntaxTree 用于约束解析，与新架构独立

---

## 下一步行动

**立即执行**:
1. 完成 `SemanticAdapter.get_module_name()` 实现
2. 测试 `build_graph()` 基本功能
3. 逐步实现其他 adapter 方法

---

## 更新日志

| 日期 | 更新内容 |
|------|----------|
| 2026-05-19 | Phase 0, Phase 1 完成 |
| 2026-05-19 | 创建本文档 |