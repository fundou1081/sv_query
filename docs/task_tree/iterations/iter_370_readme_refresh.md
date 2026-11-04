# Iteration 370: README 项目描述校准（PLAN P68）

**Metadata**:
- **Iteration #**: 370
- **Task Tree Level**: L2（PLAN `P68`）
- **Created**: 2026-11-04 GMT+8
- **Author**: 方豆 / AI 助手
- **Outcome**: ✅ 完成；2529 passed

## 🎯 动机

方豆问："需要更新 readme 中的内容吗，关于项目本身的描述。"

旧 README 的偏差：

- 标题仍是"信号追踪查询引擎"，低估了"查询 + 客观校验层"的产品定位；
- "pyslang 语义 AST，不是正则匹配"没有说明 UVM 宏是唯一 syntactic regex 例外；
- 能力列表没有 covergroup / UVM / `graph subgraph` / `verify structural`；
- 验证只写旧 smoke，没有性能基准和反幻觉 walkthrough；
- 日期/基线/文档链接滞后。

## 🔧 更新

- 标题改为"面向 agent 的 SystemVerilog 语义查询 + 客观校验引擎"；
- 语义优先 + UVM `syntactic` 例外显式化；
- 补 class/constraint/covergroup/UVM、`graph subgraph`；
- 新增"验证状态"表：
  - 2529 passed；
  - smoke + 3 设计性能 + CDC walkthrough；
  - 明确未做 HWE/VeriBug 对照、agent 命中率、多线程/门级；
- 日期/基线/相关文档同步。

## 🧪 验证

- `check_docs` / `check_plan` 通过；
- README 命令抽查（drivers/loads/paths/trace profile/fanin）；
- 全量回归保持 **2529 passed / 0 failed**。

## ⚠️ 边界

README 只描述已有能力；没有新增功能，没有性能/agent 结论变化。
