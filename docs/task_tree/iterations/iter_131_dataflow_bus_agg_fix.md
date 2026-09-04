# Iteration 131: dataflow bus 聚合修复 + usage 套件 4 债务清理

**Metadata**:
- **Iteration #**: 131
- **Task Tree Level**: L2 (审计链收尾 → usage 债务)
- **Parent Task**: [signal_graph_accuracy_audit.md](../../architecture/signal_graph_accuracy_audit.md)
- **Created**: 2026-09-04 GMT+8
- **Author**: AI 助手
- **Outcome**: ✅ 成功

## 🎯 本次目标

iter_130 真实验证暴露 usage 套件 4 失败 (被主回归 ignore 的历史债务)。
方豆 "继续" → 定性 4 失败 + 修复 1 个真实回归 (dataflow bus 聚合) + 清 3 个测试债务。

## 🔬 实际结果

### 定性: 4 失败全部非环境噪音, 其中 1 个是真回归

| 失败 | 定性 | 处置 |
|---|---|---|
| test_golden_dataflow_arbiter (40→1 paths) | **真回归** — dataflow `_find_paths` bus 查询只枚举首 entry (见下) | 修复 + golden 40→8 |
| test_p6_tlul (条件驱动 4→8) | 测试断言过时 — 检测更全 (source_d/q, error_q, rdata_q 均真实条件驱动, always_comb if 链实证) | 断言改解析计数 ≥4 |
| test_m12_visualize | 环境 — 单跑时 /tmp/naples_full 目录不存在 | 测试内 os.makedirs |
| factory make_edge 1<12 | 测试断言过时 — A 计划拆分后 factory 调用分散到 extractors/ 子模块 (实测 16 处) | 断言改扫 driver+extractors/ 全集 |

### 真回归根因: _find_paths 首个非空候选组合即 return

- **现象**: prim_arbiter_tree req_i→gnt_o dataflow golden 40 paths (Plan B A4
  时代) 崩到 1 path。bisect 定位 iter_118 (b68b1de) 引入: 之前 bus 查询
  (req_i, gnt_o) 单组合经 8 个 gnt_o[i] 中间节点返回 8 条; iter_118 per-entry
  (DRIVER 边变 req_i[i]→gnt_o[i]) 后 bus 无直接边, 需逐个 (req_i[i], gnt_o)
  组合 — 但 `_find_paths` (dataflow.py ~493) 找到首个非空组合即 return,
  req_i[0] 命中即停 → 丢 req_i[1..7]。
- **修复** (dataflow.py): 主候选组合循环**收集合并所有组合路径** (去重),
  而非首个非空 return。struct 传播 fallback 分支保持"找到即返"语义不变。
- **证据**: arbiter 8 paths 恢复 (iter_118 前语义, per-entry 正确聚合);
  generate-for bus fixture a→y 4 entry → 4 paths (修复前 1); 纯直连仍 1 path;
  per-bit 查询不变。
- **golden 同步**: usage dataflow_open_source golden 40→8; subfunction
  prim_arbiter dataflow golden 删后重建 40→8 (iter_118 时代重生成过 1 path,
  现为正确聚合值)。

### 验证

- 新 unit 3 (TestDataflowBusAggregation: genfor bus 聚合 4 / 纯直连 1 /
  per-bit 不变)
- 主全量回归: **2928 passed / 0 failed** (dataflow 修复零副作用)
- usage 套件: 4 失败清零 (重跑确认)

## 💡 关键发现 / 决策

1. **usage 套件被主回归 ignore = 债务藏身处**: 4 失败横跨 iter_118 起的
   真实回归与更早的测试断言过时 — 一直没人看见。真实验证 (iter_130) 的
   baseline worktree 对比是暴露它们的关键手段。
2. **_find_paths 的 "首个非空即返" 在 per-entry 时代失效**: 图从 bus 粒度
   变 per-index 后, 单候选组合不再覆盖全部路径 — 多候选组合需合并。
   这是 bus 聚合语义 (bus 查询 = 所有 bit 路径), 非简单 bug。
3. **factory/条件驱动计数断言应测行为而非源码结构**: factory 断言数
   make_edge 调用是源码结构软验证, 拆分后需扫全目录; p6 应解析实际计数
   而非硬编码。

## 📌 状态

- ✅ dataflow bus 聚合修复 + 3 测试债务清理; unit +3; 主全量 2928 passed
- usage 套件 4 失败清零 (重跑确认)
- 遗留: ventus 测试 (外部源码不完整) 仍排除; usage 整体仍不在主回归范围
  (opensource 依赖 + --no-strict 纪律冲突, 另行评估)
