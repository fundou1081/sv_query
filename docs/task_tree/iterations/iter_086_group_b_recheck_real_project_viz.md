# Iteration 086: B 组复查 — real_project_viz 2 个真实失败 (1 修 + 1 暂缓)

**Metadata**:
- **Iteration #**: 086
- **Task Tree Level**: L1
- **Parent Task**: Test_Assets_ABC → B 修 integration pre-existing 失败 (复查)
- **Created**: 2026-09-02 GMT+8
- **Author**: AI 助手 (方豆指示 "elk 先不管, 其他的先修")
- **Outcome**: ⚠️ 部分完成 (darkriscv 已修; picorv32 ELK 根因已定位, 方豆拍板暂缓)

## 🎯 本次目标

方豆要求确认 Task B (修 integration 14 个 pre-existing 失败) 的真实状态。
CURRENT_TODO 标 B ✅ 完成 (iter_082: 2 断言修复 + 12 环境定性), 但需验证
"可写 HOME 下 integration 0 failed" 是否可信。

## 📊 当前状态 / 预期结果

- iter_082 结论: 14 失败 = 2 真实断言 (已修) + 12 环境 artifact (cache 不可写)
- 本会话为 danger-full-access, HOME 可写 → 直接跑 integration 验证真实状态

## 🔬 实际结果

### 实测: integration = 417 passed + **2 failed** + 3 skipped

2 个失败全是 `test_real_project_viz.py` (darkriscv / picorv32) — iter_082 把
这 2 个误分类为"环境 artifact"。真实情况:

| 项目 | 失败原因 | 性质 |
|---|---|---|
| darkriscv | 断言 `'digraph' in dot_text` — `--dot` 自 V100 起写 **SVG**, 断言是 DOT 时代残留; CLI 本身成功 | 测试断言过时 |
| picorv32 | ELK `Referenced shape does not exist: port_picorv32_axi_dot_mem_axi_bvalid` | **真实管线 bug** |

### iter_082 "0 failed" 为什么失真

验证用 `HOME=/tmp/svq_home` 重定向 → `~/my_dv_proj/picorv32/...` 展开成
`/tmp/svq_home/my_dv_proj/...` (不存在) → 这两个测试动态 `pytest.skip('not found')`,
根本没跑。**HOME 重定向验证法会坑掉 `~` 依赖的真实项目路径测试** — 假绿来源。

### picorv32 ELK 根因 (证据链完整, 供后续修复)

- edge e44 引用 `port_picorv32_axi_dot_mem_axi_bvalid`, 但全图只 emit
  `port_picorv32_axi_dot_axi_adapter_dot_mem_axi_bvalid`
- expr_tree key 是**模块级**路径 (`picorv32_axi_adapter.mem_ready`), viz 端口路径是
  **嵌套模块级** (`picorv32_axi.axi_adapter.mem_axi_bvalid`)
- **emit 侧** `_walk_refs`: `parent_module.label` = `picorv32_axi_adapter.mem_axi_bvalid`
  ∉ `input_paths` → 不收集 → 不 emit
- **edge 侧** `render_tree` SignalRef fallback: 短名 `mem_axi_bvalid` →
  `_resolve_port_id` 取 `_fulls[0]` = `picorv32_axi.mem_axi_bvalid` → 悬空 id
- 两侧 fallback 规则不一致 = 同一端口两种 id (elk_bridge Fix A-G / V16.12/16.13
  反复修补的 bug 家族)
- 测试历史: 该测试自引入 (6e8256c, 2026-08-25) **从未绿过** (当时 darkriscv 还
  RecursionError, cycle detection 是后来 a939d68 才加) — 不是 iter_082 之后回归

### 本次修复 (方豆 "其他先修")

- **darkriscv**: 断言改为校验 SVG (`<svg` 根 + target 模块名在文本), CLI 标志改用
  `--svg` (主标志, --dot 是 deprecated alias)
- **删 `--no-strict`**: 违反 AGENTS.md 硬规则 #1; 实测 strict 模式 darkriscv 可过
- **picorv32**: 保持真实失败可见 (不设 xfail), 根因已记录, 等方豆排期

## 💡 关键发现 / 决策

1. **"环境 artifact" 结论必须复核**: iter_082 的 12 个里只有 10 个真是环境问题,
   2 个 (real_project_viz) 因验证方法缺陷被误分类。
2. **HOME 重定向验证法的副作用**: `~` 展开依赖 HOME, 真实项目路径测试会被动态
   skip → 假绿。TESTING.md 需补警告。
3. **测试"从未绿过" ≠ 回归**: real_project_viz 是引入时就挂的测试 (aspirational),
   修复优先级应低于"最近回归"类。
4. **决策**: 方豆 "elk 先不管, 其他的先修" → elk_bridge 根因修复另行排期;
   darkriscv 断言 + 纪律 + 文档本次完成。

## 📌 状态

- ✅ darkriscv 断言修复 + 删 --no-strict (本 commit)
- ⏸ picorv32 ELK 根因修复暂缓 (根因记录如上)
- ✅ 文档更正: CURRENT_TODO / TEST_MAP §0 / TESTING.md 警告 / L2 任务文件 / overview
- 新基线: integration = 418 passed + 1 failed (picorv32) + 3 skipped

---

## ✅ 后续修复 (2026-09-02, iter_106)

**picorv32 ELK dangling port 已修** (方豆 "继续" 拍板重启):
- 修复: elk_bridge `_resolve_emitted_port_id` (短名 fallback 已 emit 优先)
  + 最终兜底补发 (平铺阶段扫全部边端点)
- 验证: integration **419 passed + 0 failed** (历史首次全绿);
  test_real_project_viz 3 passed
- 根因分析 (本节) 保持有效, 修复细节见 iter_106
