# Iteration 106: picorv32 ELK dangling port 修复 (iter_086 暂缓项)

**Metadata**:
- **Iteration #**: 106
- **Task Tree Level**: L1 (viz 管线)
- **Parent Task**: B 组 real_project_viz 暂缓项 (方豆 "elk 先不管" → 本轮 "继续")
- **Created**: 2026-09-02 GMT+8
- **Author**: AI 助手
- **Outcome**: ✅ 成功 — integration 全绿 (2836 passed + 7 skipped, 0 failed)

## 🎯 本次目标

修复 iter_086 定位的 picorv32 ELK dangling port bug:
`Referenced shape does not exist: port_picorv32_axi_dot_mem_axi_bvalid`。

## 📊 当前状态 / 预期结果

- test_real_project_viz[picorv32] 自引入 (6e8256c) 从未绿过
- 根因 (iter_086): edge 侧 SignalRef 解析与 emit 侧端口发射不一致

## 🔬 实际结果

### 根因 (iter_086 定位 + 本轮细化)

expr_tree key 是**模块级**路径 (`picorv32_axi_adapter.mem_ready`), viz 端口路径
是**嵌套实例级** (`picorv32_axi.axi_adapter.mem_axi_bvalid`)。两处不一致:

1. **emit 侧** `_walk_refs`: `parent_module.label` = `picorv32_axi_adapter.mem_axi_bvalid`
   ∉ input_paths → 不收集 → 不 emit
2. **edge 侧** `render_tree` SignalRef fallback: 短名 `mem_axi_bvalid` →
   `_resolve_port_id` 取 dedup `_fulls[0]` **任意项** = `picorv32_axi.mem_axi_bvalid`
   → 悬空 id

### 修复 (两层)

1. **`_resolve_emitted_port_id` (preference)**: 短名 fallback 优先解析到**已 emit**
   的端口 id (emit 循环先跑, `_emitted_port_ids` 可用) — mem_axi_bvalid 场景
   复用 adapter 层孪生, 不再任意取 `_fulls[0]`
2. **最终兜底校验**: expr_trees_to_elk 返回前扫**全部**边端点 (root_edges 平铺时),
   未 emit 的 port id 补发 shape — resetn 场景 (无已 emit 孪生) 触发, 补发 1 个
   `port_picorv32_axi_dot_resetn`。注意 _wrap_into_clusters 内既有 B1v2 防御
   只扫顶层 edges, cluster 内边会漏 — 本处在平铺阶段全覆盖。

### 验证

- picorv32: mem_axi_bvalid 走 preference (复用孪生), resetn 走兜底补发 →
  ELK 布局成功, 746KB SVG
- **integration 全量: 419 passed + 3 skipped, 0 failed** (历史首次)
- 全量 (排除 usage): **2836 passed + 0 failed + 7 skipped**
- 仅改变"原本会崩"的场景 (preference 对已 emit 场景零变化; 兜底只加 shape) —
  零回归风险, 实测确认

## 💡 关键发现 / 决策

1. **同类 bug 两个实例**: mem_axi_bvalid (有孪生, preference 修) vs resetn
   (无孪生, 兜底修) — 只修一处会留另一个, 两层组合才闭环。
2. **防御补发的扫描范围**: 既有 B1v2 防御在 cluster 重分组后只扫顶层 edges,
   漏 cluster 内边 — 兜底必须放在平铺阶段。
3. **"已 emit 优先"是正确语义**: edge 引用 emit 侧实际有的端口, 而非任意
   _fulls[0] — 与"单源 of truth"注释一致, 修的是根因不是症状。

## 📌 状态

- ✅ picorv32 ELK 修复 (preference + 兜底), test_real_project_viz 3 passed
- ✅ integration 419 passed + 0 failed (历史首次全绿)
- 文档: TEST_MAP / iter_086 更正 / L2 B 段 / overview 同步
