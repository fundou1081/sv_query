# Iteration 236: 1a — 实例/层级查询落地 (`instances` / `instance` / `connections` / `hierarchy`) + `graph` 补 `--filelist`

**Metadata**:
- **Iteration #**: 236
- **Task Tree Level**: L1
- **Parent Task**: `docs/task_tree/tasks/L1_cli_layering.md` (1a = 补 core 语义缺口)
- **Created**: 2026-09-09 GMT+8
- **Author**: 方豆 / AI 助手 (方豆: "先做 1a")
- **Outcome**: ✅ 成功 (4 个只读 JSON 命令上线 + graph 支持多文件; 顺带修 bug #6)

## 🎯 本次目标

补上方豆点名的能力缺口: **实例查询**。
库侧 `get_instances()` / MIG (`ModuleInstanceGraph`) 早已就绪, 但 **CLI 零暴露** ——
agent 只能靠 `arch show` / `visualize module` **看图**, 没法**问**"这设计里有哪些实例、它们怎么连"。
同时补 `graph` 组的 `--filelist` (此前只有 `--file`, **真实多文件项目完全用不了**)。

## 📦 交付

### 1. 四个新命令 (只读 + JSON, 全部登记 `core/semantic` + `recommended`)

| 命令 | 输出 | 复用 |
|---|---|---|
| `svq instances [--module M] [--depth N]` | `{count, instances:[{full_path,name,module_type,parent}]}` | `UnifiedTracer.get_instances()` |
| `svq instance <实例路径>` | 实例详情 + `children` + `ports[{port,direction,width,internal_signal}]` | `get_instances` + MIG |
| `svq connections <实例路径\|模块名>` | 实例 → 端口↔内部信号映射; 模块 → `inputs/outputs/internals/cross_module + confidence + caveats`; **输出带 `resolved_as`** | MIG / `trace_module` |
| `svq hierarchy [--module M] [--depth N]` | 实例层级树 (`tree[{full_path,module_type,children}]`) | `get_instances` 的 parent 链 |

设计取舍:
- `connections` 的**双语义**用 `resolved_as: "instance"|"module"` 显式声明, 不让 agent 猜; 目标都不匹配 → 结构化错误 + rc=1 (不静默返回空)
- 端口位宽输出为**结构化 list** (`[7,0]`), 不是字符串 `"[7:0]"` (符合 AGENTS "结构化数据优于字符串")
- 新增 `UnifiedTracer.get_module_graph()` 公开访问器 —— CLI 不再摸私有 `_module_graph`

### 2. `graph` 组补 `--filelist` (真实项目可用)

`graph dump/nodes/edges/find` 从"直读单文件"改为走统一的 `_build_tracer(file=..., filelist=...)`,
并接上 `handle_compilation_error` 统一错误处理。顺带修 JSON 契约小缺陷: `params.file` 不再输出字符串 `"None"`,
改为 `{file: null, filelist: "<path>"}`。

### 3. ⚠️ 修掉 pre-existing bug #6: `get_instances()` 从来没工作过

新测试首次调用该 API 即报:

```
AttributeError: 'SemanticAdapter' object has no attribute 'topInstances'
```

**两个叠加缺陷**:
1. `get_instances()` 里写的是 `SemanticAdapter(adapter)` —— 把 **SemanticAdapter 又包一层**,
   新 adapter 的 `_root` 是 SemanticAdapter 而非 pyslang root → 原生实例枚举 `self._root.topInstances` 直接炸;
2. 解析函数 `_parse_instance_node()` 按**原始 `InstanceSymbol`** 形状写 (`hasattr(node,'kind')`),
   而生产路径返回的是 `SemanticInstanceWrapper` (实测字段: `.name` / `.parent_module` / `.type.value` /
   `._symbol.hierarchicalPath`) → **即使不炸也永远解析不出东西**。

**修法 (根因)**: 直接调 `self._get_adapter().get_module_instances()`, 新增
`_instance_info_from_wrapper()` 按**实测 wrapper 形状**解析 (full_path 取 `hierarchicalPath`,
parent 由 full_path 去尾段 —— 比 `parent_module`(模块名) 更准, 数组/generate 场景不会错位);
**删除 76 行死代码** `_parse_instance_node` (从未生效且与生产形状不符)。

**为什么一直没人发现**: 该 API **零 CLI 调用方** (只有我上次的注册表"计划新增"注释提过它) ——
又一次印证 "没有调用方/测试覆盖的路径 = 事实上的死代码"。

## 📊 验证

| 项 | 结果 |
|---|---|
| 新测试 `test_cli_instance_query.py` | **14 passed** (JSON 契约 / 双语义 / 错误路径 / filelist / API 回归) |
| `check_cli_layers.py` | rc=0 (69 规范命令 + 30 别名 = 99 叶子, 0 违规) |
| 冒烟 | `instances` / `instance` / `connections`(两种) / `hierarchy` / `graph {nodes,edges,dump,find} --filelist` 全部 rc=0 |
| 真实项目口径 | `graph nodes --filelist scheduler_minimal/filelist.f` → **98 节点** (单文件时代此路不通) |
| 全量 canonical | 见提交记录 (预期 ≥3336, 0 退化) |

## 💡 关键发现 / 决策

1. **"补能力"往往先要修库**: 我原以为 4 个命令只是"把已有 API 包一层 CLI", 实际第一行就炸 ——
   库 API 从未被调用过 ⇒ 契约是**想象出来的**。教训: 声称"库已就绪"前必须先手动调一次。
2. **形状要靠探针确认, 不能靠 docstring**: `native_adapter` 的 docstring 写"输出含 id/def_name",
   实测 wrapper **没有**这两个字段, 真正可靠的是 `._symbol.hierarchicalPath`。
3. **双语义必须显式声明**: `connections` 支持实例路径与模块名两种目标, 输出 `resolved_as` 让 agent
   不需要"试错式理解"; 这不属于特判, 而是把两个真实实体类型讲清楚。

## 📎 产物

- 新增: `src/cli/core/semantic/instances.py` (4 命令) / `sim/tests/unit/test_cli_instance_query.py` (14 测试)
- 修改: `src/cli/main.py` (注册 4 命令) / `src/cli/core/locate/graph.py` (`--filelist` + params 契约) /
  `src/cli/_registry.py` (4 条登记 + NEW_PLANNED 更新) / **`src/trace/unified_tracer.py`** (修 bug #6 + 公开 `get_module_graph()`)
- 生成物: `docs/CLI_SURFACE.md` (69 命令)
- 文档: 本记录 + `CURRENT_TODO.md` + `overview.md` + `INDEX.md`
