# Iteration 167: Covergroup 对抗轮 — 找盲点 (A2 cast 类型 / C4 错实例 2 真 bug)

**Metadata**:
- **Iteration #**: 167
- **Task Tree Level**: L1
- **Parent Task**: L1_covergroup_linkage (tasks/L1_covergroup_linkage.md)
- **Created**: 2026-09-06 GMT+8
- **Author**: AI 助手
- **Outcome**: ✅ 成功 (2 真 bug 修复 + 边界登记; iter_156 class 同款方法)

## 🎯 本次目标

方豆 "先来再做一些对抗性测试。试着找出盲点。" — G1-G4 闭环后构造极端用例,
找提取/绑定/查询的盲点 (通过 / 真 bug 修 / 缺口登记文档标记)。

## 📊 当前状态 / 预期结果

- covergroup 观察域 47 测试已绿。预期: 盲点 → 分类处理。

## 🔬 实际结果

**探针 A (提取/引用收集)** 9 场景:
- **A2 真 bug**: 自定义类型 cast `my_t'(w)` — cast 类型子节点是
  IdentifierNameSyntax (my_t) → 被当信号收集 (关键字 cast unsigned 是 Token
  本来跳过)。修: _expr_walk 对 class 名含 'Cast' 的节点跳过首个子节点
  (类型), 操作数保留。
- A3 匿名 cp (无标号) — 语义名 = expr 文本 ('din'), 不丢不崩 ✅
- A4 嵌套函数 f2(din) + $countones(q) — callee 全不泄漏 ✅
- A5 变量索引 arr[idx] — idx 不收集 (寻址非采样数据) — 📌 登记边界
- A6 iff 使能不进采样 ✅; A7 interface 内 cg — 提取也通 (host=top.u_if) ✅
- A8 $root.top.sig → ref 'top.sig' ($root 剥掉) — 层次引用桥 = 📌 登记
- A1 assignment pattern 无类型 → slang 拒 (0 cg) — 合法代码错误

**探针 B (实例/绑定)** 7 场景:
- B1 extends: 父类 cg + 子类实例 — 显式绑定 ✅; **auto 实例查找不含子类
  实例** (trace_class_instances('base') 空) → 📌 登记 (显式可查)
- B2 双 cg 继承 (base+sub 各 cg) — 规则/绑定各自正确 ✅
- B3 ctor 部分 new — cg_a ctor_new / cg_b uninstantiated ✅
- B4 if-else 双侧 new → ctor_new ✅; B7 无实例 class → 规则对, 无绑定 ✅
- B5 module 多实例变量 (c1/c2) — 单定义记录 (实例粒度 G2 设计) ✅
- **B6 同名 class 跨 package**: 两 cg 记录无法区分 (无 package 限定),
  绑定交叉污染 (p1 绑到两 cg) — **继承 class 域 D5 边界** (graph 侧
  iter_154 同名冲突告警同源; 静态歧义) — 📌 登记不修 (与图一致)

**探针 C (查询)** 5 场景:
- C1 子模块 cg (host=top.u_sub) — Q1 采样 id top.u_sub.mid + Q2 反向 ✅
- C2 select 位级 id (top.din[3]) 查询空答优雅; base id 命中 (select 附注) ✅
- C3 extends 属性约束 — 图内继承展平, Q3 返回 packet.c_len ✅ (无 bug)
- **C4 真 bug**: 传非该类实例 instance='top.nope' → 静默造 bogus id
  'top.nope.addr'。修: _resolve_instance 显式校验实例集 (集非空且不符 →
  missing; 集空 = 图未枚举 (extends 直查) 放行 — B1 边界保留)
- C5 module+class 同名 cg — 按名查询返回全部 (消歧 = 未来) — 📌 登记

**测试**: test_covergroup_adversarial.py 12 (A2/A3/A4/A6 cast+匿名+嵌套+
iff / B3 部分 new / C1 子模块 Q1+Q2 / C2 select 优雅 / C4 错实例→missing /
C5 同名返回全部 / B1 extends 显式放行+auto missing)。回归待跑。

## 💡 关键发现 / 决策

- **Cast/调用型语法节点首子节点 = 非信号** (callee/类型) — 与 class 域
  方法 receiver 同构的"先跳首子"模式; 关键字类 (unsigned/$) 是 Token 天然
  安全, 用户类型 (IdentifierName) 才是盲点 — 语义/语法边界交叉处。
- **静默 bogus 比显式 missing 更伤诚实性** (Claim): 查询方传错实例 → 校验
  实例集 → missing (与"未用实例成员不臆造" C2 同原则)。
- **extends 子类实例枚举** = 查询层真实缺口 (base cg auto 查不到子类实例)
  — 需 class 域 extends 层级信息 (graph 无 EXTENDS 边?) — 登记未来项。
- 同名 class/cg = 静态歧义 (package 限定缺失) — 与 D5 冲突告警同源,
  covergroup 域不单独造机制, 保持一致。
