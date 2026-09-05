# Iteration 147: README 更新 — 准确性声明 + 数字同步 (2026-09-05)

**Metadata**:
- **Iteration #**: 147
- **Task Tree Level**: L3 (文档维护)
- **Parent Task**: 项目 README 同步
- **Created**: 2026-09-05 GMT+8
- **Author**: AI 助手
- **Outcome**: ✅ 成功 (无代码改动)

## 🎯 本次目标

方豆 "项目 readme 是不是可以更新?" — README 更新日期停在 2026-08-26,
测试数 3131 过时, 缺本轮核心成果 (准确性声明 / 位对位 / CVA6 编译)。

## 🔬 实际结果

README.md 更新 (docs/README.md 是验证问题库, 不同用途, 不动):
- 头部: 更新日期 2026-09-05 + 测试数 3071 (非 opensource 主回归)
- "为什么用 sv_query": 位对位贯通 (顶层位 == 模块内位)、bus 位桥
  (同构/切片偏移)、无 string fallback 纪律、真实项目验证
  (aes/cordic/serv/verilog-axi + CVA6 core 编译)
- **新增 📜 Accuracy Claim 节**: 三层声明表 (L1 ✅ / L2 ✅ 限粒度 /
  L3 🕐 澄清+暂缓) + 反例表 7→全闭环/暂缓 + "不能无限制说一定准确"
  的诚实边界 — 链接审计文档
- 项目结构/测试段: 3131 → 3071
- 相关文档: 加准确性审计 + AGENTS.md + CURRENT_TODO 链接

## 📌 状态

- ✅ README 头部/数字/验证描述/准确性声明节全部同步
- 无代码改动
