# Iteration 130: iter_126~129 真实验证收尾 — 零副作用确认

**Metadata**:
- **Iteration #**: 130
- **Task Tree Level**: L2 (准确性审计链收尾 → 真实验证)
- **Parent Task**: [signal_graph_accuracy_audit.md](../../architecture/signal_graph_accuracy_audit.md)
- **Created**: 2026-09-04 GMT+8
- **Author**: AI 助手
- **Outcome**: ✅ 成功 (零副作用确认)

## 🎯 本次目标

iter_126~129 连续改动 (A1 CLI auto-target / A2 位提升 / A3 自环排除 /
CLOCK 守卫 / inout 分支 / interface 成员桥) 已在 2928 全量回归绿, 但需在
**真实设计**上确认无副作用 (单元回归只覆盖 fixture)。方豆 "继续" + 取消
方向提问 → 按推荐路径做真实验证收尾。

## 🔬 实际结果

### 1. 真实项目图构建冒烟

| 项目 | 规模 | 结果 |
|---|---|---|
| aes (12 文件, /openrtl/aes) | 11292 nodes / 20522 edges | ✅ 构建成功; fanin 抽样合理 (aes_out_data ← ciphertext reg[127:64]/[63:0]; valid_out ← 254 内部驱动链) |
| CORDIC/cordic.v | 68 nodes | ✅ 构建成功 |
| openofdm_tx filelist | — | ⚠️ 源码自身 UsedBeforeDeclared 编译错 (12 处, 与图逻辑无关) |
| cc_stream_intf (common_cells) | — | ✅ interface 定义层构建; 完整模块需依赖链 (cc_pkg 等) 未拉全 |

### 2. usage 套件 (真实项目 CLI 层) — 4 失败全部基线既有

跑 `sim/tests/usage` (排除 ventus, 全量回归一直 ignore 该目录):
245 passed / 4 failed / 21 skipped。4 失败逐一用 **baseline worktree**
(检出 f006ae4 = iter_125 前) 复跑 → **全部同样失败**:

| 失败测试 | 现象 | 基线同失败 |
|---|---|---|
| test_golden_dataflow_arbiter | golden 40 paths → actual 1 | ✅ (f006ae4 同) |
| test_p6_tlul_controlflow | 条件驱动 (4)→8, 数量翻倍 | ✅ 同 |
| test_m12_visualize_filelist | 待对齐 | ✅ 同 |
| test_graph_builder_factory_usage_dominates | make_edge 1 < 12 | ✅ 同 |

→ iter_126~129 对真实项目零副作用; 4 失败为 opensource/V6.9 时代
遗留 (依赖 --no-strict + 外部 filelist, AGENTS.md 已禁 no-strict, 属
历史债务另行处理)。

### 3. CLI 层 (A1 auto-target 直接验证面)

- AES 12 文件 filelist, **无 --module** (auto single-top 生效): rc=0,
  4649 SVG rects, Data 5554 / Control 2274 / Clock 1168 — 正常
- minimal_3module filelist + `--module top_minimal`: rc=0, 25 nodes within target
- AES filelist + `--module aes_top_buffered_wrapper`: ELK 报
  "Referenced shape does not exist: sig_W_array[0]_wire" — 这是 overview
  **Plan B Step G** 记录的既有 ELK dangling 问题 (Active Task 原文现象),
  非 iter_126~129 引入

### 4. Push

- 分支 chore/v11-only-cleanup 12 commits (iter_121~129 时代) 已 push 至
  backup remote (e0d5652..3288d2a)

## 💡 关键发现

1. **usage 套件 4 失败 = 历史遗留**: 用 baseline worktree (f006ae4) 复跑
   完全同失败 → 与 iter_126~129 无关。其中 prim_arbiter golden 40→1 paths
   与 controlflow 4→8 数量差异是 opensource fixture/--no-strict 时代产物,
   且 usage 目录不在全量回归范围 (ignore) — 应单独记录为已知债务。
2. **ELK dangling (Plan B Step G) 仍在**: AES `--module` 触发
   "Referenced shape does not exist" — overview Active Task 记录在案,
   本次验证顺带复现确认未解决 (属 L4 viz 层, 独立 backlog)。
3. 验证方法: worktree 检出基线对比是判定"是否本次引入"的可靠手段
   (比猜快, 比 git stash 干净 — stash 会动当前工作区)。

## 📌 状态

- ✅ iter_126~129 真实设计零副作用; usage 4 失败归因基线既有
- 新增已知债务记录: usage 套件 4 失败 (opensource/--no-strict 历史),
  ELK dangling Plan B Step G (既有)
- backlog 未动: A2 位对位折算 (大改, 待方豆指示), gate G-2/G-3,
  semantic 消歧, inout/interface 深语义
