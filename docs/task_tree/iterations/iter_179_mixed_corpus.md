# Iteration 179: C 路线第一项 — 混合真实场景语料库

**Metadata**:
- **Iteration #**: 179
- **Task Tree Level**: L1
- **Parent Task**: (C 路线: 质量纵深)
- **Created**: 2026-09-08 GMT+8
- **Author**: AI 助手
- **Outcome**: ✅ 成功 (7 语料 + 表驱动不变量测试 6 tests / 35 subtests)

## 🎯 本次目标

方豆 "走C路线" — 把 iter_164~178 对抗轮发现的混合场景**沉淀为常驻语料**,
让后续任何改动都要过"真实混合形态"这一关。

## 🔬 实际结果

- 语料: `sim/tests/fixtures/mixed_corpus/*.sv` **7 个** — env 内包 packet
  (类中类 + 方法链) / env 内包 + 约束 (Q3 嵌套) / 全栈混合 (assign + submodule
  + class 方法 + 双域 cg) / generate-for 实例链 + 类实例 + cg / 子模块层次 +
  module cg / logic 4 态实参 (Conversion 壳) / 参数化 class 内嵌参数化 class。
- 测试: `sim/tests/regression/test_mixed_corpus_truth.py` — 表驱动 CASES,
  每个语料断言 5 个维度: **提取** (cg 名/归属/实例规则) → **Q1 采样链**
  (信号 id + 驱动集**精确集合**) → **Q2 反向** (cg/cp/实例三元组) →
  **Q3 约束** (约束块 id) → **数据端点 fanin**。
- 断言值全部**实测得出**(先跑 probe 打印真实不变量再写断言); 两处首次期望写错
  (module cg 的 Q2 命中的 instance 为空串; full_stack 输出端口 fanin 含内部
  操作数+上游穿透) → 按实测修正, 并在测试注释说明语义。
- 结果: 6 tests / **35 subtests 全绿**。

## 💡 关键发现 / 决策

- **语料库的断言要"表驱动 + 精确集合"**: 松散断言 (≥N) 抓不到语义漂移;
  精确集合能同时锁住"多了/少了/错位"三类变化。
- **语料本身要贴真实形态**: 7 个语料全部来自真实 TB/混合设计模式 (env 包被测类、
  子模块 + monitor、generate + 类), 而不是人为堆语法 — 这是前几轮"单域对抗全绿
  但混合才炸"的直接结论。
- **维护约定写进文件头**: 新增语料 = 加 .sv + CASES 加一条; 实测与预期不符时
  **先判断是缺陷还是预期需修正** (禁止改断言让它过)。
