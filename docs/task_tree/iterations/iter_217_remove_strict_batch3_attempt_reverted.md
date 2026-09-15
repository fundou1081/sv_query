# Iteration 217: 批次 3 (API 形参) 尝试 → 行内传参遗漏, 已回退

**Metadata**:
- **Iteration #**: 217
- **Task Tree Level**: L1 (纪律强制 · 执行)
- **Parent Task**: 方豆 "继续推进" (iter_214 方案的批次 3)
- **Created**: 2026-09-08 GMT+8
- **Author**: 方豆 / AI 助手 (deepseek-v4-flash)
- **Outcome**: ⚠️ 部分手法有效 / 整体回退 (行内形态遗漏 → 265 failed)

## 🎯 本次目标

批次 3: 移除 API 形参 `strict` (`_build_tracer` / `build_viz_tracer` /
`_evidence_helpers.build_resolver` / `handle_compilation_error` 等), 让"恒定严格"
成为**类型层面**的事实, 而不只是传参约定。

## 🔬 实际结果

### 3a 有效 (CLI 侧 helper 去形参 + 删死传参)

- `_build_tracer(..., strict: bool = True)` → 去掉形参;
- `build_viz_tracer(..., strict)` → 去掉形参 + 调用点;
- `_evidence_helpers.build_resolver` → 去掉 `strict=False` 形参;
- 删除 **88 处**已死的 `strict=True` 传参; `handle_compilation_error` 去 `strict` 形参;
- 冒烟: `stats` / `trace` / `design show` 全部 rc=0 —— **这部分是好的**。

### 但整批失败: **行内形态**没被覆盖 → 265 failed / 6 errors

遗漏的是**行内**写法 (非独占一行):

```python
_build_tracer(..., strict=True, preprocess_macros=preprocess_macros)   # ← 我的正则没匹配
```

`_build_tracer` 已无 `strict` 形参 → 这些调用 `TypeError` → CLI 大面积崩。

### 处置: 回退 (从 /tmp/src_backup_batch3 恢复)

回退后复核: `stats` / `trace` rc=0; `test_design.py` **10 passed**; 工作树回到
**批次 2 的已知状态** (全量 34 failed / 3282 passed)。

## 💡 关键发现 / 关键技术 / 决策

1. **删除"命名参数"必须覆盖三种写法**: ① 独占一行 `strict=True,\n` ② **行内**
   `strict=True, other=...` ③ 行尾 `, strict=True)` —— 本次只覆盖 ①③, 漏了 ②,
   直接导致 265 failed。**教训 (第 3 次同类)**: 机械改写的"形态清单"必须先穷举并
   用 `grep -c` 对账 (改前 N 处 → 改后 0 处), 而不是改完就相信。
2. **分层顺序正确但要更小步**: 3a (CLI 侧 helper) 本身没问题且冒烟通过 —— 说明
   "**更小批次 + 每批冒烟**" 是该重构的正确节奏; 我这次把 3a 和 3b (全局删传参)
   合在一起跑, 才让 3a 的成功被 3b 的失败掩盖。
3. **核心层的 `strict` 是语义问题, 不是传参问题**: `compiler.py` 里 `self._strict`
   控制着"是否 raise / 是否返回 partial AST"两条**真实分支**, 移除它需要改
   `_do_compile` 的错误处理逻辑 (不是删参数那么简单) → 这才是批次 3 的真正难点,
   应单独立项。

## 📢 下一批的正确做法 (配方已就绪)

1. **只做 3a** (已验证有效) → 立即冒烟 + 跑 CLI 子集 → 提交;
2. 再做"删死传参": 用**三种形态**的完整清单 + `grep -c` 对账 (改前/改后都必须是 0);
3. 最后做核心语义移除 (`compiler.py::self._strict` / `unified_tracer`), 需要:
   - 删 `strict` 参数与 `self._strict` 字段;
   - 把 `if not self._strict:` 的**降级分支整块删除** (不再返回 partial AST);
   - 评估: 原先依赖 partial AST 的调用方 (如 `visualize` 的容错路径) 会变成硬失败
     → 与批次 5 的 fixture 修复一起验证。

## 📎 关联

- 方案: `iter_214_strict_default_scan.md`; 批次 1: `iter_215`; 批次 2: `iter_216`
- 备份: `/tmp/src_backup_batch3` (本次回退来源)
