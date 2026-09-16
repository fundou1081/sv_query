# Iteration 229: `-f` / `--filelist` 用法纪律落地 (方豆: 这是用法的不一致不算 issue, 记录好避免这样使用)

**Metadata**:
- **Iteration #**: 229
- **Task Tree Level**: L1
- **Parent Task**: `docs/task_tree/tasks/L1_zero_red_and_policy_followups.md`
- **Created**: 2026-09-09 GMT+8
- **Author**: 方豆 / AI 助手
- **Outcome**: ✅ 成功

## 🎯 本次目标

方豆原话: **"这是用法的不一致不算 issue，记录好避免这样使用"**

上下文: iter_189 把 `visualize module -f <filelist>` 崩溃查成了"上游 pyslang
`addSyntaxTree` 原生 SIGTRAP", 并把"是否向上游报 issue"登记为待决项 (issue 正文都写好了)。
**方豆判定**: 这属于**我们自己的用法不一致** (`-f` 在本项目是 `--file` 单文件, 而很多工具
`-f` 是 filelist), 不是上游缺陷 → **不提 issue**, 要做的是**记录清楚 + 避免这样使用**。

## 🔬 落地内容

### 1. `AGENTS.md` 新增核心纪律 4 (v1.7)

```markdown
### 4. 禁止用 `-f` / `--file` 传 filelist (2026-09-09 新增)

**`-f` / `--file` 只接受 SystemVerilog 源码; filelist 一律用 `--filelist`。**
```

写清了四件事 (让读的人不用再翻历史):

| 要素 | 内容 |
|---|---|
| **为什么容易写错** | 本项目 `-f` = `--file` (单文件), 很多其他工具 `-f` = filelist → 习惯迁移即误用 |
| **误用的后果** | slang 把 filelist 内容当 script 解析 → 根节点成表达式 (`DivideExpression`, 路径里的 `/`) → `addSyntaxTree()` 原生 SIGTRAP (exit 133, 无输出、不可捕获) |
| **机械保障 (已有)** | `_reject_non_design_unit` 守卫 + 回归测试 (守卫失效时 pytest 以 exit 133 崩) |
| **方豆决定** | 不提上游 issue; 正确写法给 3 条示例 (✅ `--filelist` / ✅ `-f design.sv` / ✅ `visualize module --filelist ... --target`) |

同时: **自我审视清单**加一条
`- [ ] 我有没有用 -f / --file 传 filelist? → 如果有, 改成 --filelist (核心纪律 4)`;
**版本**加 v1.7 记录 (含方豆判定原话与背景)。

### 2. `docs/KNOWN_LIMITATIONS.md` §3.1 改写

原标题 "**pyslang 非设计单元输入 → 原生 SIGTRAP**" (把责任放在上游) →
新标题 "**`-f` / `--file` 传 filelist → 原生 SIGTRAP (用法不一致, 不是上游缺陷)**",
正文改为: 方豆判定引言 → 正确/错误用法对照 → 机制说明 → 我们的守卫 → 回归测试。
删掉原来的"**上游建议**: pyslang 应…"一句 (与"不提 issue"的判定冲突)。

### 3. `TESTING.md` 已知限制行

补上"**已立为纪律 (iter_229)**"与方豆判定 (不向上游报 issue + 指向 AGENTS 核心纪律 4)。

### 4. `iter_189` 记录

- "待方豆决定"表三行全部改为**已决定**: ① `-f` 歧义 → 记录下来避免这样使用;
  ② 上游 issue → ❌ 不提; ③ 13 个 SVG skip → 先不转正 (其中 1 个已真转正)
- issue 正文一节加**醒目标注**: "⚠️ 2026-09-09 方豆决定: **不提交** —— 判定为用法不一致,
  不作为上游缺陷上报。本节仅作技术档案保留" (保留原文, 不删 —— 历史可追)

### 5. `CURRENT_TODO.md`

把"① 上游 pyslang SIGTRAP 是否提 issue"从**待决项**移除, 改为已闭环记录。

## 📊 验证

| 项 | 结果 |
|---|---|
| 文档卫生 | `tools/check_docs.py` ✅ (死链 0 / 归档越界 0 / 未登记 0) |
| 纪律检查 | `tools/check_except_pass.py` = 0 |
| 代码影响 | **无** (本轮只改纪律与文档; 守卫与测试 iter_189 已存在) |
| 全量 canonical | 不受影响 (上一轮 3317 passed / 0 failed) |

## 💡 关键发现 / 决策

1. **归因方向决定处理方式**: 同一个现象 (进程 SIGTRAP), 若定性为"上游 bug" →
   动作是提 issue、等上游修; 若定性为"我们用法不一致" → 动作是**立纪律 + 记录 + 避免**。
   方豆的判定选了后者, 因为**触发条件是我们可以控制的使用方式** (把 filelist 传给 `-f`),
   而合法输入路径不受影响。后者更可执行 —— 不依赖第三方排期。
2. **纪律要配"为什么"**: 只写"禁止 `-f` 传 filelist"会被下一个人当成无理由的约定
   (甚至被绕过); 写清"为什么容易错 (工具习惯差异) + 错了会怎样 (静默 SIGTRAP)"才会被遵守。
   本轮的纪律条目把 `AGENTS.md` 的一贯风格 (理由 + 例证 + 机械保障) 用在了用法层面。
3. **决定要写回原始记录**: iter_189 的计划 (含写好的 issue 正文) 若不回填决定, 下一个人
   读到会以为"还没提交, 要不要提?" —— 本轮把三行待决全部改成已决定, 并保留 issue 正文
   作档案 (归档不删、历史可追, 与文档卫生规则一致)。
