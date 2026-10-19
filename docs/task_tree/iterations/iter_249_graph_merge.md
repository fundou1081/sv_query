# Iteration 249: T2-c — `graph` 4→2 (`find`→`--match`, `dump`→`--detail`)

**Metadata**:
- **Iteration #**: 249
- **Task Tree Level**: L1
- **Parent Task**: `docs/task_tree/tasks/L1_core_review_and_cli_subtraction.md`
- **Created**: 2026-10-19 GMT+8
- **Author**: 方豆 / AI 助手（长期 goal: 清掉减法清单）
- **Outcome**: ✅ 成功（命令 70→68、core 30→28、叶子 94；全量 3422 passed）

## 🎯 目标

`graph` 组有 4 个命令：`nodes` / `edges` / `dump` / `find`。
其中 `find` 只是"按子串过滤 nodes"，`dump` 只是"nodes + 富字段 + edges" ——
两者本质是 `nodes` 的两个**选项**，却各占一个命令位。

## 🔬 实际结果

### 判定：两个都能折进 `nodes`

| 原命令 | 语义 | 折入方式 |
|---|---|---|
| `graph find PATTERN` | 列出 id 含 PATTERN 的节点 | `graph nodes --match PATTERN`（大小写不敏感） |
| `graph dump` | 整图 JSON（含 expression/condition 等富字段） | `graph nodes --detail`（富字段）+ `graph edges`（边） |

这符合评审里那条判据：**输入可由一个参数表达、输出同构** —— `find` 的输出就是
`nodes` 输出的子集；`dump` 的节点部分就是 `nodes` 加富字段。

### 实现

- `nodes` 增加 `--match`（子串过滤）与 `--detail`（富字段：width / expression / operands /
  signals / function_name / condition / true_branch / false_branch）
- `params` 里带上两个新选项（agent 可复现查询）
- 删除 `dump` / `find` 两个命令函数（`graph.py` 由 4 个命令缩到 2 个）

### 兼容性（破坏性，已记录）

| 老用法 | 新用法 |
|---|---|
| `graph find clk` | `graph nodes --match clk` |
| `graph dump --json` | `graph nodes --detail --json`（+ `graph edges --json` 取边） |

### 验证

- 冒烟：`graph nodes --match clk -f inst_demo.sv --json` → `total=1`（`inst_demo.clk`）；
  `--detail` → 输出含 `condition/expression/false_branch/...` 富字段
- 测试适配 3 处（2 个文件），相应套件 **17 passed**
- `capabilities`：total 68 / core 28 / locate 6；叶子 94
- 全量门禁 **3422 passed / 0 failed**

## 📊 量化

| 指标 | 前 | 后 |
|---|---|---|
| 规范命令 | 70 | **68** |
| `core` 层 | 30 | **28** |
| `locate` 组 | 7 | **6** |
| 叶子（含别名） | 96 | **94** |

## 💡 决策

- **`edges` 不折进 `dump`**：边的过滤维度（`--src/--dst/--kind`）与节点完全不同，
  硬合并会让一个命令带两套互斥参数。`nodes` / `edges` 是"两类图元素"的自然切分。
- **`--detail` 而不是保留 `dump`**：富字段是节点的属性，放在 `nodes` 上语义更直白；
  需要"整图"的调用方组合两次调用即可（agent 本来就是这么用的）。

## 🔗 相关

- 评审: [2026-10-19_core_smell_review.md §5.2](../../refactoring/2026-10-19_core_smell_review.md)
- 前置: [iter_248 diagnose 合并](iter_248_diagnose_merge.md)
