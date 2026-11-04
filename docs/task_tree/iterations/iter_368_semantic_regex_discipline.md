# Iteration 368: 语义提取 regex 纪律（PLAN P66）

**Metadata**:
- **Iteration #**: 368
- **Task Tree Level**: L2（PLAN `P66`）
- **Created**: 2026-11-04 GMT+8
- **Author**: 方豆 / AI 助手（方豆: "加一条纪律，仅 uvm 宏相关的部分，允许用regex"）
- **Outcome**: ✅ 完成；2527 passed

## 🎯 规则

class / constraint / covergroup / UVM 语义必须走 pyslang semantic AST；
源码 regex 仅允许 UVM 宏相关部分：

- `uvm_*_utils`
- `uvm_do*`
- `uvm_declare_p_sequencer`
- `type_id::create` / factory create

原因：pyslang 预处理后宏调用不在 semantic syntax；当前版本没有 MacroUsage 节点。

## 🔧 落地

1. `DISCIPLINE §3.5` + `CODING_STYLE §13` + `AGENTS` 铁律 11；
2. `tools/check_semantic_regex.py` 扫描 9 个语义模块；
   `query/uvm.py` 是唯一允许文件；
3. 新增自检测试（能检出违规 / 不误报 UVM）；
4. **顺带消除现有非 UVM regex**：
   - class 方法调用提取从文本 regex 改为 semantic `SubroutineSymbol.body` 遍历；
   - Unicode class name 修复从 regex 改为字符串切分。
5. AGENTS/REVIEW_CHECKLIST/WORKFLOW 加入检查器。

## 🧪 测试

- 检查器仓库 0 违规；
- 检查器能检出 `import re` / `re.search`；
- UVM 例外不误报；
- class relations 现有调用断言保持通过；
- 全量 **2527 passed / 0 failed**。

## ⚠️ 边界

- 规则只覆盖语义提取模块，不禁止 ID/literal/search 的字符串解析；
- UVM regex 结果仍标 `confidence=syntactic`，不能作为 verify 证明；
- 不改变 UVM 运行时语义（factory override / phase 仍不做）。

## 🔗 相关

- 规则: [DISCIPLINE §3.5](../../dev/DISCIPLINE.md)
- 计划: [PLAN.md P66](../../../PLAN.md)
