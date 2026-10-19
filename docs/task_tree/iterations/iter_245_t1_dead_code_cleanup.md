# Iteration 245: 减法 T1 — 归档死代码 + 删死方法 + 修过期 note

**Metadata**:
- **Iteration #**: 245
- **Task Tree Level**: L1
- **Parent Task**: `docs/task_tree/tasks/L1_core_review_and_cli_subtraction.md`
- **Created**: 2026-10-19 GMT+8
- **Author**: 方豆 / AI 助手 (方豆: "按照这个列表，做一个长期 goal，先把这些都清掉")
- **Outcome**: ✅ 成功 (src −4,562 行 / −19 文件; 全量 3419 passed / 0 failed)

## 🎯 本次目标

执行评审 T1（零风险档）：归档 `_archived*`、删死方法、清理孤立模块、修 registry 过期 note。

## 🔬 实际结果

### T1-a 归档 16 个历史渲染器 → `docs/archive/2026-10-19-src-archived/`

- `_archived/` 5 文件 + `_archived_dot/` 12 文件，**3,248 行**，零 import
- **连带发现一处隐藏引用**：`sim/tests/unit/test_viz_data.py` 有 5 条测试
  在测 `_archived_dot/viz_dot_renderer.render_dot` —— 即"测试在测已归档的渲染器"
- 处理：把 5 条 DOT 测试**替换为 2 条活路径测试**（`VizData → viz_to_elk` 的结构不变式：
  必须含 `id/children/edges`、节点 id 不得含 `.`），而不是直接删掉
  - 净 −3 条测试；但覆盖的对象从"已归档代码"变成"唯一渲染路径"，覆盖方向更正确
- 附带修正 `src/trace/core/graph/viz/__init__.py` 里写着 `_archived_dot/` 的过时说明

### T1-b 删除 `LoadExtractor._get_signal`（285 行）

- 依据：`extract()` 从不调用它；唯一的调用都是它自己递归自己；末尾 `raise` 之后
  还有 7 行**不可达代码**
- `load_extractor.py` 398 → 115 行
- 删除前复核：`sim/tests` 无任何测试直接调用该方法（`test_get_signal_identifier.py`
  是端到端建图，不碰这个方法）

### T1-c 两个孤立模块

| 模块 | 行数 | 处理 | 依据 |
|---|---|---|---|
| `graph/signal_graph_viewer.py` | 895 | **归档** | 全仓 0 import；且自带 `__main__` **实测跑不通**（`KeyError: 'show_type'`，移动前就坏——用 `git show HEAD:` 取出原文件复现过） |
| `builder/function_expander.py` | 131 | **归档** | 全仓 0 import，`builder/__init__.py` 也不导出 |
| `cli/commands/` | 5 | **删除** | 只剩空 `__init__.py` |

> 计划里写的是"移到 `tools/`"（`signal_graph_viewer` 看起来是可运行的调试脚本）。
> 实测发现它跑不通，于是改为归档 —— **移动一个坏脚本只是把死代码搬个地方**。

### T1-d 修正 4 条过期 note + 重生成 CLI_SURFACE

`graph nodes/edges/find/dump` 四条 note 原写「[缺口] 只支持 `--file` 单文件」，
但 iter_236 已补 `--filelist`（实测可用）。已改为准确描述并 `gen_cli_surface.py` 重生成。

### T1-e `diff compare` → 推迟到 T2（附理由）

计划里把它算进 T1，实际检查后**不满足零风险标准**：

| | `diff compare` | `snapshot compare` |
|---|---|---|
| 输入 | 两个 **SV 文件** | 两个**快照 tag** |
| 后端 | `diff_with_health`（健康分/耦合/可达性） | `SnapshotManager.compare`（节点计数差/稳定核心） |
| JSON schema | health_score / coupling_warning / reachability_diff | node_count_diff / stable_core |

合并需要统一入参与 schema，属于 T2 的范围。已在评审文档 §5.2 保留该条目，
T1 不改动它（避免用"零风险"的名义做一次有风险的语义变更）。

## 📊 量化

| 指标 | 前 | 后 | 变化 |
|---|---|---|---|
| `src/` 文件数 | 183 | **164** | −19 |
| `src/` 行数 | 64,336 | **59,774** | **−4,562** |
| 归档目录 | — | 19 文件 / 4,273 行 | 新增（可追溯） |
| 全量测试 | 3422 passed | **3419 passed** | −3（DOT 测试 5 → ELK 测试 2） |
| 规范命令 | 74 | 74 | 不变（T2 处理） |

## 💡 关键发现 / 决策

1. **"零风险"要先验证再宣布。** `signal_graph_viewer` 在评审里被判断为"孤立但可运行"，
   实际取出原文件一跑就 `KeyError`。若按原计划移进 `tools/`，我们会把一份坏脚本
   变成"受支持的脚本"。**判断"某个东西能不能留"要跑一次，不能只看 import。**

2. **测试也要跟着代码走，但方向要换。** 5 条 DOT 测试不是"为通过而删"——
   它们测的渲染器已经不在产品里了；替换成 2 条 ELK 结构测试后，
   锁定的对象变成当前唯一渲染路径（还顺带锁了"节点 id 不含点"这个真不变量）。

3. **顺手抓到一处文档谎言**：`docs/ARCHITECTURE.md` §4.4 写
   `signal_graph_viewer.render_html/render_mermaid`「内部 helper 仍在使用」——
   实际零引用且脚本跑不通。已改为事实描述。

## 🔗 相关

- 任务: [L1_core_review_and_cli_subtraction.md](../tasks/L1_core_review_and_cli_subtraction.md)
- 评审: [2026-10-19_core_smell_review.md](../../refactoring/2026-10-19_core_smell_review.md)
- 归档说明: [docs/archive/2026-10-19-src-archived/README.md](../../archive/2026-10-19-src-archived/README.md)
