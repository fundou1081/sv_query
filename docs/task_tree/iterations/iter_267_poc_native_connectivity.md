# Iteration 267: POC — slang-native 连通性 vs 现有两套路径实现

**Metadata**:
- **Iteration #**: 267
- **Task Tree Level**: L1
- **Parent Task**: `docs/task_tree/tasks/L1_core_review_and_cli_subtraction.md`
- **Created**: 2026-10-23 GMT+8
- **Author**: 方豆 / AI 助手（方豆: "先做 poc，但要标记清楚 poc，以及适用场景，优点，缺陷等"）
- **Outcome**: ✅ POC 完成，产出可复现基线 + 决策依据

## 🎯 目标

在改 `paths` / `dataflow` 之前，先**用数据**回答：
slang 原生端口连接建出的连通层，与现有两套实现差多少？差在哪？

## 🔬 做法

新增 **POC 工具** `tools/poc_native_connectivity.py`（不碰 `src/`）：

1. 原生侧：`Compilation` + `root.topInstances` + `portConnections`
   → 父网路径 / 子端口路径 / 方向（全部来自 public API）
2. 旧侧：`UnifiedTracer.build_graph()` + `PathResolver`
3. 对比：命名空间量化、顶层输入可达性、采样对四列可达性、PathResolver 终点正确率

## 📊 关键结果（两个 fixture）

| 指标 | minimal_3module | scheduler_minimal |
|---|---|---|
| 旧图节点 | 44 | 98 |
| **影子节点（模块定义命名空间）** | **17（38.6%）** | **30（30.6%）** |
| **影子节点从顶层输入可达** | **0/17** | **0/30** |
| PathResolver 终点 ≠ 请求 dst | **78/120** | **65/120** |
| 逆流路径（无向可达/有向不可达） | 104/120 | 88/120 |

## 💡 结论

1. 影子命名空间真实存在且**完全不可达** —— 以影子节点结尾的 `paths` 结果是伪路径
2. `PathResolver` **不能**直接给 `dataflow` 复用（无向 + 终点漂移）
3. slang 原生确实能给出端口两侧的准确路径与方向 → 单一连通层可行
4. 但本 POC 只验证了端口层，**不能**据此宣称整体更快/更准

## ⚠️ 明确标注的局限

见 [POC 文档 §5](../../poc/2026-10-23_native_connectivity.md)：只比可达性不比路径质量、
原生侧只建端口边、旧有向用 BFS 近似 dataflow、不展开 generate、只有 2 个小 fixture、不测性能。

## 🔗 相关

- POC 文档: [docs/poc/2026-10-23_native_connectivity.md](../../poc/2026-10-23_native_connectivity.md)
- 工具: `tools/poc_native_connectivity.py`
- 限制登记: [KNOWN_LIMITATIONS §3.3-3](../../KNOWN_LIMITATIONS.md)
