# Iteration 207: R4-3 落地 — filelist `+incdir+` 现在传入编译器

**Metadata**:
- **Iteration #**: 207
- **Task Tree Level**: L2 (输入管线一致性)
- **Parent Task**: iter_205 三步计划第 2 步 (R4-4 已由 iter_206 解决)
- **Created**: 2026-09-08 GMT+8
- **Author**: 方豆 / AI 助手 (deepseek-v4-flash)
- **Outcome**: ✅ 修复落地 + 2 条回归测试

## 🎯 本次目标

iter_205 定位的 R4-3 (`--filelist` 的 `+incdir+` 在 `stats`/`visualize` 路径被丢弃)
在 iter_206 解决 R4-4 后可以安全落地。

## 🔬 实际结果

### 修复 (与 iter_205 验证过的方案一致)

- `cli/_common.py` 新增 **`_read_filelist_full()`** → `(sources, include_dirs)`
  (复用 iter_193 的 `parse_filelist`, 把 `spec.include_dirs` 交出去);
- `_read_filelist()` 变为薄包装 (保持既有 API);
- `_build_tracer()`: 合并 filelist 的 `+incdir+` 与 `--include` 后传 `UnifiedTracer`。

### 验证

| 用例 | 修复前 | 修复后 |
|---|---|---|
| `graph --filelist <带 +incdir+>` | rc=1 (UndeclaredIdentifier 级联) | **rc=0** |
| `stats --filelist <带 +incdir+>` | rc=1 | **rc=0** |
| `trace --filelist` (走 add_filelist) | rc=0 | rc=0 (无回归) |
| 简单 include (无 token paste) | rc=0 | rc=0 (无回归) |

回归测试: 追加 2 条 (stats/graph 必须 rc=0 且无 `Undeclared`; trace 路径回归) →
`test_json_contract_adversarial.py` 共 16 条; 连同 parity 文件 32 passed。

### 与 iter_205 的差别 (为什么这次成功)

iter_205 时我只做了 R4-3 的修复, 结果卡在 9 个 parity 失败上 —— 那 9 个是
**R4-4 (路径显示形态) 的既有失败**, 与 R4-3 无关。**先修 R4-4 再落地 R4-3** 的顺序
是对的: 它把"既有红"清掉后, R4-3 的真实影响 (0 失败) 才可见。

## 💡 关键发现 / 关键技术 / 决策

1. **"先修既有红, 再做新改"**: 红着的套件无法作为新改动的判据 —— 这正是 iter_205
   卡住的原因; 顺序调整 (R4-4 → R4-3) 后一轮落地。
2. **同一解析器, 消费方必须消费全部字段**: iter_193 统一了解析器, 但 CLI 侧只取
   `sources`, 把 `include_dirs` 丢了 → 分歧换了个地方出现 (tracer 侧正常 / CLI 侧异常)。
3. **R4-2 结论已在 iter_205 更正**: 我们的预处理器只做 object-like 宏, 含参宏交给
   pyslang —— "token paste 不生效"是 R4-3 的症状, 不是宏实现缺陷。

## 📢 后续

R4-1 (`-f <filelist>` 误用提示退化, 小) / push (36 commit) / 199 处 `--no-strict`
分层清单 / `check_regression.py` 阈值 / 上游 pyslang trap issue。

## 📎 关联

- 修复: `src/cli/_common.py` (`_read_filelist_full` / `_build_tracer`)
- 测试: `sim/tests/cli/test_json_contract_adversarial.py` (R4-3 × 2)
- 前序: `iter_205_r4_3_filelist_incdir.md` (真因) / `iter_206_r4_4_display_path.md` (清障)
