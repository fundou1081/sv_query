# 纪律违反记录

> 审查日期: 2026-05-28
> 最终更新: 2026-05-28 (晚间)

---

## 铁律1: SyntaxTree → Semantic AST 修复状态

| 文件 | 方式 | 原因 |
|------|------|------|
| `covergroup_extractor.py` | ✅ Semantic AST | 不依赖 UVM |
| `call_graph_builder.py` | ✅ Semantic AST | 不依赖 UVM |
| `uvm_testbench_extractor.py` | ⚠️ SyntaxTree | UVM 宏 (type_id::create, uvm_component_utils) 需要 uvm_pkg 宏展开，Semantic AST 无法解析 |
| `constraint_visitor.py:551` | ✅ 合规 | `if __name__ == "__main__"` 示例代码 |
| `pyslang_adapter.py:144,148` | ⚠️ 死代码 | `trace_signal_from_file/code` 未被调用 |

### 技术说明

- pyslang SVCompiler 可以编译 `import uvm_pkg::*` + UVM 宏的代码（需加入 uvm_pkg.sv 源码）
- 但 UVM 测试源码使用 `type_id::create` 等简化写法，未包含完整 UVM 宏定义
- UVM 提取器只需语法结构（类定义、create 调用、connect 调用），不需要语义信息
- 未来如需 UVM 语义分析，可通过 SVCompiler + uvm_pkg.sv 预处理实现

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

## 状态

- [x] P0: covergroup/call_graph SyntaxTree → Semantic AST
- [x] P0: compiler 支持 UVM include 路径
- [ ] P0: 数据模型加 errors (CovergroupInfo, UVMTestbench)
- [ ] P2: except 加注释
- [ ] P2: 清理 pyslang_adapter.py 死代码
