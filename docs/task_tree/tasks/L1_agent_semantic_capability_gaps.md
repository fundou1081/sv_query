# L1: Agent 语义能力缺口补全 (实例/层级/端口)

**Metadata**:
- **Task Tree Level**: L1
- **Created**: 2026-09-09 GMT+8
- **Author**: 方豆 / AI 助手
- **Status**: ✅ CLOSED (1a ✅ iter_236 / 候选 1~4 ✅ iter_237)
- **触发**: 方豆 2026-09-09 列出的缺口 —— **"instance 查询 / trace driver 信号驱动了谁 / trace loader 信号被谁使用"**

---

## 🎯 背景

主消费者是 **agent**; 它理解一个 RTL 设计的推理链是:
**定位 → 信号事实 → 结构 → 架构叙述**。
其中"结构"这一层 (有哪些实例、怎么连、端口映射) 此前**只有图, 没有查询** ——
`arch show` / `visualize module` 能**画**, 但没法**问**。

实测 (iter_236 前):

| 项 | 状态 |
|---|---|
| 库 API | `get_instances` / `trace_module` / `trace_port` / `find_connected_modules` 4 个都在 |
| CLI 暴露 | **0** (`grep` 在 `src/cli/` 只命中注册表的"计划新增"注释) |
| `get_instances()` 可用性 | ❌ **坏的** (双重包装 adapter + 按错误形状解析) → 见下 |

## ✅ 1a: 已完成 (iter_236)

| 命令 | 契约 |
|---|---|
| `svq instances [--module] [--depth]` | 实例列表 (full_path / module_type / parent), 支持 `--filelist` |
| `svq instance <路径>` | 详情 + 子实例 + 端口 (方向/位宽/内部信号) |
| `svq connections <实例路径\|模块名>` | 实例→端口映射 / 模块→四类边; 带 `resolved_as` |
| `svq hierarchy [--module] [--depth]` | 层级树 (机器可读版 `arch show`) |

顺带修复:
- **bug #6**: `UnifiedTracer.get_instances()` 从未工作 (双重包装 + 错误形状解析) → 重写 + 删 76 行死代码
- `graph` 组补 `--filelist` (此前只有 `--file`, 真实多文件项目不可用)
- 新增 `UnifiedTracer.get_module_graph()` 公开访问器 (CLI 不再摸私有属性)

## 📋 候选 (未拍板)

| # | 能力 | 状态 |
|---|---|---|
| 1 | 参数 override 查询 | ✅ **完成 (iter_237)**: `svq params <实例>` + `is_overridden` |
| 2 | class 实例成员查询 | ✅ **完成 (iter_237)**: `svq classes` / `svq class <name> [--member M]` |
| 3 | 跨模块路径查询 | ✅ **完成 (iter_237)**: `svq paths <src> <dst> [--all]` (并修 PathResolver 跨模块缺陷) |
| 4 | per-module 端口总览 | ✅ **完成 (iter_237)**: `svq ports <模块>` |

## 🔜 仍可挖掘 (未拍板)

- 参数**类型/表达式**级信息 (当前只有生效值; `$clog2` 之类派生参数未展开)
- 跨模块**约束**查询 (constraint 域已在 C1~C5 闭环, 但无 CLI)
- 时序/CDC 的**可靠算法** (见 `docs/EXP_NAMESPACE.md` 晋升门槛)

## 🔗 相关

- 迭代: [iter_236](../iterations/iter_236_instance_query_and_graph_filelist.md)
- 分层任务: [L1_cli_layering.md](L1_cli_layering.md) (本任务补的是其中的"能力"面, "结构"面已完成 P0~P3)
