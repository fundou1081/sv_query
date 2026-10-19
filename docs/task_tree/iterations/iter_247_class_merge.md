# Iteration 247: T2-a — `classes` 合并进 `class` (2 → 1)

**Metadata**:
- **Iteration #**: 247
- **Task Tree Level**: L1
- **Parent Task**: `docs/task_tree/tasks/L1_core_review_and_cli_subtraction.md`
- **Created**: 2026-10-19 GMT+8
- **Author**: 方豆 / AI 助手（长期 goal: 清掉减法清单）
- **Outcome**: ✅ 成功（规范命令 74→73，默认可见 47→46，测试 21 passed 无回归）

## 🎯 目标

评审 §5.2 的第一族：`class` 与 `classes` 只差"有没有给 class 名"，
两个命令让 agent 多一次猜测。合并为 1 个。

## 🔬 实际结果

### 改法

- `class` 的 `name` 参数从**必填**改为**可选**
- 不给 `name` → 走原 `classes` 的输出信封（`{"ok":true,"count":N,"classes":[...]}`）
- 给了 `name` → 原行为（`members` / `instances`，`--member` 仍可用）
- 删除 `classes_cmd`（69 行文件 → 48 行）

### 兼容性

| 用法 | 之前 | 现在 |
|---|---|---|
| `svq classes --json` | ✅ | ❌ 命令不存在（**破坏性**） |
| `svq class --json` | ❌ 缺参数报错 | ✅ 等价于原 `classes` |
| `svq class packet --json` | ✅ | ✅ 不变 |

**这是有意为之的破坏性合并**：保留 `classes` 别名会失去"减一个叶子"的意义。
旧用户按新帮助即可恢复（帮助文本已写明"不给 class 名 → 列所有 class"）。

### 验证

- `sim/tests/unit/test_cli_semantic_queries.py` 的 2 处调用改为 `class`，**21 passed**
- 冒烟（真实 fixture `param_class_nested.sv`）：
  - `svq class -f ... --json` → `{"count": 2, "classes": ["inner","packet"]}`
  - `svq class packet -f ... --json` → `member_count=3 / instance_count=1`
- `capabilities`：`total` 73 / `core` 33 / `semantic` 16；叶子 103
- `gen_cli_surface` 重生成；`check_cli_layers` rc=0

## 📊 量化

| 指标 | 前 | 后 |
|---|---|---|
| 规范命令 | 74 | **73** |
| `core` 层 | 34 | **33** |
| 默认可见（capabilities） | 47 | **46** |
| 叶子（含别名） | 104 | **103** |

## 💡 决策

- **不做"保留别名"的温和合并**：本次目标就是减叶子；留一个等价别名等于没减。
  破坏性变更在 `capabilities` / `CLI_SURFACE` 里立刻可见（agent 读的是这两个）。
- `--member` 语义不变：它只在"给了 class 名"时有意义，未给名时传 `--member` 应报错
  （当前是静默忽略，记入后续 polish）。

## 🔗 相关

- 评审: [2026-10-19_core_smell_review.md §5.2](../../refactoring/2026-10-19_core_smell_review.md)
- 前置: [iter_246 B4](iter_246_cli_output_layer.md)
- 改动: `src/cli/core/semantic/classes.py` / `src/cli/main.py` / `src/cli/_registry.py`
