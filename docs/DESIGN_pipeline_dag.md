# #5 设计文档: UnifiedTracer build_graph 显式 DAG 管线

> **状态**: 设计定稿 (方案 C — 先设计文档, 后实施)
> **创建**: 2026-08-28 23:50
> **实施**: 已提交 `04a882f` (行为 1:1, 0 回归)
> **关联**: [ARCHITECTURE_TODOLIST #5](ARCHITECTURE_TODOLIST.md) / [iter_049](task_tree/iterations/iter_049_pipeline_dag.md)

---

## 🎯 目标

`build_graph` 原本是**隐式顺序调用链** (11 步 `self._xxx()` 依序执行)。
重构为**显式 DAG**: 每步声明 inputs/outputs, 拓扑排序保证依赖先执行。
收益:
1. 依赖关系**一目了然** (不再靠阅读顺序推断)
2. 新增步骤只需声明 inputs/outputs, `Pipeline.validate()` 抓配置错误
3. **结构上支持并行** (独立步骤将来可并发)
4. 与项目纪律一致: 显式优于隐式, 结构化数据优于字符串

---

## 📊 11 步盘点: inputs / outputs / 依赖

> **注意**: todolist 记录 "20 步" 是过时估计, 实际盘点是 **11 步**。

| # | 步骤 | 输入 (inputs) | 输出 (outputs) | 依赖说明 |
|---|---|---|---|---|
| 1 | **compile** | — | `root` | 起点: `get_root()` |
| 2 | **adapter** | `root` | `adapter` | SemanticAdapter 包装 root |
| 3 | **graph** | `adapter` | `graph` | GraphBuilder 构建主图 |
| 4 | **class** | `adapter`, `graph` | — (副作用) | ClassGraphBuilder 追加类子图 |
| 5 | **class_member** | `adapter`, `graph` | — (副作用) | 解析 class 实例成员访问 |
| 6 | **bit_select** | `adapter`, `graph` | — (副作用) | BitSelectHandler 处理位选 |
| 7 | **module_graph** | `adapter`, `graph` | `module_graph` | ModuleInstanceGraph 跨模块 |
| 8 | **path_resolver** | `graph`, `module_graph` | `path_resolver` | 路径解析 |
| 9 | **tracers** | `graph`, `module_graph` | — (副作用) | 初始化 4 个 tracer |
| 10 | **cond_ops** | `graph` | — (副作用) | emit OP_TERNARY/OP_CASE 节点 |
| 11 | **backfill** | `adapter`, `graph` | — (副作用) | 补 source_location |

### 依赖 DAG

```
compile → adapter → graph ┬→ class ─────────┐
                           ├→ class_member ──┤
                           ├→ bit_select ────┤
                           └→ module_graph → path_resolver → tracers
graph ─→ cond_ops
adapter + graph → backfill
```

### 可并行分析

| 组 | 步骤 | 只依赖 | 可并行? |
|---|---|---|---|
| A | class / class_member / bit_select | `graph` | ✅ 互相独立 |
| B | module_graph | `graph` | ✅ 与 A 组独立 |
| C | path_resolver / tracers | `graph` + `module_graph` | 需 B 完成后 |
| D | cond_ops / backfill | `graph` (+adapter) | ✅ 与 A/B 独立 |

**结论**: A/B/D 三组只依赖 graph, 结构上完全可并行。
但当前**全部串行执行** (GIL 限制下 pyslang 遍历并行收益有限), DAG 结构已就绪。

---

## 📐 设计: Pipeline + PipelineStep

### 新模块 `src/trace/core/pipeline.py`

```python
@dataclass
class PipelineStep:
    name: str
    run: Callable[[dict], Any]    # run(context) -> 产物 (副作用步返回 None)
    inputs: tuple[str, ...] = ()  # 需要的产物 key
    outputs: tuple[str, ...] = () # 产出的 key

class Pipeline:
    def __init__(self, steps: list[PipelineStep]):
        self.steps = steps
        self._validate_dag()        # 构造时校验

    def _validate_dag(self):
        # 1. 每个 output 唯一 producer (无重复)
        # 2. 每个 input 有 producer (无悬空依赖)

    def topological_order(self) -> list[PipelineStep]:
        # Kahn's algorithm; 死锁 (环/缺 producer) 抛 ValueError

    def run(self, context: dict | None = None) -> dict:
        # 按拓扑序执行, outputs 写入 context
```

### 关键设计决策

| 决策 | 选择 | 理由 |
|---|---|---|
| PipelineStep 结构 | name/run/inputs/outputs | 最小声明集, 满足验证+排序 |
| 产物传递 | context dict (按 key) | 与步解耦, 便于测试单步 |
| 副作用步 | outputs=() + run 修改 self/graph | 保持既有存储 (self._xxx) 不变 |
| 校验时机 | 构造时 _validate_dag | 尽早暴露配置错误 |
| 排序 | Kahn (拓扑序) | 经典, 稳定, 可检测死锁 |

### 行为 1:1 保证

- 拓扑序 == 原顺序 (compile→adapter→graph→class→...→backfill)
- 产物存储不变 (self._graph/_adapter/_module_graph/_path_resolver/_tracers)
- 副作用顺序不变 (class 先于 bit_select, module_graph 先于 tracers)

---

## 📋 实施要点 (已落地 `04a882f`)

1. `Pipeline`/`PipelineStep` 定义在 `src/trace/core/pipeline.py`
2. `build_graph` 内定义 11 个 `_step_*` 函数 + Pipeline 声明
3. `pipeline.run({"compiler": ...})` 执行
4. 缓存逻辑保留在 pipeline 之后 (不受影响)

### 实施失误记录 (iter_049)

`_step_compile` 错写 `return ctx["root"]` (读取) → KeyError → 353 失败。
正确: `return self._get_compiler().get_root()` (产出)。已修复。

---

## ✅ 验收

| 项 | 结果 |
|---|---|
| 全套回归 | integration 13→13 / cli 20→20 / unit 4→4 (沙箱) / truth 4 passed = 0 回归 |
| 4 探针 (assign/flatten/always/function) | byte-identical |
| ruff | pipeline.py All checks passed |
| Pipeline 单测 | 拓扑序正确 (a→{b,c} 排序) |

---

## 📌 待确认 (请审阅)

1. **11 步盘点是否符合你的预期** — todolist 写 "20 步", 实际 11 步 (已核实 build_graph 代码)
2. **可并行组 A/B/D** 是否需要现在并行执行, 还是保留串行 (结构就绪)
3. **副作用步 (outputs=())** 的处理方式是否可接受 — 它们修改 self/graph 而非返回产物
