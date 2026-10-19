# Iteration 244: 核心代码坏味道评审 + CLI 命令面盘点

**Metadata**:
- **Iteration #**: 244
- **Task Tree Level**: L1
- **Parent Task**: `docs/task_tree/tasks/L1_core_review_and_cli_subtraction.md`
- **Created**: 2026-10-19 GMT+8
- **Author**: 方豆 / AI 助手 (方豆: "找出 core 代码中的坏味道，并评估严重程度。结合架构信息一起 review。我们要对功能做一些减法，或者说分层处理。现在 cli 命令太多。")
- **Outcome**: ✅ 评审完成（只读，未改代码）；产出 1 份带严重度的评审 + 分档减法方案

## 🎯 本次目标

按"减法 / 分层"的视角评审全部核心代码，找出坏味道并给严重度。

## 🔬 实际结果

### 量化基线

| 范围 | 文件 | 行数 |
|---|---|---|
| `src/trace/` | 114 | 44,620 |
| `src/cli/` | 54 | 15,987 |
| `src/applications/` | 14 | 3,724 |
| 合计 | 183 | **64,336** |

其他度量：函数 1,609 个（>100 行 91 个，>200 行 26 个，最长 908 行）；
`except Exception` 246 处；裸 `except:` **0** 处；TODO/FIXME 41 处。

### 主要发现（完整清单见评审文档）

| # | 发现 | 严重度 | 证据 |
|---|---|---|---|
| 1 | 3,248 行归档代码在 `src/` 打包路径内 | 🟠 P1 | `graph/viz/_archived*` 16 文件，无 import，占 viz 模块 40% |
| 2 | `LoadExtractor._get_signal` 283 行死方法 | 🟠 P1 | 仅自递归，`extract()` 不调用；L110 注释显示上次清死方法漏了它 |
| 3 | `UnifiedTracer` 36 公开方法跨 10 领域 | 🟠 P1 | 1,403 行，所有 CLI 命令的必经之路 |
| 4 | CLI 74 规范 + 30 别名 = 104 叶子 | 🟠 P1 | 默认可见 47；`main.py` 55 个注册点 |
| 5 | `elk_bridge.expr_trees_to_elk` 单函数 908 行 | 🟠 P1 | 全仓最大函数 |
| 6 | CLI 输出层 7 份副本 | 🟡 P2 | `output_json` ×7 / `output_text` ×6 |
| 7 | **双导入根**：`from src.*` 27 处 vs `from cli/trace.*` 1,012 处 | 🟡 P2 | 实测 `cli.errors is src.cli.errors` → **False**；`verify_app` 两个对象 |
| 8 | 2 个孤立模块 1,026 行 | 🟡 P2 | `signal_graph_viewer` 895 / `function_expander` 131，全仓 0 引用 |
| 9 | registry note 过期 | 🟡 P2 | `graph nodes --filelist` 实测可用，note 仍写"只支持 --file" |
| 10 | `diff compare` 宣布合并未执行 | 🟡 P2 | note 写"[计划] 并入 snapshot compare"，命令仍在 |

### 减法方案（三档，未执行）

- **T1 零风险**：归档 3,248 行 + 删死方法 283 + 删孤立模块 1,026 + 修 note + 删 `diff compare` → **-4,560 行**
- **T2 合并同族**（core 34→26 / view 13→9 / 别名 30→6）：`graph` 4→2、`diagnose` 4→1、
  `class` 2→1、`controlflow` 3→2、`snapshot` 5→4、`dev` 3→1、view 叙述类 3→1
- **T3 结构性**：拆 `UnifiedTracer` / 统一输出层 / 拆 `visualize.py` 与 `semantic/trace.py` / 拆 `elk_bridge`

## 💡 关键发现 / 决策

1. **第一版"死模块扫描"是错的，我纠正了。** 最初的脚本用"前缀匹配"判断引用，
   把被 import 的**包下的所有模块**都当成活的（`mod.startswith(prefix)` 方向写反），
   结论是"0 个死模块"。改用**正确解析相对导入**后，得到 50 个候选；
   再逐个用 grep 复核，才分出 16 个真归档 + 2 个真孤立 + 其余是 `from src.*` 造成的假阳性。
   **假阳性本身变成了第 7 条发现（双导入根）** —— 测量工具的错误暴露了真问题。

2. **"命令太多"不是审美问题，是发现成本问题。** 47 个默认可见命令里，
   `graph dump`（1 个测试引用）、`visualize compute`（1 个）、`visualize timed`（2 个）
   这类命令占了用户的注意力预算却不常被用；而 `hierarchy` 测试只有 3 个引用但文档引用 133 次
   —— **测试引用数只能用来排序嫌疑，不能作为删除依据**，必须看语义重叠。

3. **没有 P0 值得单独说。** 方向性纪律（无反向依赖、无裸 except、单一注册表、
   只读证明）都在生效；真正的问题是"每加一个变体就加一个命令"的膨胀模式，
   所以评审里建议给 `check_cli_layers.py` 补一条规则：
   **输入可由一个枚举参数表达、输出 schema 同构的两个命令，必须合并**。

## 🔗 相关

- 任务: [L1_core_review_and_cli_subtraction.md](../tasks/L1_core_review_and_cli_subtraction.md)
- 评审: [2026-10-19_core_smell_review.md](../../refactoring/2026-10-19_core_smell_review.md)
- 架构: [ARCHITECTURE.md](../../ARCHITECTURE.md)
