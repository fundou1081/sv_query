# Iteration 210: 清理测试里的 `--no-strict` — 第一批 (202 → 91)

**Metadata**:
- **Iteration #**: 210
- **Task Tree Level**: L1 (纪律强制)
- **Parent Task**: 方豆指示 "使用 no strict 明确违反开发纪律, 不可接受, 必须更改"
- **Created**: 2026-09-08 GMT+8
- **Author**: 方豆 / AI 助手 (deepseek-v4-flash)
- **Outcome**: ⚠️ 部分完成 (111 处已清, 91 处待处置) — **如实记录**

## 🎯 本次目标

AGENTS 核心纪律 1 明令禁止在 `run_cli.py` / 测试 / 脚本里使用 `--no-strict`。
实测 `sim/tests/` 有 **202 处 / 41 文件** (另有 `tools/` 脚本与 CLI 帮助文本提及)。

## 🔬 实际结果

### 第一批: 机械清理 (25 文件 / 122 处)

脚本按三种形态删除 (`"--no-strict", ` / `, "--no-strict"` / 兜底), 每改一个文件
`ast.parse` 校验后才写回 → **25 文件 / 122 处**成功; 12 文件因结构复杂解析失败而
**原样保留** (未写入)。

### 暴露的问题: 1 个文件的 fixture 有**真实 elaboration 错误**

清理后跑 `unit + cli` 子集: **16 failed / 1563 passed** —— 全部集中在
`sim/tests/cli/test_visualize_teach_nested_mux.py`。

**结论 (正是纪律要防的事)**: 这些测试过去**靠 `--no-strict` 容忍 fixture 的真实
错误** (优雅降级成 partial AST 后断言仍然通过)。flag 一撤, 真实问题立刻现形。

处置 (本轮): **回退该文件** (保留 flag) + 记录为待修 fixture; 其余 24 文件保持
已清理状态 (它们撤掉 flag 后依然全绿 = flag 本来是多余的)。

### 剩余 91 处 / 22 文件分类 (待后续轮次)

| 类别 | 规模 | 处置建议 |
|---|---|---|
| **专门测试该 flag 行为** | `test_stats_non_strict.py`(13) + `test_strict_default.py`(20) + `test_snapshot_non_strict_mode.py`(2) | 方豆指示"不可接受" → 建议**归档**这些文件 (移出代替删除), 或改写为只测 strict 行为 |
| **fixture 有真实错误** | `test_visualize_teach_nested_mux.py`(7) | **先修 fixture** (找出 SV 错误) 再撤 flag |
| **结构复杂未清理** | 其余文件 (合计 91 处中的大部分) | 逐个手工清理 (多行列表/条件拼接), 撤后跑该文件验证 |
| `tools/*.py` 脚本 | `coverage_gen_demo.py` / `llm_schema_validate.py` | 同属"脚本"范畴 → 一并清理 |
| `src/cli/**` 帮助文本 | 多处 "Use --no-strict ..." + 选项定义 | **选项本身保留** (给用户的逃生舱); 但**提示语**要审: iter_209 已让"输入类型错误"不再建议它 |

## 💡 关键发现 / 关键技术 / 决策

1. **`--no-strict` 是"假绿"生产器**: 16 个测试在优雅降级下"通过", 但它们断言的
   其实是**残缺 AST 的输出** —— 撤掉 flag 才知道 fixture 本来就编不过。
2. **机械清理必须带语法校验 + 备份**: 我先 `cp -r sim/tests /tmp/tests_backup_nostrict`,
   再逐文件 `ast.parse` 校验后才写回 → 12 个复杂文件被安全跳过, 失败文件可从备份精确回退
   (本轮就用了)。
3. **纪律 vs 绿灯的冲突要如实呈现**: 用户指示"必须改", 但一次性撤完会留下 16 个红测试
   (且红的原因是真 fixture 错误)。**分批 + 先修 fixture** 才是正解, 而不是把 flag 加回去
   或改断言。

## 📢 下一步

1. 修 `test_visualize_teach_nested_mux.py` 的 fixture (看它的 SV 错误), 然后撤 flag;
2. 处置 3 个 flag-behavior 测试文件 (建议归档);
3. 手工清理 11 个复杂文件 (38 处) + `tools/` 脚本;
4. 审 `src/cli/**` 的 `--no-strict` 提示语 (选项保留, 提示语气/discouragement 待定)。

## 📎 关联

- 纪律: `AGENTS.md` 核心纪律 1
- 备份: `/tmp/tests_backup_nostrict` (本轮回退来源)
