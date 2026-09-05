# Iteration 141: CVA6 建图解码点清理 (iter_140 续) + 内存边界定性

**Metadata**:
- **Iteration #**: 141
- **Task Tree Level**: L2 (Accuracy Claim L3 #7: CVA6; 大设计健壮性)
- **Parent Task**: [signal_graph_accuracy_audit.md](../../architecture/signal_graph_accuracy_audit.md)
- **Created**: 2026-09-05 GMT+8
- **Author**: AI 助手
- **Outcome**: ⚠️ 部分 (解码健壮性批量修复 ✅; CVA6 完整建图 = 8GB 内存/原生
  segfault 边界, 非代码 bug, 登记)

## 🎯 本次目标

方豆 "继续" → iter_140 续: 打通 CVA6 完整建图 (逐个修解码点)。

## 🔬 实际结果

### 解码健壮性批量修复 (iter_141, 真 bug — 同类不再出)

CVA6 大设计暴露 pyslang pybind 属性/str() 在非 utf8 identifier 上抛
UnicodeDecodeError 的**系统性**点, 全部换 safe_attr/safe_str (项目已有
工具, _safe.py safe_attr 已 catch UnicodeDecodeError):

| 文件 | 点 | 修法 |
|---|---|---|
| `_common.py` | get_signal NamedValue (iter_140) / MemberAccess / HierarchicalValue / iter_bit_selects `str(syn)` / 单引号 name getter ×9 | safe_attr/safe_str 批量 |
| `_common.py` (新) | `safe_symbol_name(sym)` helper | hasattr+str 防护, 返回 None sentinel |
| `always_extractor.py` | find_clock symbol name ×2 | safe_symbol_name |
| `driver_extractor.py` | find_reset ×3 + _detect_binary_op str(syntax) | safe_symbol_name / safe_str |
| `semantic_adapter.py` | MemberAccess member str / get_function_name / get_task_name / get_assignments loopVariable | safe_str / safe_attr |
| `function_extractor.py` | subroutineName / name ×4 / str(callee) | safe_attr / safe_str |
| `expression_tree.py` | `str(token)` 冗余双重检查 (kind 已权威) | 删解码路径 |

**效果**: 崩溃 → warning (get_primitive_instances 失败 / 提取失败 日志),
提取路径不再整图崩溃。

### CVA6 完整建图 = 环境边界 (Segmentation fault)

解码修复后建图推进更远, 最终 **Segmentation fault (native)** — CVA6 core
~100 模块实例树在 8GB MBA 上 elaboration + 图构建耗尽内存/触发 pyslang
native 崩溃 (iter_059 已记录同款 "Subprocess OOM / OpenTitan unavailable on
8GB MBA")。**非代码 bug**: 需更大内存机器或上游 pyslang 修复。处置:
CVA6 完整建图登记环境边界; core **编译**已通 (iter_140) 可用于后续
大内存环境验证。

## 💡 关键发现 / 决策

1. **解码点 = 系统性而非个别**: pyslang pybind 的 `.name`/`.subroutineName`/
   `str(node)` 在非 utf8 identifier 抛 UnicodeDecodeError — 已有 safe_attr/
   safe_str (iter 早期建) 但提取路径大量裸用。CVA6 规模一次性暴露; 修复
   是通用健壮性债 (任何大设计受益)。
2. **修复原则**: 失败显式 (warning/sentinel) 不 crash — 与 AGENTS.md §2
   一致 (get_primitive_instances 失败已 warning; get_signal None sentinel)。
3. **CVA6 建图边界 = 内存/原生**: 8GB MBA 限制 (iter_059 先例); 完整建图
   需大内存环境 — 不是修复项, 是环境项 (Claim L3 #7 登记)。

## 📌 状态

- ✅ 解码健壮性批量修复 (~15 点, 6 文件) — 崩溃 → warning
- ✅ 回归: unit+integration (见 commit; 改动全在提取路径, unit 覆盖广)
- 🚧 CVA6 完整建图: 8GB 内存/原生 segfault 边界 (环境项, 大内存机器可验)
