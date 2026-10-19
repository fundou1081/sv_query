# Iteration 246: B4 — CLI 输出层收敛 (7 份 → 1 份) + R9 机械规则

**Metadata**:
- **Iteration #**: 246
- **Task Tree Level**: L1
- **Parent Task**: `docs/task_tree/tasks/L1_core_review_and_cli_subtraction.md`
- **Created**: 2026-10-19 GMT+8
- **Author**: 方豆 / AI 助手（长期 goal: "先把这些都清掉"）
- **Outcome**: ✅ 成功（7 份 `output_json` 收敛为 1；`fail` 收敛为 1；新增 R9 + 3 条自检）

## 🎯 本次目标

评审 B4：CLI 没有统一输出层，`output_json` 有 7 份副本、`output_text` 6 份、
三个 `_common` 各自为政。合并顺序上它排在 T1 之后、T2 之前 ——
**先让"加一个字段只改一处"成立，后续命令合并才便宜**。

## 🔬 实际结果

### 1. 收敛 `output_json`：7 → 1

先比对 7 份实现，结果**逐字节相同**（`graph` / `stats` / `diff` / `trace` /
`dataflow` / `controlflow` / `expression`）：

```python
def output_json(data: dict, pretty: bool = False) -> None:
    indent = 2 if pretty else None
    print(json.dumps(data, indent=indent, ensure_ascii=False))
```

新建 `src/cli/_output.py`（`emit_json` / `fail`），7 处改为 `from cli._output import emit_json`
并把调用点改名。顺带删掉 6 个因此不再使用的 `import json`。

### 2. 收敛 `fail`：2 → 1

`core/semantic/_common.py` 的 `fail` 移入 `_output.py`，原位置改为 re-export
（既有 `from ._common import fail` 的导入路径继续有效，零改动）。

### 3. 新增机械规则 R9 + 自检

`tools/check_cli_layers.py` 增加 **R9**：

> 命令模块不得自己定义 `output_json` / `emit_json` / `fail` / `output_error`
> —— 一律用 `cli/_output.py`（唯一例外：`_output.py` 自身）。

配套 3 条自检（`sim/tests/unit/test_cli_layering.py::TestCheckerSelfTest`）：

- 合成违规文件 → R9 必须命中
- `_output.py` 自身 → 不误报
- 真实 `src/cli` 树 → 零违规

> 依据项目教训（iter_190 `except:pass`、iter_224 1-tuple）：**规则没有机械检查就会长回来**。

### 4. 未做的部分（如实记录）

CLI 里仍有 **45 处内联 `json.dumps`**（`snapshot` 9 处、`diagnose` 5 处、
`capabilities` / `search` / `trace` 等）。它们分两类：

| 类型 | 例子 | 为何本次不动 |
|---|---|---|
| 一次性信封 | `{"ok": false, "tag":..., "deleted": false}` | 与 `--json` 通用路径无关，改动收益低 |
| 特化格式 | `print(json.dumps(snapshots, indent=2))`（固定缩进，不看 `--pretty`） | 机械替换会改变输出字节，需逐个确认测试 |

**结论**：B4 的"7 份 helper"目标已达成；内联 dumps 的收敛列为 B4 的后续项
（需要逐个确认输出字节，不能批量替换）。

## 📊 量化

| 指标 | 前 | 后 |
|---|---|---|
| `output_json` 定义 | 7 | **1** |
| `fail` 定义 | 2 | **1** |
| 因此删掉的 `import json` | — | 6 |
| 检查规则 | R1~R8 | **R1~R9** |
| 检查器自检 | — | +3 |

## 💡 关键发现 / 决策

1. **先验证"是否真的相同"再合并。** 7 份 `output_json` 看起来像复制粘贴，
   但可能有细微差异（`typer.echo` vs `print`、`indent` 计算）。逐份比对确认**逐字节相同**后
   才敢机械替换 —— 这是"零风险"的前提，不是感觉。

2. **re-export 是低风险的收敛技巧。** `fail` 有多个既有导入方，
   直接改调用点会扩大 diff；在原位置 re-export 既保证单一实现，又让调用方零改动。

3. **规则要配自检，否则只是文档。** R9 加完后立刻写了"合成违规必须被检出"的测试；
   否则将来有人把 `output_json` 复制回去，检查器若写错也不会有人发现。

## 🔗 相关

- 评审: [2026-10-19_core_smell_review.md §4 B4](../../refactoring/2026-10-19_core_smell_review.md)
- 前置: [iter_245 T1](iter_245_t1_dead_code_cleanup.md)
- 新模块: `src/cli/_output.py`
