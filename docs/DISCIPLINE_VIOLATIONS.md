# 纪律违反记录

> 审查日期: 2026-05-28
> 更新日期: 2026-05-28 (下午)

---

## 铁律1: SyntaxTree → Semantic AST 修复状态

| 文件 | 状态 | 说明 |
|------|------|------|
| `covergroup_extractor.py` | ✅ 已修复 | 使用 SVCompiler Semantic AST |
| `call_graph_builder.py` | ✅ 已修复 | 优先 Semantic AST，无 fallback |
| `uvm_testbench_extractor.py` | ✅ 已修复 | 优先 Semantic AST，UVM 源码 fallback 到 SyntaxTree (pyslang 无法编译 uvm_pkg) |
| `constraint_visitor.py:551` | ✅ 合规 | `if __name__ == "__main__"` 示例代码，非运行时 |
| `pyslang_adapter.py:144,148` | ⚠️ 死代码 | `trace_signal_from_file/code` 未被调用，待清理 |

---

## 铁律10: 数据模型 confidence/errors

| 模型 | 状态 | 说明 |
|------|------|------|
| `CovergroupInfo` | ⚠️ 待补充 | 无 errors 字段 |
| `CallGraph` | ✅ 已有 | 有 errors 字段 |
| `UVMTestbench` | ⚠️ 待补充 | 无 errors 字段 |

---

## 铁律3.1: except 注释

| 文件 | 状态 | 说明 |
|------|------|------|
| 各提取器 `except TypeError` | ⚠️ 待补充注释 | pyslang Token 不可迭代 |

---

## 已知技术限制

| 限制 | 说明 |
|------|------|
| pyslang 无法编译 UVM 源码 | UVM 1.2 使用 pyslang 不支持的语法，SVCompiler 编译失败 |
| 测试源码不依赖 UVM | 测试用自定义 create/start_item/finish_item 替代 UVM 函数 |

---

## 状态

- [x] P0: covergroup/call_graph/uvm_tb SyntaxTree → Semantic AST
- [ ] P0: 数据模型加 errors (CovergroupInfo, UVMTestbench)
- [ ] P2: except 加注释
- [ ] P2: 清理 pyslang_adapter.py 死代码
