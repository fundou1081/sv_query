# Iteration 237: 语义查询补全 — `params` / `ports` / `paths` / `classes`+`class` (+ 修 PathResolver 跨模块缺陷)

**Metadata**:
- **Iteration #**: 237
- **Task Tree Level**: L1
- **Parent Task**: `docs/task_tree/tasks/L1_agent_semantic_capability_gaps.md` (候选 1~4)
- **Created**: 2026-09-09 GMT+8
- **Author**: 方豆 / AI 助手 (方豆: "先把上面做好")
- **Outcome**: ✅ 成功 (5 个新命令 + 修 PathResolver; 新增 14 条测试)

## 🎯 本次目标

把 1a 之后列出的 4 类同类缺口一次做完 (都是"库有、CLI 没有"):

1. **参数 override 查询** —— `#(.WIDTH(8))` 实际生效值
2. **端口总览** —— per-module 端口表
3. **跨模块路径查询** —— `PathResolver.find_all_paths`
4. **class 查询** —— `list_classes` / `trace_class_members` / `trace_class_instances` / `trace_member_instances`

## 📦 交付

| 命令 | 输出契约 | 复用 |
|---|---|---|
| `svq params <实例路径>` | `{instance, module_type, parameters:[{name, value, **is_overridden**, is_local_param}]}` | `InstanceSymbol.body.parameters` |
| `svq ports <模块名>` | `{count, by_direction, ports:[{port, direction, width, in_edges, out_edges}]}` | 信号图 PORT_* 节点 + 邻接 |
| `svq paths <src> <dst> [--all] [--max N]` | `{found, hop_count, path}` / `{count, truncated, all_paths}` | `PathResolver` |
| `svq classes` | `{count, classes:[...]}` | `list_classes()` |
| `svq class <name> [--member M]` | `{members(类型级), instances(实例级)}` / `{instances(实例成员节点)}` | `trace_class_*` |

设计要点:
- **`params` 区分 override 与默认值** (`is_overridden`) —— 直接回答"这个 `.W(4)` 到底生效没有";
  实测: `u_child` → W=4(override)、DEPTH=3(override); `u_child_default` → W=4(override)、**DEPTH=2(默认)**
- **`ports` 字段诚实命名**: `in_edges`/`out_edges` 是**信号图原始邻接计数**, 不冒充语义 driver/load
  (docstring 明确指向 `connections` / `drivers` 做语义判定)
- **`class` 分开返回类型级成员与实例级节点** —— 遵循 iter_152 架构决策 D3 (类型级=结构参考, 实例级=数据端点)
- 新增 `core/semantic/_common.py` 共享 tracer 构建 / JSON 输出 / 节点序列化 / 结构化失败,
  避免 5 个模块各复制一份

## 🔧 修复: `PathResolver` 的跨模块缺陷 (item 3 的真身)

**现象**: `find_path('inst_demo.in_a', 'inst_demo.add_out')` 恒 `None`, `find_all_paths` 恒 `[]` ——
尽管图上存在完整边链。

**根因 (两个)**: 
1. BFS 只做**"进模块"**映射 (`get_internal_signal`: 端口路径 → 内部信号),
   **不做"出模块"** (`get_port_path`: 内部信号 → 端口路径) → 一旦走到模块内部就出不来;
2. `find_path` 走 successors+predecessors, 而 `find_all_paths` **只走 successors** →
   两者结论互相矛盾 (同一对信号: 一个有路径、一个返回空)。

**修法 (根因)**:
- 新增 `PathResolver._neighbors(node)`: successors + predecessors + **进模块** + **出模块** 四路邻接, 单一真相源
- `find_path` (BFS) 与 `find_all_paths` (DFS) **共用** `_neighbors` → 不变式:
  **`find_path` 找得到的路径必然出现在 `find_all_paths` 里** (已由测试锁定)
- `find_all_paths` 加 `max_paths=50` / `max_depth=60` 上限 (有环图防爆), 输出带 `truncated`

**验证** (inst_demo): `in_a → add_out` 现有 4 条路径, 其中 3 条穿越模块内部
(如 `in_a → u_adder.a → sub_adder.a → sub_adder.sum → u_adder.sum → add_out`) —— 旧实现 0 条。

## 📊 验证

| 项 | 结果 |
|---|---|
| 新测试 `test_cli_semantic_queries.py` | **14 passed** (params override 语义 / 端口表 / 跨模块路径 / PathResolver 自洽性 / MIG 双向映射 / class 三查) |
| 既有 `test_cli_instance_query.py` | 14 passed (无回归) |
| `check_cli_layers.py` | rc=0 (74 规范命令 + 30 别名 = 104 叶子, 0 违规) |
| 全量 canonical | 见提交记录 (预期 ≥3350, 0 退化) |

## 💡 关键发现 / 决策

1. **"库 API 存在" ≠ "库 API 能用"** —— `PathResolver` 是第二个例子 (第一个是 `get_instances`):
   两个 API 都**零 CLI 调用方**, 也都是坏的。**这一批 4 项里 2 项需要先修库**。
   → 经验: 暴露库 API 前必须先手动跑一次真实输入, 否则等于把 bug 包装成命令 (对 agent 是"撒谎工具")。
2. **两个入口必须共用同一套语义**: `find_path` 与 `find_all_paths` 各自实现遍历 → 结论矛盾。
   抽 `_neighbors` 后, 不变式可测 ("一条路径 ⊆ 所有路径")。
3. **测试断言要匹配契约**: 我第一版断言 `find_path` 必须走模块内部 → 失败。实际契约是
   "返回最短跳数路径", 内部路线在 `--all` 里。**不是放宽断言, 是把契约写清楚** (同时改了 docstring)。
4. **字段命名不许含糊**: `in_edges/out_edges`(图邻接) vs `drivers/loads`(语义) —— 前者不能冒充后者。

## 📎 产物

- 新增: `src/cli/core/semantic/{_common,params,ports,paths,classes}.py` / `sim/tests/unit/test_cli_semantic_queries.py`
- 修改: `src/trace/core/module_instance_graph.py` (**PathResolver 修跨模块 + 统一邻接 + 上限**) /
  `src/trace/unified_tracer.py` (`get_path_resolver()` 公开访问器) / `src/cli/main.py` (注册 5 命令) /
  `src/cli/_registry.py` (5 条登记)
- 生成物: `docs/CLI_SURFACE.md` (74 命令)
- 文档: 本记录 + `L1_agent_semantic_capability_gaps.md` (候选 1~4 ✅) + `CURRENT_TODO/overview/INDEX`
