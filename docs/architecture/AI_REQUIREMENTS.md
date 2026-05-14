# AI 功能需求清单

> 来源：AI Agent 反馈，2026-05-13

## 1. MCP Server（Model Context Protocol）

**优先级**：⭐⭐⭐⭐⭐（长远目标）  
**当前计划**：封装为 CLI，不做 MCP

将 sv_query 包装成 MCP Server，暴露 `trace_driver`、`get_constraints` 等 Tool，使 Claude Desktop、Cursor、Zed、Cline 等 AI 工具能直接调用。

**备注**：作者计划封装为 CLI，MCP 暂不考虑。

---

## 2. `--depth` 参数（路径追踪深度控制）

**优先级**：⭐⭐⭐⭐  
**现状**：
- fanin（递归追溯驱动）：有递归，但无 depth 控制
- fanout（递归追溯负载）：目前只支持单层，缺少递归能力
- `find_path`/`find_all_paths`：有 `max_depth=20` 但写死

**需求语义**：

| depth 值 | 行为 |
|---|---|
| `1` | 单步查询（直接驱动/负载） |
| `N` | 指定深度（递归 N 层） |
| `None` / 不指定 | 无限递归（全部追溯） |

**影响文件**：`query_signal.py`、`query_load.py`、`unified_tracer.py`

**对称性现状**：
- `trace_fanin` → 调用 `_collect_all_drivers`（递归）
- `trace_fanout` → 调用 `_find_loads`（单层）

**改动点**：给两个方向的 trace 方法统一加 `depth: int | None` 参数。

---

## 3. JSON / Mermaid 输出

**优先级**：⭐⭐⭐⭐  
**当前计划**：暂不做

提供结构化文本输出：
- **JSON**：便于 AI 解析
- **Mermaid**：可渲染成图，也便于 AI 读取

**备注**：现阶段先不做。

---

## 4. Diff 查询模式

**优先级**：⭐⭐⭐⭐  
**当前状态**：待深挖

人类常见问题："我改了这几行代码，影响了哪些信号？"

**核心能力**：对比两次 AST 的 Graph Diff，输出变更影响面。

**待确认问题**：
1. **存储方案**：如何保存历史 snapshot？（文件、内存、数据库？）
2. **算法方案**：如何高效对比两个 SignalGraph 的差异？
3. **架构影响**：是否需要新的模块（如 `graph_diff.py`）？

**需要进一步分析**后决定架构和实现路径。