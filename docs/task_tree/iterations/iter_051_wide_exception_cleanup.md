# Iteration 051: 清理 10 处宽异常 except Exception: pass

**Metadata**:
- **Iteration #**: 051
- **Task Tree Level**: L1
- **Parent Task**: fallback 清理 (清单 [清] 组)
- **Created**: 2026-08-29 00:40 GMT+8
- **Author**: 方豆 / DSH Agent
- **Outcome**: ✅ **成功** — 10 处全清, 0 回归, 4 探针 byte-identical

---

## 🎯 本次目标

用户指令: **"先清理那10个宽异常"** → 处理清单里 🔴 [清] 组的
10 处 `except Exception: pass` (宽异常, 最需要处理)。

---

## 📋 处理明细 (10 处)

| # | 位置 | try 内容 | 处理 |
|---|---|---|---|
| 1 | `base.py:1124` | `int(expr.literal.valueText)` | 收窄 `(ValueError, TypeError)` + debug |
| 2 | `base.py:1230` | 同上 | 同上 |
| 3 | `base.py:1456` | getattr + 遍历子节点 | 收窄 `(AttributeError, TypeError)` + debug |
| 4 | `driver_extractor.py:1158` | `get_module_name()` | 保留 Exception + warning |
| 5 | `_common.py:790` | `expr.eval()` 常量求值 | 保留 Exception + debug |
| 6 | `always_extractor.py:161` | genvar 登记 | 保留 Exception + debug |
| 7 | `always_extractor.py:649` | 条件信号收集 | 保留 Exception + warning |
| 8 | `expression_tree.py:45` | bytes decode | 收窄 `(UnicodeDecodeError, TypeError)` + debug |
| 9 | `module_extractor.py:430` | 接口位宽提取 | 保留 Exception + warning |
| 10 | `semantic_adapter.py:2369` | 子节点迭代 | 收窄 `TypeError` + debug |

**原则**: 能确定异常类型的**收窄** (5 处), 不能确定的**保留 Exception 但加日志**
(5 处) — 至少不再是 silent。

---

## 🔴 实施失误 (诚实标注)

1. **脚本多次 anchor 缩进不匹配** — 每个文件缩进不同, 固定文本 replace 失败多次。
   最终用 "行号 + 上下文锚点 + 动态缩进" 才稳定。
2. **`from __future__` 位置错误** — 在 expression_tree/module_extractor 把
   `import logging` 插到 `from __future__ import annotations` 前 →
   `SyntaxError: from __future__ imports must occur at the beginning` → 3 测试失败。
3. **ruff --fix 引入了 unsafe 改动** — 把 `Optional[X]` → `X | None` 等
   现代语法转换 (超出本次范围), 已恢复并只保留我的 logger 改动。
4. **logger 插入位置** — 曾插在 import 中间导致 E402, 修正为"所有 import 之后"。

**教训**: 
- 多文件批量改脚本, 每个文件缩进/结构不同, 必须用动态缩进 + 上下文锚点
- `from __future__` 必须是文件第一个 import
- ruff --fix 会做 unsafe 转换, 用前先看会改什么

---

## 📈 验证

| 项 | 结果 |
|---|---|
| `integration` | 13 failed (基线) = **0 回归** |
| `cli` | 20 failed (先期) = **0 回归** |
| `unit` | 4 failed (沙箱) = **0 回归** |
| `test_case27_1to1_truth` | **4 passed** ✅ |
| 4 探针 (assign/flatten/always/function) | **byte-identical** ✅ |
| ruff | **与基线一致** (62=62, 无新引入) |

---

## 📌 后续

- 🟡 [查] 组 30 处收窄异常 — 用户是否要处理, 待定
- 🟢 [留] 组 20 处防御性 — 建议保留
