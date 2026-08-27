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

## 6. SemanticAdapter 方法总览 (53 公开方法)

> 2026-08-27 Phase 1B 修正: 前版写"76 个"是按 def 总行数算的。subagent 严格按"外部可调用 class 方法"重数 = **53 个**。差额 23 = 6 嵌套 helper + 17 私有/dunder。

| 调用频次 | 标记 | 说明 |
|---|---|---|
| 🔥 > 5 文件 | 核心 API | 所有生产 extractor、CLI 都调用 |
| 高频 (2-5) | 正常使用 | 多个业务点调用 |
| 低频 / 单点 (1×) | 🔸 可能内部细节 | 只在 1 个调用点使用，需考察是否应合并 |
| 0 调用方 | ⚠️ UNUSED | 兼容性 stub / 后续可删 |

### 6.1 🔥 核心方法（按调用频次降序）

| 方法 | 调用文件数 | 主要调用方 |
|------|------|------|
| `get_modules` | 27× | 所有 9 个 extractor, CLI, tests |
| `get_port_declarations` | 13× | connection_extractor, driver_extractor, bit_select_handler, load_extractor, clock_domain_extractor, CLI |
| `get_module_name` | 13× | CLI (`arch`/`visualize`), manual scripts |
| `extract_port_width` | 10× | connection_extractor, bit_select_handler, driver_extractor, load_extractor, clock_domain_extractor, CLI |
| `get_port_name_and_direction` | 10× | driver_extractor, load_extractor, bit_select_handler, connection_extractor |
| `get_assignments` | 8× | driver_extractor, generate handling tests |
| `get_module_instances` | 8× | connection_extractor, module_instance_graph, graph_builder, unified_tracer |
| `get_classes` | 7× | ClassGraph, regression tests |
| `clean_name` | 6× | 5 个 extractor 全员使用（委托给 `_safe.clean_name`） |

### 6.2 高频方法 (2-5 调用方)

| 方法 | 频次 | 主要调用方 |
|------|------|------|
| `get_source_location` | 5× | driver_extractor, load_extractor, clock_domain_extractor, unified_tracer（--show-source） |
| `get_always_blocks` | 5× | driver_extractor, procedural_blocks test |
| `get_module_parameters` | 3× | driver_extractor, parameter_extraction tests |
| `get_genvar_context` | 2× | driver_extractor (line 1195), generate_handling tests |
| `get_source_text` | 2× | driver_extractor (line 1605, 1907, 2304) |
| `root` (@property) | 2× | graph_builder, trace_evidence |
| `get_variable_declarations` | 2× | driver_extractor (line 1119) |
| `get_data_declarations` | 2× | bit_select_handler, unified_tracer |
| `get_signal_name` | 2× | driver_extractor, unified_tracer |
| `extract_data_width` | 2× | bit_select_handler, driver_extractor |

### 6.3 🔸 低频 / 单点调用方（仅 1 个调用点）

| 方法 | 调用点 | 备注 |
|------|------|------|
| `get_function_name` | driver_extractor | 仅 function/task name 提取 |
| `parser` (@property) | connection_extractor (L112, L146) | 兼容性 wrapper，返回 self |
| `get_modport_info` | interface regression test |  |
| `get_generate_instances` | connection_extractor (L123, L147) | 与 `get_module_instances` 联用 |
| `get_function_declarations` | driver_extractor (L3318, L3716) |  |
| `get_task_params` | driver_extractor |  |
| `get_interface_modport_signals` | graph_builder (L711, L737) |  |
| `get_function_params` | driver_extractor |  |
| `get_interfaces` | interface regression test |  |
| `get_modport_declarations` | interface regression test |  |
| `get_instance_connection` | connection_extractor (L318) |  |
| `get_port_names` | clock_domain_extractor |  |
| `get_port_name` | bit_select_handler (L55) | 已被 `get_port_name_and_direction` 替代 |
| `get_task_declarations` | driver_extractor |  |
| `get_loads` | driver_extractor |  |
| `get_drivers` | driver_extractor |  |
| `extract_signals_from_expr` | — | 私有 helper；真实现是 `_extract_signals_from_expr` |
| `get_net_declarations` | driver_extractor | 与 `get_generate_net_declarations` 互补 |
| `get_net_aliases` | driver_extractor | alias 提取 |

### 6.4 ⚠️ UNUSED / 兼容性 stub（0 调用方）

前版 spec 列了但 subagent 严格反向 grep 发现这些方法**未被任何外部调用方使用**：

| 方法 | 判定 | 备注 |
|------|------|------|
| `get_visit` | ⛔ UNUSED | 文档列了但**完全未调用** |
| `get_top_level_subroutines` | ⛔ UNUSED | **完全未调用** |
| `get_class_name` | ⛔ UNUSED | **完全未调用** |
| `items` | ⛔ 兼容性 stub | 注释明示"返回空迭代器"；唯一 .items 调用是 `dict.items()` 链 |
| `trees` | ⛔ 兼容性 stub | 同 items |
| `get_port_name` | ⚠️ 已被替代 | 现有调用点建议改用 `get_port_name_and_direction` |

> **后续可作**: UNUSED 方法 + 已被替代的方法可在下一轮 deprecation 中移除。`items`/`trees` 是为了兼容旧代码留下的 stub，删除前确认无外部依赖。

### 6.5 不属于"公开 API"的内部构造（23 个）

| 类型 | 举例 | 说明 |
|------|------|------|
| 嵌套 helper | `_fix_unicode_class_names` | 仅在 `get_classes` 内部调用 |
| `_`-prefix | `_iter_children`/`_safe_str`/`_find_target_top`/`_collect_drivers_from_stmt`/`_extract_assignment_drivers`/`_extract_signals_from_expr` | 私有 helper，外部不推荐调用 |
| dunder | `__init__`/`__str__`/`__repr__` | 对象生命周期，不列入公开 API |
| `@property` 内部 | `parser` (wrapper) | 内部访问，不列入 public API |
| Wrapper 内部 | `SemanticInstanceWrapper`/`SemanticInstanceDeclWrapper` 的所有内部方法 | 包装器内部 |

> 加上以上项，`semantic_adapter.py` 总 `def` 行数 = 53 (公开) + 23 (内部) = 76。

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
