# Iteration 168: Covergroup 混合真实场景对抗 — env 嵌套 + 全栈混合 (2 修)

**Metadata**:
- **Iteration #**: 168
- **Task Tree Level**: L1
- **Parent Task**: L1_covergroup_linkage (tasks/L1_covergroup_linkage.md)
- **Created**: 2026-09-06 GMT+8
- **Author**: AI 助手
- **Outcome**: ✅ 成功 (2 真缺口修 + 10 混合场景测试)

## 🎯 本次目标

方豆 "这次可以混合 class module covergroup 来实际测试，这样更接近真实场景"
— 组合 TB 形态 (env 内包 packet、module 驱动链、submodule + 双域 cg) 全
管线验证, 找跨域盲点。

## 📊 当前状态 / 预期结果

- 对抗轮 iter_167 (单域) ✅。预期: 混合域交叉处找真缺口。

## 🔬 实际结果

**M8 (env{packet p; cg} + drive 链) — 发现真实盲点**:
- class 被实例化为另一 class 成员 (env.p) 时, 图的 IS_INSTANCE_OF 指向
  **类型级成员槽** 'tb_env.p', 不是每个容器的**活对象** 'top.e.p'。
  → packet 的 cg (cg_p) auto 实例解析落到 tb_env.p.addr (非数据节点,
  drivers 空); 而活对象 top.e.p.addr (driven by drive→p.set, 经 cg_env
  路径实测 drivers=[din]) 反而够不到 — 显式 instance='top.e.p' 也被校验
  拒 (不在实例集)。真实 TB (env 内包被测类 + 类内 cg) 的 Q1 断。
- **修 1 (query/covergroup.py)**: `_class_instances` **槽展开** — 实例 id
  首段 = class 名 (编译域 list_classes) → 是成员槽, 展开为 owner 对象 ×
  成员后缀 (递归至模块层对象); 深度守卫防环。Q1/Q2/Q3 auto + 显式校验
  全走展开后对象集 (top.e.p ∈ 集 → 显式通过)。

**M8B (packet 带约束) — 发现 class/constraint 域缺口**:
- ConstraintTracer 实例→类型解析只支持单级 (top.p.addr, rsplit 剥 1 段);
  嵌套 top.e.p.addr → 空 (Q3 静默空答)。
- **修 2 (query/constraint.py)**: 路径 2 泛化 — 逐级实例前缀 (最长优先)
  IS_INSTANCE_OF → 类; 成员链 `_walk_member_type` 沿 class 类型递归
  (tb_env.p 成员槽 IS_INSTANCE_OF packet → 续 addr → packet.addr)。
  单级路径等价保留 (MEMBER_SELECT 路径 1 不动; iter_153 测试 4/4)。

**M3 (全栈混合: assign + submodule 端口 + class 方法 + module/class 双 cg)
— 验证通过**: module cg cp_w {w,din} 驱动 {din,din2}; cp_x → xored 驱动
{u_sub.s}; class cg_acc (accumulate(xored)) 驱动链跨域到 u_sub.s; Q2
语义正确 (无人直接采样 u_sub.s → 空; top.w → cp_w)。

**测试**: test_covergroup_mixed_scenarios.py 10 (env 嵌套 Q1 auto 槽展开 /
env cg / Q2 双 cg 活对象 / 显式嵌套实例 / Q3 嵌套约束 / constraint API
直查嵌套 / 全栈 module+class cg / 跨域驱动链 / Q2 空与命中)。回归待确认。

## 💡 关键发现 / 决策

- **"实例"在 class 域有两种存在**: 类型级成员槽 (tb_env.p, IS_INSTANCE_OF
  指向它) vs 每容器活对象 (top.e.p, 只以数据端点存在)。C2 设计实例节点
  = 声明位置 → 成员槽; 查询层需**展开**才能答数据流问题 — 这是建模层
  (图) 与查询语义 (对象) 的桥, 放 query 域 (图不变, B 同构)。
- **跨域缺口往往在边界文件里被各自测试漏掉**: 单域对抗 (iter_167) 全过,
  混合才暴露槽展开 + 嵌套约束 — 混合语料是 class/covergroup 域的试金石。
- Q3 嵌套约束修复放 ConstraintTracer (class 域文件) 而非 covergroup —
  通用化使 trace_constraints API 本身受益 (非 covergroup 专用补丁)。
