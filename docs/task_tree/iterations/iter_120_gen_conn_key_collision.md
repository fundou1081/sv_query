# Iteration 120: generate 实例连接 key 碰撞修复 — legacy 族移除 + 逐实例路径

**Metadata**:
- **Iteration #**: 120
- **Task Tree Level**: L2 (iter_119 观察项深挖 → 真实缺口)
- **Parent Task**: [tasks/L2_conn_rangeselect_naming.md](../tasks/L2_conn_rangeselect_naming.md) 后续
- **Created**: 2026-09-03 GMT+8
- **Author**: AI 助手
- **Outcome**: ✅ 成功

## 🎯 本次目标

iter_119 观察: G2[0] 实例连接在图里缺失/错挂 (G2[1] 源重复连两个切片)。
深挖 → 两个叠加根因, 均真实缺口:

1. **legacy get_generate_instances 族嵌套时丢 root**: 连接路径 'u_m2.G2[0].u_leaf'
   缺 'top' → 同 key 覆盖正确 indexed 族 → 实例连接整条消失
2. **module_to_path key 不含父实例路径**: 同一模块多实例 (G1[0]/G1[1] 各含
   m2, m2 内同名 G2 entry) → key (module, name, gen) 碰撞 → 后写覆盖 →
   部分实例 (G2[0] 跨两份 m2) 连接错挂

## 🔬 实际结果

### 探查

- get_instance_connection 输出正确 (G2[0]→a[1:0]/y[1:0]) — 下游 connection
  extractor 丢边
- connection extractor 单跑: 边存在但**缺 'top' 前缀** ('u_m2.a[1:0] → ...')
  → _filter_by_target 丢弃 → 终图 0 连接
- module_instances 四份 leaf 齐全 (2 m2 副本 × G2[0]/[1]) — 非枚举丢失

### 修复 (connection_extractor)

| # | 改动 | 理由 |
|---|---|---|
| 1 | 两处 instances 去掉 `+ get_generate_instances()` | iter_113 曾因路径加倍而保留 legacy; **iter_117 修了 indexed 族 get_path gen_block 去重后 legacy 已冗余** — 且 legacy 嵌套时父路径丢 root → 覆盖正确路径。移除后 generate 只走 indexed 族 (hp 全路径) |
| 2 | 第三阶段改**逐实例路径** `paths_by_info[_idx]` (与 instances 同序) | module_to_path key 无父实例路径 → 多实例同名 gen entry 碰撞; 逐实例取 get_path 无碰撞 |

### 验证

- minimal 单级: 4 条 leaf 连接全路径 + 正确归属 (G2[0]→y[1:0]/a[1:0],
  G2[1]→y[3:2]/a[3:2]), 0 占位 (iter_120 前 0 连接)
- 4 层 fixture: **4 条 leaf 连接全对** — G1[0].G2[0]→y[1:0] / G1[0].G2[1]→y[3:2]
  / G1[1].G2[0]→y[1:0] / G1[1].G2[1]→y[3:2] (修复前 G2[0] 全丢)
- 受影响批次 (genfor/cordic/CLA/chain/gate/nested/connection/generate/d1)
  **101 passed** 零回归 (legacy 移除安全 — iter_117 兜底)
- unit test_nested_generate_instance 13→14 (per-entry 归属断言 + minimal)
- 全量回归结果见 commit

## 💡 关键发现 / 决策

1. **legacy 族的"必需"是历史包袱**: iter_113 保留它是因为当时 indexed 族路径
   加倍 (iter_117 已修) — 修复链路上"先修根因再清冗余"的顺序再次奏效
   (iter_113 → iter_117 → iter_120 三段才把 generate 实例连接做对)。
2. **module_to_path key 设计缺陷**: (module, name, gen) 无父路径, 对"同一模块
   多实例"必然碰撞 — 逐实例路径 (对齐索引) 是通用解; 该 map 仅剩 fallback 用。
3. 教训: 观察到的 "G2[0] 缺失" 实为两级叠加 (legacy 覆盖 + key 碰撞), 各自
   独立可修 — 归因必须拆开验证 (minimal vs 嵌套对照)。

## 📌 状态

- ✅ 代码 + unit; 全量回归见 commit
