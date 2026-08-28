# Iteration 049: #5 UnifiedTracer 管线 → 显式 DAG

**Metadata**:
- **Iteration #**: 049
- **Task Tree Level**: L1
- **Parent Task**: ARCHITECTURE_TODOLIST #5
- **Created**: 2026-08-28 23:10 GMT+8
- **Author**: 方豆 / DSH Agent
- **Outcome**: ✅ **成功** — 0 回归, 4 探针 byte-identical

---

## 🎯 本次目标

用户指令: **"继续"** → #5 把 build_graph 的隐式顺序链重构为显式 DAG。

---

## 🔬 盘点: 实际 11 步 (非记录的 20 步)

```
compile       : get_root()                       → root
adapter       : SemanticAdapter(root)            → adapter
graph         : GraphBuilder(adapter).build()    → graph
class         : ClassGraphBuilder(adapter).build(graph)
class_member  : _resolve_class_member_access(adapter, graph)
bit_select    : BitSelectHandler(adapter, graph).process()
module_graph  : ModuleInstanceGraph(adapter, graph).build()  → module_graph
path_resolver : PathResolver(graph, module_graph)            → path_resolver
tracers       : _init_tracers()
cond_ops      : _emit_conditional_op_nodes()
backfill      : _backfill_source_locations(adapter)
```

**依赖关系**:
- `compile → adapter → graph → {class, class_member, bit_select, module_graph}`
- `module_graph → path_resolver → tracers`
- `graph → {cond_ops, backfill}`
- **独立步骤**: class/class_member/bit_select 与 module_graph 只依赖 graph → 结构上可并行

---

## 🛠️ 设计: Pipeline + PipelineStep

新建 `src/trace/core/pipeline.py`:

```python
@dataclass
class PipelineStep:
    name: str
    run: Callable[[dict], Any]   # run(context) -> 产物
    inputs: tuple[str, ...] = ()  # 需要的产物 key
    outputs: tuple[str, ...] = () # 产出的 key

class Pipeline:
    - validate(): 检查每个 input 有 producer, 无重复 output
    - topological_order(): Kahn's algorithm
    - run(): 按拓扑序执行, 产物存 context
```

build_graph 里 11 步声明为 PipelineStep, 行为 1:1 一致。

---

## 🔴 实施失误 (诚实标注)

**`_step_compile` 错写**: 写成了 `return ctx["root"]` (读取) 而非 `return self._get_compiler().get_root()` (产出) → `KeyError: 'root'` → **353 个 integration 测试失败**。

错误信息 `KeyError: 'root'` 直接定位, 修复后 0 回归。

**教训**: PipelineStep 的 run 返回**产物**, 不是读产物。首步 (无 inputs) 尤其容易写错。
更好的防御: Pipeline 应该在首步无 inputs 时显式检查其 run 是否有产出。

---

## 📈 验证

| 项 | 结果 |
|---|---|
| `integration` | 13 failed (基线) = **0 回归** (修复前 353) |
| `cli` | 20 failed (先期) = **0 回归** |
| `unit` | 4 failed (沙箱) = **0 回归** |
| `test_case27_1to1_truth` | **4 passed** ✅ |
| 4 探针 (assign/flatten/always/function) | **byte-identical** ✅ |
| ruff | pipeline.py All checks passed; unified_tracer 无新引入 (B023 先期) |

---

## 💡 关键发现

1. **"20 步"是过时估计** — 实际 11 步。盘点后确认依赖链。
2. **DAG 结构已支持并行** — class/bit_select 与 module_graph 只依赖 graph,
   将来可并发 (GIL 限制下收益有限, 但结构已就绪)。
3. **显式依赖的价值** — 新增步骤只需声明 inputs/outputs, 依赖关系一目了然;
   validate() 在运行时抓出"input 无 producer"这类配置错误。

---

## 📌 后续

- 可选: 并行执行独立步骤 (需确认 pyslang GIL 行为)
- 可选: B023 (18 处先期) 清理
