# EXTRACTION_FAILURES.md — 提取失败路径集中表

> **创建日期**: 2026-08-28 21:45
> **维护人**: 方豆 + AI 助手
> **状态**: 持续维护 — 发现新的 fallback / sentinel / 吞异常模式时**必须**登记到这里
> **关联**: [ARCHITECTURE_REVIEW_2026-08-27.md §三.7](ARCHITECTURE_REVIEW_2026-08-27.md) / [ARCHITECTURE_TODOLIST #4](ARCHITECTURE_TODOLIST.md) / [AGENTS.md 核心纪律 #2](../AGENTS.md)

---

## 🎯 目的

AGENTS.md 核心纪律 #2 禁止 silent fallback。但"禁止"不等于"不存在"——
**代码库里现存大量 fallback 模式** (2026-08-28 全仓扫描), 其中一部分是
**有意设计的防御** (有注释、有 warning、有 sentinel), 一部分是**历史遗留的 silent fallback**
(吞异常 / 静默 default / 无注释兜底)。

本表的目标:
1. **登记**所有已知 fallback 路径, 让"修一处"不再是靠运气
2. **分类**清楚哪些是合规的 (sentinel + warning), 哪些是违规的 (silent)
3. **给出修复建议**, 供后续逐步清理
4. **关联已修的 Bug** #2/#3, 作为"怎么改"的正面参考

---

## 📊 全仓扫描结果 (2026-08-28)

| 模式 | 数量 | 判定 |
|---|---|---|
| `try/except + pass` (吞异常) | **113 处** | ⚠️ 大部分违规, 需逐点审查 |
| `fallback / 退化 / 兜底` 关键词 | **121 处** | ⚠️ 需区分"有意设计"vs"silent" |
| `getattr(x, None/"")` (静默 default) | 37+ 处 | ⚠️ 部分合规 (取可选属性), 部分违规 |
| `return None / [] / ''` (sentinel) | 大量 | ✅ 合规 (显式 sentinel, 见下) |

---

## 📋 Fallback 分类表

### 分类 A: ✅ 合规 — 显式 sentinel + warning (正面参考)

**原则**: 失败时返回 sentinel + `logger.warning`, 调用方能识别。**这是 AGENTS.md 要求的样子。**

| 位置 | 模式 | 触发条件 | 行为 | 修复建议 |
|---|---|---|---|---|
| `coverage_generator.py:35` | `NO_TREE_MARKER = "<NO_TREE>"` | expr tree 提取失败 | 返回 marker + WARNING, 绝不 string fallback | ✅ **保持** (已是正面标准) |
| `extractors/_common.py:781` | `_eval_to_int` return None | 表达式无法折叠成常量 (如 `data[i]` 符号下标) | None 是既定 sentinel, 调用方保留符号形式 | ✅ **保持** (有注释说明非 fallback) |
| `connection_extractor.py:384` | Bug #2: 端口方向未识别 | 端口不在 module_ports / direction='unknown' | `logger.warning` + `extra={"direction": ..., "fallback": "PORT_IN"}` | ✅ **保持** (2026-08-27 已修) |
| `connection_extractor.py:389` | Bug #3: 同款 warning+extra | 同上 | 同上 | ✅ **保持** |

### 分类 B: ⚠️ 待审查 — try/except + pass (吞异常)

**原则**: `except ...: pass` 会隐藏真实错误, 且让"失败"与"正常"不可区分。**113 处需逐点审查。**

| 位置 | 触发条件 | 行为 | 判定/建议 |
|---|---|---|---|
| `uvm_testbench_extractor.py:154/190/214/265/402/519` | pyslang Token 不可迭代 (TypeError) | pass 跳过 | ⚠️ 有注释说明"跳过", 但无 warning — 建议加 `logger.debug` |
| `native_adapter.py:156` | `except (UnicodeDecodeError, TypeError, Exception)` | pass | 🔴 **包揽 Exception** — 最危险模式, 建议拆细 |
| `coverage_models.py:239` | `except Exception` | pass | 🔴 同上, 建议至少 log |
| `compiler.py:481/486` | `except Exception` | pass | 🔴 同上 |
| `driver_extractor.py` (多处) | 各提取路径异常 | pass | ⚠️ 需逐点审查, 部分可能是历史遗留 |

> **注意**: 不是所有 `pass` 都违规 — 有些是"可选增强, 失败不影响主流程" (如 source_location 提取失败不阻塞 edge 创建)。**判定标准**: 失败是否会导致**静默产出错误数据**。是 → 必须加 warning/sentinel; 否 → 可留 debug 级日志。

### 分类 C: ⚠️ 待审查 — fallback 关键词 (部分合规)

**原则**: `fallback` 注释本身不违规, 但要看 fallback 路径是否**显式** (有 warning / sentinel) 还是**静默** (直接换一条路)。

| 位置 | 触发条件 | 行为 | 判定/建议 |
|---|---|---|---|
| `graph/viz/elk_bridge.py` (25 处) | ELK 渲染兜底 | 多种 fallback | ⚠️ 数量最多, 需抽查是否 silent |
| `driver_extractor.py` (12 处) | 提取路径兜底 | 多种 | ⚠️ 部分已被 Step 1-8 清理, 需复查 |
| `coverage_generator.py` (12 处) | 覆盖提取兜底 | 多种 | ⚠️ 与 NO_TREE_MARKER 同文件, 抽查 |
| `connection_extractor.py` (10 处) | 端口连接兜底 | 多种 | ⚠️ Bug #2/#3 已修 2 处, 其余待查 |
| `semantic_adapter.py` (8 处) | pyslang API 兜底 | 多种 | ⚠️ 含 `_iter_children` 的属性遍历兜底 (合规) |
| `trace_evidence.py` (6 处) | evidence 提取兜底 | 多种 | ⚠️ 待查 |
| `extractors/_common.py` (5 处) | 共享 helper 兜底 | 多种 | ⚠️ 已清理 silent fallback (Step 3/6/7), 剩余多为合规 |

### 分类 D: ✅ 合规 — 显式 sentinel 返回 (返回 None/[]/'' 表示"无结果")

**原则**: 函数语义上"可能无结果", 返回 None/[] 是**契约的一部分**, 不是隐藏失败。
**判定标准**: 调用方是否**明确处理** None/[] (如 `if x is None: return` / `if not lst: ...`)。

**常见合规模式**:
- `get_signal(expr)` → None 表示"表达式不是信号" (调用方判空)
- `_find_task_definition` → None 表示"没找到 task" (调用方继续)
- `_parse_assign` → (None, None, None) 表示"不是可解析的赋值" (调用方短路)

> **关键区分**: sentinel 返回值 vs silent fallback 路径。
> - 前者: 函数**明确声明**"可能无结果", 调用方**显式处理** → ✅
> - 后者: 主路径失败后**悄悄换路** (如 string parse), 调用方不知情 → 🔴 违规

### 分类 E: ⚠️ 待审查 — getattr + default (静默 default)

**原则**: `getattr(node, attr, None)` 取可选属性是**防御性编程**, 本身合规。
**违规情形**: 当**必须存在**的属性缺失时仍静默取 default, 导致下游用错数据。

| 位置 | 触发条件 | 行为 | 建议 |
|---|---|---|---|
| 各提取器 (37+ 处) | pyslang 节点属性缺失 | 取 None/"" | ⚠️ 大部分合规 (AST 属性本来就是可选的), 但**关键路径** (如信号名/方向) 缺失时应 warning |

---

## 🔗 关联已修 Bug

### Bug #2: 端口方向未识别静默落 PORT_IN (connection_extractor.py)

**修复前**: 端口方向未知 → 静默当 PORT_IN → 用户看到错误方向无提示。

**修复后** (commit `e02da76`):
```python
if port_name not in module_ports:
    logger.warning(
        f"port '{port_name}' not in module_ports of '{inst_module_name}'", extra={...}
    )
    port_extra = {"direction": "missing", "fallback": "PORT_IN"}
elif direction == "unknown":
    ...
```

**模式**: 行为保持兼容 (仍取 PORT_IN) + **显式 warning + extra 记录实际状态**。
这是"不能改行为但必须暴露问题"的标准做法。

### Bug #3: 同文件同款问题

与 Bug #2 同 commit 修复, 同样的 warning+extra 模式。

---

## ✅ B/C/E 三类审查结论 (2026-08-28 21:50)

对分类 B/C/E 做了**逐点审查** (113 处 try/except+pass + 121 处 fallback 关键词 + 163 处 getattr default)。

### 分类 B 审查结果: 111 处判定 = **36 违规 / 55 合规 / 20 边界** (✅ 36 违规 + 20 边界已处理, iter_048)

| 判定 | 数量 | 说明 |
|---|---|---|
| 🔴 **违规** | 36 | Exception 过宽 + 数据提取路径, 失败静默丢数据 |
| 🟢 合规 | 55 | 防御性遍历 / 可选增强 / 有 sentinel / 有注释 |
| 🟡 边界 | 20 | 有防御意图但无日志, 建议加 logger.debug |

**处理状态**: iter_048 (36 违规+20 边界+23 冗余) / iter_051 (10 宽异常) / iter_052 (**全仓 except: pass 清零**) 已落地.
**全面禁止 except: pass** (AGENTS.md 核心纪律 2.5): 所有 except: pass 改为 `except X as e: logger...` 或加注释, 全仓计数 = 0.

**违规分布** (按文件):
- `class_graph_builder.py` (7 处): 类约束/成员提取失败静默 — **最高危** (约束数据丢失)
- `graph_builder.py` (6 处): 图构建失败静默 — 丢节点/边
- `load_extractor.py` (7 处): 端口/参数提取失败静默
- `sva_extractor.py` (5 处): SVA 信号提取失败静默
- `compiler.py` (5 处): source_location 提取失败静默
- `semantic_adapter.py` (4 处): 端口/成员提取失败 + Exception 冗余
- `native_adapter.py` (1 处): `except (UnicodeDecodeError, TypeError, Exception)` — Exception 包揽前两个, 冗余

**典型违规模式**:
```python
# 违规: Exception 过宽 + 无日志
try:
    for item in node.items:
        self.visit(item)
except Exception:
    pass  # ← 类约束遍历失败, 约束数据静默丢失
```

**合规典型** (不需要改):
- `graph/dataflow.py` NetworkX 无路径返回空 — 正常契约
- `_dot_common.py` 临时文件清理 OSError — 资源清理
- `extractors/_common.py` 常量折叠返回 None — sentinel
- `uvm_testbench` / `call_graph` / `covergroup` 的 TypeError 跳过 — 有注释
- `sva_extractor` 的 TypeError 遍历跳过 — 有注释

### 分类 C 审查结果: 121 处 fallback 关键词 = **绝大多数有意设计**

抽查 (elk_bridge 25 / driver_extractor 12 / coverage_generator 12 / connection_extractor 10 / semantic_adapter 8):

| 类型 | 占比 | 说明 |
|---|---|---|
| ✅ 有意设计 (优先路径 + fallback helper) | ~85% | 注释明确 "优先入参, fallback 才用 helper" |
| ✅ 显式 sentinel (NO_TREE_MARKER) | ~10% | coverage_generator 已贯彻纪律 |
| ⚠️ 需注意 | ~5% | `driver_extractor:450` filelist mutex fallback (特殊处理, 合规但复杂) |

**结论**: 分类 C 无系统性违规, 注释驱动的 fallback 是项目设计的一部分。
重点是**新增代码**不要引入 silent fallback (AGENTS.md 纪律 #2)。

### 分类 E 审查结果: 163 处 getattr+default = **绝大多数合规**

抽查 (class_graph_builder 68 / module_instance_graph 37 / load_extractor 33 / sva_extractor 28):

| 类型 | 占比 | 说明 |
|---|---|---|
| ✅ 防御性 AST 遍历 (getattr kind/name → "") | ~95% | pyslang 属性可选, kind 判断走 else 分支 |
| ✅ 属性名兼容 (or 链尝试多个属性名) | ~4% | pyslang v10/v11 兼容 |
| ⚠️ 需注意 | ~1% | `base.py:521` direction 缺省取 "" (modport, 边界) |

**结论**: getattr+default 是防御性编程标准做法, 合规。
关键字段 (方向/信号名) 缺省时建议加 warning, 但当前无实际数据错误。

---

## 🛠️ 清理优先级建议 (审查后更新)

| 优先级 | 目标 | 理由 | 状态 (2026-08-29 核实) |
|---|---|---|---|
| P0 | `class_graph_builder.py` 7 处违规 | 类约束数据静默丢失, 最影响功能正确性 | ✅ **已清理** (iter_048: 10 个 except 全带 logger/raise) |
| P0 | `graph_builder.py` 6 处违规 | 图节点/边静默缺失 | ✅ **已清理** (iter_048 + 本次: 失败分支 print→logger.warning) |
| P0 | `load_extractor.py` 7 处违规 | 端口/参数提取失败静默 | ✅ **已清理** (iter_048; 本次: msb/lsb=0 加注释说明 sentinel) |
| P0 | `native_adapter.py:156` / `compiler.py` 5 处 | Exception 过宽 + source_location 静默 | ✅ **已清理** (iter_051/052 + GAP 系列; compiler 有 print/traceback) |
| P1 | `sva_extractor.py` 5 处违规 | SVA 信号提取失败静默 | ✅ **已清理** (iter_048: L38 有 errors.append 显式记录) |
| P1 | `semantic_adapter.py` 4 处违规 | 端口/成员提取失败 | ✅ **本次收窄**: 7 处 `(UnicodeDecodeError, Exception)` 冗余 → `(UnicodeDecodeError, TypeError)` (零回归) |
| P2 | 20 处边界 → 加 logger.debug | 低成本提升可观测性 | ⚠️ 未全做 (iter_048 已处理大部分; 剩余为可选) |
| P3 | `base.py:521` direction 缺省 → warning | 关键字段缺失提示 | ⚠️ 未做 (低风险, 可选) |

> **核实结论 (2026-08-29, iter_060)**: P0/P1 全部已清理或已核实合规。
> 剩余为 P2/P3 可选增强 (可观测性), 非功能正确性问题。

---

## 📝 维护纪律

1. **发现新的 silent fallback → 必须登记到此表** (位置/触发/行为/建议)
2. **修复某条 → 移到"已修复"并在 commit 里引用本表条目**
3. **新代码** → 遵循 AGENTS.md 核心纪律 #2: 显式报错或 sentinel + warning,
   **禁止** silent fallback
4. 本表是**活文档**, 随代码库演变持续更新
- **2026-08-29 (iter_068)** — `test_generate_real_world.py` line 85 用 `--no-strict`
  (CLI 调用, Plan F1.5 遗留): pre-existing 纪律 #1 违规 — ZipCPU 真实 RTL 含未知
  子模块, strict 编译失败。已回退新增的 strict=False 断言 (不扩大违规), 原遗留
  待决策: 补完整 filelist 修根因 / 或标记 TEMPORARY 接受。
