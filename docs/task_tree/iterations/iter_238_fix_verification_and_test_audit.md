# Iteration 238: 针对本轮修复的测试评审 + 覆盖补强 + 全量复核 (发现并修 `hierarchy` 树失真)

**Metadata**:
- **Iteration #**: 238
- **Task Tree Level**: L1
- **Parent Task**: `docs/task_tree/tasks/L1_agent_semantic_capability_gaps.md`
- **Created**: 2026-09-09 GMT+8
- **Author**: 方豆 / AI 助手 (方豆: "先跑一下测试，针对修复的地方，评估是不是需要补充一些新的测试。确认功能正确。通过完整的测试集评估现在整体状态")
- **Outcome**: ✅ 成功 (补 16 条测试; 又发现并修 1 个语义缺陷; 全量 **3380 passed / 0 failed**)

## 🎯 本次目标 (方豆四问)

1. 针对**修复的地方**跑测试
2. **评估是否需要补测试**
3. **确认功能正确** (不止单测, 要真实输入)
4. 跑**完整测试集**评估整体状态

## 1️⃣ 针对修复处跑测试

| 修复 | 涉及模块 | 跑到的测试 |
|---|---|---|
| bug #6 `get_instances()` | `unified_tracer.py` | `test_cli_instance_query.py` + 7 个引用 MIG/实例的既有套件 |
| bug #7 `PathResolver` 跨模块 | `module_instance_graph.py` | `test_cli_semantic_queries.py` + `test_mig_*` / `test_pr3_mig_fallback` / `test_pr4_visualize_l2` / `test_cross_module_tracking` / `test_portconn_native_poc` / `test_comment_handling` / `test_mig_validator` |

**结果: 122 passed** (既有测试面 + 两个新文件), 0 回归。

## 2️⃣ 覆盖审计 → 补了 16 条测试

审计发现的**空白** (都补上了):

| 空白 | 为什么重要 | 新测试 |
|---|---|---|
| `find_all_paths` **截断** | 上限是我新加的; 不测等于没保证 | `test_max_paths_caps_results` / `test_max_flag_wires_truncation` |
| `max_depth` 上限 | 同上 (防环爆) | `test_max_depth_bounds_search` |
| **环安全** | DFS 在有环图必须终止且不重复节点 | `test_cycle_graph_terminates` (+ `test_cycle_reachable_paths`, 用真实组合环 fixture `b↔c`) |
| `find_path` **最短跳数**契约 | 我在 docstring 写了"最短", 必须有测试 | `test_find_path_is_shortest_hop` |
| **未知节点**不抛异常 | 健壮性 (图里没有的 id) | `test_unknown_node_does_not_raise` |
| **多级嵌套** parent 推导 | bug #6 的修复只在 1 层 fixture 上验过; 深层才是真考验 | `test_multi_level_parent_chain` (top→mid→leaf) |
| **空结果 vs 失败** 的区分 | "无参数模块"/"无 class 设计" 应 `ok=true, count=0`, 不是报错 | `test_instance_without_parameters` / `test_design_without_classes` |
| `paths` 同点 / 未知 dst | 边界契约 | `test_same_src_dst_single_node_path` / `test_unknown_dst_reported` |

新增文件 `sim/tests/unit/test_path_resolver_semantics.py` (**9 passed**) —— 把 PathResolver 的
**不变式与边界**独立成文件, 便于日后回归定位; `test_cli_semantic_queries.py` 14 → **21 passed**。

## 3️⃣ 真实输入功能确认 → 发现 `hierarchy` 树失真 (第 8 个问题)

用**真实多文件项目** (`scheduler_minimal/filelist.f`) 跑新命令:

```
instances: 7 个 ✓
hierarchy: 7 实例 / **7 根**   ← ⚠️ 不对
ports:     9 个 {input: 5, output: 4} ✓
instance:  sourceD 端口数 4 ✓
params:    0 个 [] ✓
```

**问题**: `hierarchy` 把 7 个子实例各自当成根。根因: **顶层模块本身不是"实例"**,
所以它的子实例 `parent` 指向一个不在实例表里的路径 → 旧逻辑把"parent 不认识"直接当根。
真实项目因此显示"7 实例 / 7 根", 完全看不出设计层级 (而 `arch show` 显示的是 1 个顶层 + 7 子)。

**修法**: 为这类 parent 造**合成根** (`synthetic: true`, `full_path` = 顶层模块名),
树恢复真实层级; 同时 `instance_count` **只数真实实例** (合成根不计), 新增 `tree_node_count` 区分。

修后:
```
root=1  真实实例=7  树节点=8  根=Scheduler_minimal(synthetic=True)
```

> 这是本轮**第 3 次**印证同一条经验: **fixture 单测通过 ≠ 功能正确** ——
> 前面 14 条 CLI 断言全绿, 真实项目一跑就暴露树失真 (fixture 只有 1 层, 看不出这个 bug)。

## 4️⃣ 完整测试集评估

| 阶段 | 全量 canonical |
|---|---|
| 补测试前 (iter_237 提交时) | 3364 passed / 0 failed |
| 补 16 条测试后 (9 resolver + 7 CLI) | **3380 passed / 0 failed** |
| 修 `hierarchy` 失真后 (仅改断言, 未加测试) | **3380 passed / 0 failed** ← 最终 |

> 更正: 我最初把"修 hierarchy"也记成 +16 条 (3364→3380→3396), 那是**重复计数** ——
> 深层测试 (多级嵌套) 属于那 16 条里的, hierarchy 修复本身只更新了断言。数字以实测为准。

`check_cli_layers` rc=0 / `gen_cli_surface --check` ✅ / `check_docs` ✅ / `check_except_pass` 0 /
`scan_strict` 0 —— 纪律检查全绿。

## 💡 关键发现 / 决策

1. **"修复处跑测试"必须包含既有测试面**: 我只跑自己新写的测试是不够的 ——
   `PathResolver` 被 `test_mig_*` / `test_pr3_mig_fallback` / `test_pr4_visualize_l2` 等 8 个既有文件间接覆盖,
   它们才是"我改的东西没弄坏别的"的证据 (122 passed)。
2. **新增能力要有"边界测试"**: 截断/深度上限/环/未知输入这四类是我的实现里**新引入的机制**,
   不测就等于把风险留给用户。特别是**环安全** —— 我用真实组合环 fixture 验证 DFS 终止。
3. **真实输入是最后一关**: `hierarchy` 的树失真在 fixture 上永远看不到 (fixture 是 1 层)。
   → 建议把"真实多文件项目跑一遍新命令"固化成新命令的验收步骤 (可写进 TESTING.md)。
4. **空结果 ≠ 失败**: "无参数模块"和"找不到模块"必须给不同响应 (前者 `ok=true,count=0`,
   后者 `ok=false` + rc=1) —— 这对 agent 很重要, 否则它无法区分"确实没有"和"查错了"。

## 📎 产物

- 新增测试: `sim/tests/unit/test_path_resolver_semantics.py` (9 条) + `test_cli_semantic_queries.py` +7 条
- 修改: `src/cli/core/semantic/instances.py` (**hierarchy 合成根 + 计数修正**)
- 测试契约更新: `test_cli_instance_query.py` / `test_cli_semantic_queries.py` 的 hierarchy 断言
- 文档: 本记录 + `CURRENT_TODO.md` + `overview.md` + `INDEX.md`
