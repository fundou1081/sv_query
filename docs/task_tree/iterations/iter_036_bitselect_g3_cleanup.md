# Iteration 036: #2 G3 选项 3 收尾 — 消除路径 A regex + 清除 silent fallback

**Metadata**:
- **Iteration #**: 036
- **Task Tree Level**: L2
- **Parent Task**: ARCHITECTURE_TODOLIST #2 (BitSelect 改用 pyslang Semantic API)
- **Created**: 2026-08-28 11:40 GMT+8
- **Author**: 方豆 / DSH Agent
- **Outcome**: ✅ **成功** — 3 项收尾全部完成, 实测 0 回归, 另修好 3 个先前失败

---

## 🎯 本次目标

用户指令: **"继续"** — 即完成 iter_035 结案时列出的 3 项收尾:

1. 修 silent fallback (`_common.py:440-441`) — 违反核心纪律 #2
2. 改造路径 A (`bit_select_handler.py`) 仍是 regex — 选项 3 只完成一半
3. 清理 `graph_builder.py:442` 残留 `import re`

---

## 📊 当前状态 / 预期结果

开工时 HEAD = `bec0f51` (路径 B 已改造完成, 0 回归)。
预期: 3 项做完, 保持 0 回归。

---

## 🔬 实际结果

### ✅ 1. silent fallback 已清除 (`_common.py`)

**先探索**: 查证 pyslang 是否真是"可选依赖"——
- `pyproject.toml` `[project.dependencies]`: `pyslang>=10.0.0,<12.0.0` **硬依赖**
- `requirements.txt` 同样硬声明, 且注释写明 "之前 pyslang 标 optional (实际是核心依赖)"
- `src/` 下**其余 12 处**全部直接 `import pyslang`, **0 处**用 try/except

→ 原注释 "pyslang 在测试/lint 环境可能没装 (CI)" 的前提**不成立**, 本文件是全项目唯一例外。

**改动**:
- `try/except ImportError` + `_HAS_PYSLANG` 开关 → 直接 `from pyslang import ...`
- `iter_bit_selects()` 里 `if not _HAS_PYSLANG: return  # 退化: 让调用方走 regex 老路径` → **删除**
- `module is None` 从静默 `return` → `raise ValueError` (附原因说明)

### ✅ 2. 路径 A 已改用 semantic API (`bit_select_handler.py`)

`_create_hierarchical_bit_nodes` 原用 `re.match(r"^([^\[]+)\[(\d+):(\d+)\]$", nid)`
反推节点 ID 字符串, 现改为复用**与路径 B 同一个** helper `_common.iter_bit_selects`。

- 模块级 `import re` 删除
- 新增 `_get_pyslang_root()`, 取不到 root 时 `raise ValueError` 而非静默跳过

**刻意保留的语义**: 只处理 RangeSelect (`[msb:lsb]`), 不处理 ElementSelect (`data[0]`)。
原正则要求 `(\d+):(\d+)` 冒号形式, 从不匹配单下标 —— 这是该类 docstring 明示的
"数组下标不是位选", 属**行为对齐**而非遗漏。同理 `msb/lsb` 无法折叠为常量时跳过,
与原正则只接受字面量一致。

### ⚠️ 3. `graph_builder.py:442` 的 `import re` — **不删, 我之前判断错了**

实际读代码后发现: 它属于 **`_collect_struct_members()`**, 用
`re.match(r"^(.+)\.([^.]+)$", node_id)` 从节点 ID 提取 `parent.member` 结构,
**与位选无关**, 且是该函数唯一 `re` 用法。删除会直接破坏 struct 成员识别。

**iter_035 把它列为"位选改造的残留"是我的误判**, 特此更正。

### 🆕 4. 额外发现并修复: 路径 B 也有一处 silent fallback

`graph_builder._create_hierarchical_bit_nodes` 里:
```python
if pyslang_root is None:
    return          # ← 静默跳过全部位选处理
```
`SemanticAdapter.__init__` 恒设 `self._root`, 故 None 只可能是调用方传错 adapter 类型。
静默 return 会让**整张图的 BIT_SELECT 边凭空消失**, 且与"该设计本来就没有位选"无法区分。
→ 改为 `raise ValueError`。

**这是 iter_035 漏掉的一处**, 本次一并清理。

---

## 📈 回归验证 (git worktree A/B 对照, 基线 = `bec0f51`)

| 测试套 | 基线 `bec0f51` | 本次改动后 | 结论 |
|---|---|---|---|
| `sim/tests/integration` | 13 failed | **13 failed** | ✅ **0 回归** |
| `sim/tests/cli` | 23 failed | **20 failed** | ✅ **0 回归, 另修好 3 个** |
| `sim/tests/unit` | 13 failed | 13 failed | ✅ 0 回归 (全沙箱所致) |
| `test_case27_1to1_truth.py` | — | **4 passed** | ✅ 全绿 |

**意外修好的 3 个** (`test_visualize_graph_source.py`):
`test_graph_show_source_adds_file_line_to_label` / `..._adds_url_attribute` / `..._has_no_url`
— 推测: 路径 A 改用 semantic API 后, 位选节点带上了正确的 `line/col` 源码位置
(helper 的 `BitSelectHit` 含 `.sourceRange`), 而旧 regex 反推拿不到位置信息。

---

## 💡 关键发现 / 关键技术 / 决策

### 发现 1: "兼容性"注释可能是假的, 必须查证

`_common.py` 原注释声称 "pyslang 在测试/lint 环境可能没装 (CI)"。查 `pyproject.toml` +
`requirements.txt` + 全仓 import 方式后证实**前提不成立**。
**教训**: 看到 try/except 的理由注释, 要去查依赖声明验证, 不能直接采信。

### 发现 2: 同一类纪律问题常成对出现

iter_035 只标出了 `_common.py` 一处 silent fallback。本次改造路径 A 时顺手检查路径 B,
发现 `pyslang_root is None: return` 是**同类问题**。
**教训**: 发现一处 silent fallback, 应把同一调用链上下游都扫一遍。

### 发现 3: 我在 iter_035 的一处判断是错的

把 `graph_builder.py:442` 的 `import re` 列为"位选改造残留"——实际它服务于
`_collect_struct_members`, 与位选无关。**未经读代码就凭 grep 行号下结论是不够的**,
这也正是 AGENTS.md "不了解的代码不要贸然修改" 要防的。幸好本次动手前先读了代码。

---

## ✅ #2 完成度

G3 选项 3 (pyslang semantic API 替代 regex) **两条路径均已完成**:

| 路径 | 位选解析方式 | silent fallback |
|---|---|---|
| A `bit_select_handler.py` | ✅ semantic API | ✅ 已改显式 raise |
| B `graph_builder.py` | ✅ semantic API | ✅ 已改显式 raise |

残留的两处 `re` 均**与位选无关且合理**:
- `bit_select_handler.py:216` — constraint 表达式**文本**扫描 (非 AST 反推)
- `graph_builder.py:442` — struct 成员名 `parent.member` 拆分
