# Iteration 253: T3-3 起手 — 拆 `semantic/trace.py` (1,835 → 1,081 行)

**Metadata**:
- **Iteration #**: 253
- **Task Tree Level**: L1
- **Parent Task**: `docs/task_tree/tasks/L1_core_review_and_cli_subtraction.md`
- **Created**: 2026-10-19 GMT+8
- **Author**: 方豆 / AI 助手（长期 goal）
- **Outcome**: ✅ 成功（1,835 → 1,081 行，拆出 3 个模块；全量 3422 passed）

## 🎯 目标

`src/cli/core/semantic/trace.py` 是 CLI 里最大的文件（1,835 行），同时承载
**5 个命令**（fanin / fanout / impact / evidence / overview）+ DOT 生成 + 三种文本渲染。
评审列为 T3-3 的拆分对象之一。

## 🔬 实际结果

### 拆分结果

| 模块 | 行数 | 内容 |
|---|---|---|
| `semantic/trace.py` | **1,081**（原 1,835） | `trace_app` + fanin / fanout / impact + 命令注册 |
| `semantic/trace_common.py` | 298 | 共享 helper：DOT 生成、信号收集、节点序列化、过滤器、快照加载 |
| `semantic/trace_evidence.py` | 219 | `evidence` 命令 + 文本渲染 |
| `semantic/trace_overview.py` | 321 | `overview` 复合命令 + 文本渲染 |

### 关键约束（拆的时候踩到的）

1. **不能循环 import**：命令模块不能 `from ...trace import trace_app`。
   做法：函数体里**去掉装饰器**，由 `trace.py` 统一 `trace_app.command("x")(x)` 注册。
2. **共享 helper 必须再下沉**：`evidence` 用 `_collect_signals`，直接 import `trace.py`
   会形成环 → 抽出 `trace_common.py`，两边都从这里引。
3. **既有导入路径不能断**：`cli/_evidence_helpers.py` 引用
   `from cli.core.semantic.trace import _load_tracer_from_snapshot`。
   `trace.py` 从 `trace_common` 导入该名字 → 天然 re-export，调用方零改动。
4. **注册顺序**：`trace.py` 末尾先 import 命令模块，再注册 —— 否则 Typer 拿到的是未定义对象。

### 验证

- import 冒烟：`import cli.main` OK
- 命令冒烟：`trace evidence inst_demo.add_out` / `trace overview in_a add_out` 均返回 `ok: true`
- CLI 套件 **445 passed**
- 全量门禁 **3422 passed / 0 failed**

## 📊 量化

| 指标 | 前 | 后 |
|---|---|---|
| `semantic/trace.py` | 1,835 行 | **1,081 行** |
| 单文件命令数 | 5 | **3** |
| 新增模块 | — | 3（common / evidence / overview） |

## 💡 决策

1. **先拆最独立的两块**（evidence / overview），不一次拆完。
   `fanin` / `fanout` / `impact` 之间共享大量输出逻辑，拆它们需要先抽 `output_text`
   的分派结构 —— 留到下一迭代，避免一次改动过大难以定位回归。
2. **`trace_common.py` 是被迫出现的**，但它是对的方向：把"命令"和"渲染/序列化"
   分开，后续拆 `visualize.py` 时同一模式可复用。
3. **拆分用"全量门禁"兜底，不靠肉眼**：本次改动涉及 3 处移动 + 4 处导入，
   肉眼很难确认没有遗漏的名字引用；连跑 2 次门禁（拆分后 + 修 helper 后）。

## 🔗 相关

- 评审: [2026-10-19_core_smell_review.md T3-3](../../refactoring/2026-10-19_core_smell_review.md)
- 前置: [iter_252 删 dev 层](iter_252_remove_dev_layer.md)
- 剩余 T3: `visualize.py` (2,376) / `elk_bridge` 908 行函数 / `UnifiedTracer` 36 方法
