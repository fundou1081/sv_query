# V16 Viz 清理 — 修改计划

> 创建: 2026-08-14 09:19
> 目标: 修复 case26 viz 中 V15 设计假设与用户期望不一致的问题
> 决策: 用户选择全部 6 项 (Phase 1 + 2 + 3)

## 背景

V15 的两个设计假设已被用户反馈需要修订：

1. **V15 fix 3 跳过中间 wire 节点** → 用户说"golden_hier_top 范围不对, 4 个 wire 都没出现"
2. **const 节点硬编码顶层** → 用户说"常量节点应该在 clamp 里, 而不是 top"

## 调研结论

通过 dump VizData (`build_viz_data` 输出) 验证：

- **VizNode.cluster_id 字段已填好**（case26: 25 nodes, cluster_id ∈ {'', 'u_scale', 'u_off', 'u_clamp_u', 'u_clamp'}）
- **VizData 不含 const 节点**（25 nodes, 0 CONST kind）—— const 节点在 `expr_trees_to_elk` 渲染阶段才被 emit
- **V15 fix 3 设计决策**：`elk_bridge.py:1015-1024` 故意跳过中间 wire 节点，改为 emit 直接 port→port 拼接边
- **const 硬编码顶层**：`elk_bridge.py:558-559` 对 `const_*` prefix 硬编码 `cluster_id = ''`

## 修改列表

### Phase 1（低风险核心）

| # | 改动 | 文件 | 风险 |
|---|---|---|---|
| 1.1 | const 节点 emit 时计算 `cluster_id` 字段 | `src/trace/core/graph/viz/elk_bridge.py:413-420` | 🟡 中 |
| 1.2 | `_child_cluster` 改为读 const 的 `_meta.cluster_id` 字段（删硬编码顶层） | `src/trace/core/graph/viz/elk_bridge.py:558-559` | 🟡 中 |
| 1.3 | 32-case strict 验证 | `regress_golden_mini` | 🟢 低 |

### Phase 2（高风险核心）

| # | 改动 | 文件 | 风险 |
|---|---|---|---|
| 2.1 | 撤回 V15 fix 3，保留中间 wire 节点 | `src/trace/core/graph/viz/elk_bridge.py:1015-1084` | 🟠 高 |
| 2.2 | 跨 instance 边改 emit 为两步 (X.dout → wire → Y.din) | 同上 | 🟠 高 |
| 2.3 | 32-case strict 验证 + 视觉检查 case26 | `regress_golden_mini` | 🟢 低 |

### Phase 3（辅助）

| # | 改动 | 文件 | 风险 |
|---|---|---|---|
| 3.1 | `_viz_to_jsonable` 补 dump 字段 (cluster_id, instance_path, module_type, is_port, is_function, def_name, depth) | `sim/tests/manual/regress_golden_mini.py:118-130` | 🟢 低 |
| 3.2 | `build_viz_data` 从 `expr_trees` 提取 const 节点 emit 进 VizData | `src/trace/core/graph/viz/viz_data_builder.py` | 🟠 中-高 |
| 3.3 | 32-case strict 验证 | `regress_golden_mini` | 🟢 低 |

## 预期结果

- **case26 viz**：4 个 wire (scaled, offsetted, clamped_w, clamped) 出现在 `golden_hier_top` cluster 内部
- **const 节点归位**：`11'd255` / `8'd255` 在 `u_clamp`/`u_clamp_u` cluster 内，`3'b0` 在 `golden_hier_top` 顶层
- **32-case strict**：32/32 PASS（可能需要更新部分 checker 期望值）
- **回归无副作用**：case1-25 纯顶层 case 无变化

## 风险评估

| 风险 | 级别 | 缓解 |
|---|---|---|
| 跨 instance 边 routing 变化 | 🟠 高 | 分两步走，先 const 后 wire |
| checker 期望值不匹配 | 🟡 中 | 跑 32-case，看具体 fail 点 |
| `_viz_to_jsonable` 字段缺失影响 dump 验证 | 🟢 低 | 补字段只加不删 |
| 32-case 期望变化 | 🟡 中 | 旧 case 1-25 纯顶层无变化 |

## 实施原则

1. **每个 Phase 单独 commit** 便于回滚
2. **每个 Phase 单独跑 32-case 验证**
3. **不改 src/trace/core/connection_extractor.py**（V15.2 修复不动）
4. **不改 src/trace/core/semantic_adapter.py**（V15.2 修复不动）
5. **如失败 → 回滚到上一 stable commit**

## Commit 计划

```
commit A: feat(viz): V16.1 const 节点归位 (Phase 1)
commit B: feat(viz): V16.2 wire 节点回归 + 跨 instance 边两步 (Phase 2)
commit C: feat(viz): V16.3 dump 字段补全 + VizData emit const (Phase 3)
```

## 验收

- [ ] 32-case strict 32/32 PASS
- [ ] case26 viz 显示 4 个顶层 wire
- [ ] case26 viz 紫色跨 instance 边 3 条（不破坏 V15 fix 3 之前）
- [ ] case26 viz const 节点 (11'd255, 8'd255) 在 u_clamp / u_clamp_u cluster 内
- [ ] 视觉确认 + 飞书发图给用户
