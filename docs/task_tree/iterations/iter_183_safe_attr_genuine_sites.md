# Iteration 183: 剩余属性读取定性 + 真实点收尾 (iter_182 续)

> ⚠️ **iter_185 更正 (2026-09-08)**: 本记录里 "语料含非 UTF-8
> identifier / 内存压力导致部分 elaboration" 的归因 **已被证伪**。
> 真因 = `SVCompiler` 的 `SourceManager` 生命周期 (局部变量被 GC →
> 源文件 buffer 释放 → 符号名是指向释放内存的 `string_view`)。
> 见 `iter_185_slang_sourcemanager_lifetime.md`。本记录作为时间点
> 快照保留, 不修改当时观测数据。

**Metadata**:
- **Iteration #**: 183
- **Task Tree Level**: L1
- **Parent Task**: (iter_182 收敛续)
- **Created**: 2026-09-08 GMT+8
- **Author**: AI 助手
- **Outcome**: ✅ 真实点收尾; 剩余全部定性为误报

## 🎯 本次目标

方豆 "继续" — 继续收敛 scanner 报出的剩余属性读取点。

## 🔬 实际结果

**扫描器修正**: 跳过 **Store 上下文** (`self.name = ...` 不是读取, 不会触发
getter) → 74 → 70;并逐点定性剩余 70 处:

| 类别 | 数量 | 判定 |
|---|---|---|
| `node.name` 等 — 接收者是**我们自己的 dataclass** (TraceNode / viz 模型 / `result.instances` 项) | ~60 | **误报** (Python 属性, 无 getter 崩溃风险) |
| `self.name` / `self.type` — wrapper 自身属性读写 | 6 | 误报 (Store/自身属性) |
| `port_sym.type` (module_instance_graph) | 2 | **真实** → 修复 |
| `self._symbol.name` (_wrappers) | 1 | **真实** → 修复 |
| `member_val.name` (graph_builder / load_extractor, modport 成员) | 2 | **真实** → 修复 |
| `node.body` (sva_extractor) | 1 | **真实** → 修复 |

**修复方式 (真实点 5 处 / 5 文件)**:
- `.type` / `.name` / `.body` 全改 `safe_attr(...)` + 语义安全默认值
- 关键发现: **`hasattr(x, "name")` 并不安全** — 它只吞 `AttributeError`,
  pyslang 的 `UnicodeDecodeError` 会**穿透** (`hasattr` 判定 → 属性读取 → 抛)。
  两处 `x.name if hasattr(x, "name") else ...` 模式因此都属于真实风险点。

**验证**: class truth + 混合语料 + interface 测试 39 passed / 35 subtests;
全量 gate 见 commit。

## 💡 关键发现 / 决策

- **误报治理与真实点修复同等重要**: 70 处里只有 5 处真实 — 不做定性就会浪费
  大量精力在 dataclass 属性上;反之若因"看着像误报"跳过 `hasattr` 模式, 就漏掉
  真实崩溃点。
- **`hasattr` 陷阱值得单独记**: 在 pyslang 上做属性探测必须用
  `safe_attr(x, "name", None) is not None` 而不是 `hasattr` (后者不吞
  UnicodeDecodeError)。已写入本记录, 后续评审可据此扫描同类模式。
- 该族收敛至此: iter_141 (`str()` 转换点) + iter_182 (热路径 getter 70 点) +
  iter_183 (真实残余 5 点) — 抽取路径的属性读取风险基本清零; 可视化/CLI 侧
  剩余点均为 dataclass 误报。
