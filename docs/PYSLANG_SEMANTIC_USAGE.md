# pyslang Semantic 使用模式 (PYSLANG_SEMANTIC_USAGE)

> 创建时间: 2026-08-27
> 状态: 活跃维护
> 目的: **规范本项目如何安全、正确地使用 pyslang semantic API**，沉淀 G1/G2/G3 及此前多轮踩坑得出的模式，避免后续开发重复探索/踩坑。
> 任务来源: [task 2] 用户 2026-08-27 13:28 — "缺少对于pyslang semantic 的使用模式"

---

## 0. 为什么需要这份文档

sv_query 的核心是**用 semantic AST 构建 SignalGraph**。pyslang 的 semantic API 与 syntax API 边界、可迭代性、异常行为、内存特性都与普通 Python 对象不同。过去多轮（PR1-7、F1/F1.2、G1/G2/G3）暴露了大量陷阱（mutex lock 死锁、UnicodeDecodeError、`isUninstantiated` 幻觉边、symbol 不可 setattr 等）。本文档把这些**沉淀为可复用的模式**。

---

## 1. 核心原则

### 1.1 一律走 Semantic，绝不 fallback 到 syntax 字符串

> AGENTS.md 纪律（2026-08-27 方豆确认）：**纯 semantic + 禁止 silent fallback**。

- 从 `SemanticAdapter`（它封装了 pyslang `Compilation`）拿 semantic symbol，不直接读源码字符串。
- `assign.assignment` 是 semantic 表达式；`assign.syntax` 是 syntax 树。**默认用 semantic**。
- 例外（G3, 2026-08-27）：`acc[N][?:0]` 非标准语法被 pyslang 标为 `InvalidExpression` 时，**不是 fallback**，而是**改 fixture / 明确跳过**（见 §5.5）。

### 1.2 通过 SemanticAdapter 访问，不直接碰 pyslang

`SemanticAdapter(root, compiler, target_module)` 是唯一门面。GraphBuilder/Extractor 只调 adapter 的 68 个方法，不直接 import pyslang 深层 API。这样：
- pyslang API 变动只改 adapter 一处
- 异常/内存问题可集中兜底（`_safe_str`, `_iter_children`, mutex 防护）

---

## 2. 遍历模式 (Iteration Patterns)

### 2.1 安全遍历 `_iter_children(node)`

```python
def _iter_children(self, node) -> list:
    # 1. 处理 __iter__ 可迭代
    # 2. 处理常见属性: members/body/statement/statements/left/right/expr/
    #                  condition/consequent/alternate
    # 3. 属性访问抛异常时, 检查 'mutex' in str(e).lower() → 吞掉 (pyslang 死锁防护)
```

**用途**: 通用递归遍历。重要：捕获 `mutex lock failed: Invalid argument`——
elaboration 不完整时 InstanceSymbol 属性访问会死锁，必须吞掉继续。

### 2.2 Generate 展开 (generate-for)

```python
# get_assignments 里的 generate for 递归:
if "GenerateBlockArray" in kind:
    genvar_name = loopVariable.name          # genvar 名 ('i')
    for entry in entries:
        if entry.isUninstantiated: continue   # [F1.2] 跳未实例化
        child_ctx[genvar_name] = int(entry.arrayIndex)   # genvar 值
        for child in self._iter_children(entry):
            find_assignments(child, child_ctx)
    return
```

**模式要点**:
- `GenerateBlockArray` → `entries`（每个 entry = arrayIndex 一个实例）
- `loopVariable.name` = genvar 名，`entry.arrayIndex` = genvar 值
- **必须 `isUninstantiated` filter**（generate if/case 的 false 分支仍 expose symbol，不 filter 会造幻觉边）

### 2.3 GenerateBlock (generate if/case 单块)

```python
if "GenerateBlock" in kind:
    if node.isUninstantiated: return   # [F1.2] false 分支必须跳过
    for child in self._iter_children(node):
        find_assignments(child, ctx)
    return
```

### 2.4 ProceduralBlock (always)

```python
if "ProceduralBlock" in kind:
    for child in self._iter_children(node):
        find_assignments(child, ctx)
    return
```

---

## 3. 上下文传递模式 (genvar_ctx)

### 3.1 为什么用 dict 而非给 symbol 加属性

**pyslang symbol 不可 setattr**（pybind11 冻结对象）。所以 genvar 上下文不能挂在 symbol 上。

### 3.2 模式: id-keyed dict

```python
self._genvar_context: dict[int, dict] = {}   # {id(assign): {genvar: value}}

# 在 get_assignments 递归时存入:
self._genvar_context[id(node)] = dict(ctx)   # node = ContinuousAssign / AssignmentExpression

# 下游读取:
def get_genvar_context(self, assign) -> dict:
    return self._genvar_context.get(id(assign), {})
```

**要点**: 用 `id(assign)` 做 key（对象身份），不是 name（name 不可靠，见下）。

### 3.3 用途：genvar 引用 substitute

driver_extractor 拿到 `.genvar_ctx` 后，把 expression 里 genvar 引用 substitute 成具体值：
`acc[i+1]` 在 gen_accum[1] 内 → `acc[2]`，而非合并成单一 `acc[i+1]` 节点。

---

## 4. 身份/去重模式 (Identity & Dedup)

### 4.1 用 id(node) 而非 name 做 dedup key

```python
# [PR1] name_str 依赖 pybind11 decode (随机成功/失败 → 不稳定)
# 正确: 用 id(node)
seen_ids = set()
if id(node) in seen_ids: return
seen_ids.add(id(node))
```

### 4.2 hierarchicalPath 用于区分 generate 内独立 symbol

```python
# [G3] generate-local 'wire prod' 4 个 entry 是 4 个独立 symbol
# 顶层有同名 module-level 'prod' (无 init) → get_net_declarations 只返回无 init 那个
hp = getattr(child, "hierarchicalPath", None)   # 'generate_loop.gen_accum[0].prod'
# 用 hp 当 node id → 4 个独立 node/edge/tree
```

**要点**: `hierarchicalPath` 自动给出完整路径，是区分 generate 内同名符号的权威手段（比自拼 name 可靠）。

---

## 5. 边界与已知陷阱 (Pitfalls)

### 5.1 mutex lock 死锁

elaboration 不完整时，InstanceSymbol 属性访问抛 `mutex lock failed: Invalid argument`。
必须捕获并吞掉（`_iter_children` 已处理）。注意：某些 native segfault 抛 `BaseException` 会绕过，无法防护。

### 5.2 UnicodeDecodeError

name/hierarchicalPath 的 pybind11 decode 可能随机失败 → 用 `_safe_str()` 兜底，失败返回 placeholder（`_anon_` / hex 形式）。

### 5.3 内存不足 (8GB MBA)

pyslang elaboration 内存不足时**静默失败**（不报 OOM error），表现为 graph 大小随机（270-4700）、UnicodeDecodeError、缺 module。
**解决**: 运行前 4GB 强分配回收 (`bytearray(4*1024**3)`) + `_check_memory_pressure()` 检测 swap > 2GB 告警。
详见 `docs/PYSLANG_MEMORY_ISSUE.md`。

### 5.4 isUninstantiated 幻觉边

generate if/case 的未实例化分支仍 expose symbol → 手动 filter，否则产生幻觉 driver 边。

### 5.5 InvalidExpression（非法语法）

非标准语法（如 `acc[N][?:0]`）被 pyslang **正确地**标为 `InvalidExpression`（left/right=None）。
**决策 (G3, 2026-08-27)**：不为非法语法 fallback，**改 fixture / 跳过**。因为语法本身非法，不该为它做兜底。

### 5.6 属性访问的通用防护

```python
_safe_attr(node, "name", None)      # 捕获 UnicodeDecodeError/TypeError/Exception
_safe_str(val)                       # str() 失败 → placeholder
str(getattr(node, "kind", ""))       # kind 转字符串判断 (contains 匹配)
```

---

## 6. SemanticAdapter 方法总览 (68 个)

| 分类 | 方法 | 说明 |
|------|------|------|
| 入口 | `__init__`, `root`, `parser`, `trees`, `items` | 构造 + 顶层访问 |
| 源码 | `get_source_location`, `get_source_text` | --show-source |
| 模块 | `get_modules`, `get_module_instances`, `get_module_name`, `_find_target_top` | 模块/实例 |
| class | `get_classes`, `get_class_name` | ClassGraph |
| interface | `get_interfaces`, `get_modport_declarations`, `get_modport_info`, `get_interface_modport_signals`, `get_interface_members` | interface/modport |
| generate | `get_generate_instances`, `get_generate_net_declarations` | [G3] generate 内 net | 
| 端口 | `get_instance_connection`, `get_port_declarations`, `get_port_names`, `get_port_name`, `get_port_name_and_direction`, `extract_port_width` | 端口 |
| 赋值 | `get_assignments`, `get_genvar_context`, `get_net_declarations`, `get_net_aliases`, `get_variable_declarations`, `get_data_declarations` | 赋值/net/var |
| 过程块 | `get_always_blocks`, `get_task_declarations`, `get_function_declarations`, `get_top_level_subroutines` | always/task/function |
| 信号 | `get_signal_name`, `extract_data_width`, `get_drivers`, `get_loads`, `extract_signals_from_expr`(私有 `_extract_signals_from_expr`) | 信号操作 |
| 函数 | `get_function_params`, `get_function_width`, `get_task_params`, `get_task_name`, `get_function_name`, `analyze_task_internal_drivers` | 函数/任务 |
| 参数 | `get_module_parameters` | parameter |
| 遍历 | `visit`, `visit_module`, `_iter_children`, `iter_modules`, `get_definition` | 通用 |
| 工具 | `clean_name`, `SemanticInstanceWrapper` | 名字清理/实例包装 |

---

## 7. 未来方向 (用户 2026-06-25 记录, 未实施)

pyslang 11.0.0 提供完整 native API 可简化很多当前手写逻辑：
- `root.topInstances`（顶层 InstanceSymbol 列表）
- `inst.hierarchicalPath`（自动完整路径，替代自拼）
- `inst.body`（InstanceBodySymbol, iterable children）
- `inst.portConnections`（端口连接列表，**替代 sv_query 自建 MIG**）
- `inst.visit(callback)`（visitor pattern）

**预期收益**: 性能 4x+（CVA6 265ms→60ms）、消除 namespace rewrite、代码更简单。

**⚠️ 暂不做，等用户指示**（2026-06-25 21:38 "先记录下来"）。
