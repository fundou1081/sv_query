# Iteration 135: Signal Graph 准确性声明 (Accuracy Claim) 落档

**Metadata**:
- **Iteration #**: 135
- **Task Tree Level**: L2 (准确性审计 → 声明框架)
- **Parent Task**: [signal_graph_accuracy_audit.md](../../architecture/signal_graph_accuracy_audit.md)
- **Created**: 2026-09-05 GMT+8
- **Author**: AI 助手
- **Outcome**: ✅ 成功

## 🎯 本次目标

方豆问询: "现在我能说 signal graph 产生的图一定是代码的准确映射吗?"
结论落档为**可核查的分层声明**, 写入审计文档, 替代一句式拍板。

## 📊 当前状态 / 预期结果

审计文档只有"已修复/未修复/候选"的逐条证据, 没有对外的一页式
**答案**。预期: 文档头部新增 Accuracy Claim 章节 — 任何人对
"图准不准"可直接对照三层声明核查。

## 🔬 实际结果

### 核心判断 (不美化)

**不能无限制地说"一定是准确映射"**。理由三点:

1. **图 = 建模决策产物, 非字面镜像**: 大量刻意抽象 (总线粒度 /
   端口边界停靠 / 自环排除 / CLOCK 非数据源 / wrapper 穿透 /
   inout-interface 单向建模) — "准确"必须按"查询语义 + 建模决策"
   理解, 否则任何抽象点都是"不准"。
2. **已知反例清单非空** (L3): inout 双向多驱动、interface 多写共享、
   A2 位对位、gate G-2/G-3、slang entry 合并、CVA6 等 strict 编译
   受阻、#7 inline/SVA procedural 域 — 命中任一项 = 图不准。
3. **验证语料非穷举**: 3048 tests (fixture 抽取) + 真实设计抽查
   (aes/cordic/serv/verilog-axi); "一定"需要穷举或等价验证, 语义域外
   本就不承诺。

### 分层声明 (写入文档的形态)

| 层 | 承诺 | 状态 |
|---|---|---|
| L1 结构层 (节点/边存在性) | 实例路径/连接/驱动存在性正确 | ✅ 已验证设计域内可宣称 (iter_117~134 修复后) |
| L2 查询层 (fanin/驱动答案) | 查询结果正确 | ✅ 限"建模粒度语义"内 (总线/端口粒度 + wrapper 穿透规则) |
| L3 深层语义层 (多驱动/双向/共享归属) | 归属/合并语义 | ❌ 不承诺 — 已知反例 = backlog |

### 落档位置

- `docs/architecture/signal_graph_accuracy_audit.md` 头部新增
  `📜 Accuracy Claim` 章节 (对外答案在前, 逐条证据在后)

## 💡 关键发现 / 决策

1. "准确性"是**分层属性**不是单一布尔: 结构正确 ≠ 查询语义正确 ≠
   多驱动归属正确。单层断言 (如 "fanin 全对") 与全称断言
   ("图 = 准确映射") 是不同强度的声明, 必须分开说。
2. 图工具的诚实声明模板 = 承诺层 + 范围限定 + 反例清单, 三者缺一
   不可; 只列反例显得全不准, 只列承诺变成吹嘘。
3. 后续清 backlog (位对位折算 / inout 多驱动 / interface 多写) 时,
   每修一项 = L3 反例移出, 声明自动增强 — 声明文档是 backlog 的
   "消费端"。

## 📌 状态

- ✅ Accuracy Claim 章节写入 audit 文档 (L1/L2/L3 + 抽象表 + 范围限定)
- ✅ CURRENT_TODO / overview 同步 (iter_135)
