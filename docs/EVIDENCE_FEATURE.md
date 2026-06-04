# Evidence 功能 - 实施总结

> 创建时间: 2026-06-03
> 状态: ✅ Stage 1-3 全部完成
> 路径: /Users/fundou/my_dvproj/sv_query
> Git: main 分支

---

## 1. 起点问题

用户原话:
> "我希望加一个 evidence 功能,能实际告诉我这个代码来自源代码的哪一行,或者哪一个 scope,比如把某一个赋值语句对应的 always 或者 if block 完整召回"

即: trace 不仅能看 driver 链,还能看每一步**来自源代码的哪一行,被哪个 always/if 块包住**,完整召回该块源码。

---

## 2. 起点 vs 终点

| 指标 | Stage 0 (改前) | Stage 3 (改后) | Δ |
|------|---------------|----------------|---|
| TraceEdge 有 source_location | ❌ | ✅ | 100% 填充 |
| `get_source_location` 返回真实数据 | ❌ 返回 `("", 0, 0, 0)` | ✅ 返回 `(file, line, col, offset)` | 修复死代码 |
| always 块完整源码召回 | ❌ | ✅ (`enclosing_always.text`) | 核心需求 |
| if/else 块完整源码召回 | ❌ | ✅ (`enclosing_if.text`) | 核心需求 |
| enclosing scope chain | ❌ | ✅ 8 层 (inner condition → module) | 增强 |
| CLI 端到端查询 | ❌ | ✅ `run_cli.py trace evidence` | 用户面 |
| 测试 | 1418 | **1428** (+10) | 守护 |
| ruff 新增错误 | - | 0 | 干净 |

---

## 3. 4 Stages 实施回顾

### Stage 1 - `TraceEdge.source_location` 基础

**目标**: edge 知道自己来自哪一行源码

**改动**:
- `graph/models.py`: TraceEdge 加 `source_location: SourceLocation | None = None` 字段
- `semantic_adapter.py`: 修 `get_source_location` 走 `semantic_node.syntax.sourceRange` + `SourceManager.getLineNumber`
- `driver_extractor.py`: `extract()` 末尾加 post-processing pass,遍历 edges 填 source_location

**真实效果**: 0% → 70.2% 填充率(33/47 边)

**Commit**: `a1d21fa`

### Stage 2 - `TraceEvidenceResolver` + always/if 完整召回

**目标**: 走 AST parent 链找 enclosing always/if 块,完整召回源码

**改动**:
- 新增 `trace_evidence.py` (~250 行):
  - `Evidence` dataclass (含 `enclosing_always`, `enclosing_if`, `enclosing_chain`)
  - `TraceEvidenceResolver` 类 (`resolve(signal)` + `resolve_chain(signal)`)
  - `_walk_parent_chain`: 走 `condition_ast.syntax.parent` 链 (pyslang 原生)
  - `_make_snippet`: syntax node → SourceSnippet
- `semantic_adapter.py`: 加 `get_source_text(node)` helper
- 精确 kind 匹配 (`SyntaxKind.ConditionalStatement` 而非模糊 `Conditional*`)

**真实效果**:
- 完整 always_ff 块召回 (L33-45, 13 行)
- 完整 if/else 块召回 (L34-44, 11 行)
- enclosing_chain 8 层

**Commit**: `0887aee`

### Stage 3B - 100% source_location 填充率

**目标**: 修剩余 30% (14 边) 缺失

**根因**: 14 missing 边都是 CLOCK/RESET with combined condition,`condition_ast` 是纯 syntax node (没 `.syntax` 属性)。原 `get_source_location` 只处理 semantic node,silently 失败。

**改动**:
- `semantic_adapter.py get_source_location` 兼容两种: semantic node (有 `.syntax`) + syntax node 直接 (有 `.sourceRange`)

**真实效果**: 70.2% → **100%** 填充率 (47/47 边)

**Commit**: `ccb169e`

### Stage 3A - CLI 集成

**目标**: `run_cli.py trace evidence` 端到端可用

**改动**:
- `cli/commands/trace.py`: 新 `evidence` 子命令
  - 默认: 人友好文本输出
  - `--json`: JSON 输出(程序消费)
  - `--chain`: 递归 driver 链
  - `--pretty`: pretty-print JSON
  - `log_level="ERROR"` 避免 WARNING 污染 JSON stdout
- 3 个新 helper: `_snippet_to_dict`, `_evidence_to_dict`, `_output_evidence_text`

**真实效果**:
```
$ python run_cli.py trace evidence data_path.stage1_data -f test_data_path.sv

Signal: data_path.stage1_data
============================================================
Source: 'if (!rst_n) begin'

>>> Enclosing IF @ test_data_path.sv:34-44:
        if (!rst_n) begin
            stage1_data  <= '0;
            ...
        end else begin
            if (din_valid && din_ready) begin
                ...
            end
        end

>>> Enclosing ALWAYS @ test_data_path.sv:33-45:
    always_ff @(posedge clk or negedge rst_n) begin
        ...
    end
```

**Commit**: `d0ea750`

---

## 4. 数据流图

```
SV 源文件
  ↓
[UnifiedTracer.build_graph()]
  │
  ├─→ [StatementCollectorVisitor]  ← 已有
  │     └─ 条件 AST → ctx.condition_ast
  │
  └─→ [GraphBuilder/DriverExtractor]
        ├─ 边创建时填 condition_ast (V2.A.2 17b/17d)
        └─ extract() 末尾 post-processing
           ├─ ast.syntax.sourceRange → SourceLocation
           └─ 写 edge.source_location
  ↓
SignalGraph (TraceEdge 含 source_location + condition_ast)
  ↓
[TraceEvidenceResolver.resolve(signal)] ← Stage 2 新增
  │
  ├─ 找 signal 的 incoming edge
  ├─ condition_ast.syntax.parent 链
  │     ├─ 找 AlwaysFFBlock → enclosing_always
  │     └─ 找 ConditionalStatement → enclosing_if
  └─ SourceManager.getSourceText 提取完整源码
  ↓
Evidence (含 always/if 完整源码)
  ↓
[CLI: run_cli.py trace evidence] ← Stage 3A 新增
  │
  ├─ 默认: 文本输出
  └─ --json: JSON 输出
```

---

## 5. 关键设计决策

| 决策 | 选择 | 理由 |
|------|------|------|
| 数据持久化 (source_location on edge) | ✅ 边字段 | JSON 输出立刻可用,不依赖 resolver |
| AST 入口 | `semantic_node.syntax` | pyslang 原生, 走 parent 链 |
| parent 链 walk | `condition_ast.syntax.parent` | 无需从 assignment 重新定位 |
| 精确 kind 匹配 | `SyntaxKind.ConditionalStatement` | 避免匹配到 Predicate/Expression 中间节点 |
| 兼容 syntax node | `get_source_location` 改 | 100% 填充率 |
| 复用现有 dataclass | SourceLocation / SourceSnippet | 零新增类型 |
| CLI 输出两种模式 | text + JSON | 人 + 程序两用 |
| evidence CLI 入口 | `run_cli.py trace evidence` | 跟现有 trace 子命令一致 |

---

## 6. 关键经验教训 (10 条新增)

31. **pyslang source location 走 syntax.sourceRange**: semantic_node.syntax 拿 syntax 节点
32. **sm.getLineNumber(sr.start) 把 offset 转行号**: SourceManager 是 pyslang 给的工具
33. **semantic_node 和 syntax_node 是两个东西**: 前者有类型,后者有位置;get_source_location 兼容两者
34. **condition_ast 可能是纯 syntax node**: IntegerVectorExpressionSyntax (combined conditions) 没有 .syntax 属性
35. **parent 链 walk 是 enclosing scope 检索的关键**: pyslang SyntaxNode.parent 一直走上去到 root
36. **except Exception: pass 是隐形杀手**: Stage 1 post-processing 用 try/except 包住,失败 silently 14 边 Stage 3B 才暴露
37. **精确 kind 匹配 vs 模糊字符串匹配**: "Conditional" 匹配到 Predicate,只匹配 "ConditionalStatement" 才正确
38. **data layer 优先于 user layer**: Stage 1 修好数据,Stage 2 修好查询,Stage 3 加 CLI;反过来会更乱
39. **CLI 测试要 --log_level=ERROR**: V2.A.2 cycle 13 教训重复 — WARNING 污染 stdout
40. **typer 0.9+ registered_commands 是 list of CommandInfo**: name 是 None, 用 callback.__name__ 拿

---

## 7. 与 V2 / P1 关系

```
V1 → V2 (功能增量)
     ↓
     Coverage Generator 支持 JSON + 多信号 + AST 基础
     ↓
P1 (结构优化)
     ↓
     graph_builder 拆 5 个文件 + factory 消模板重复
     ↓
Evidence 功能 (新维度)
     ↓
     trace 不只看 driver 链, 还能看 source line + enclosing scope
```

V2/P1 是"做得更好",Evidence 是"做用户想要的新能力"。三者在代码上正交。

---

## 8. 验收标准 (全部达成)

- [x] TraceEdge 有 source_location 字段
- [x] `get_source_location` 修复返回真实数据
- [x] 100% 条件边 source_location 填充率 (47/47)
- [x] enclosing always 块完整多行源码召回
- [x] enclosing if 块完整多行源码召回
- [x] enclosing_chain 完整 scope 链
- [x] CLI 文本输出 (人友好)
- [x] CLI JSON 输出 (程序消费)
- [x] 1428 测试全过, ruff 干净

---

## 9. 剩余工作 (后续可选)

| 任务 | 价值 | 估计 |
|------|------|------|
| assignment 自身位置追踪 | 用户能精确知道 `q <= ...` 行 (而不仅是 if 条件行) | 1-2 cycle |
| `--chain` 模式真实测试 + 文档 | driver 链上每一步 evidence | 1 cycle |
| Evidence 嵌入 decompose() | CoverageGenerator 的 atomic 也带 source | 1 cycle |
| case path evidence 独立追溯 | case 语句的 evidence | 1 cycle |

---

## 10. 一句话总结

**Evidence 功能用 4 stages / 10 测试 / 4 commits,把 trace 从"看 driver 链"升级到"看 source line + 完整 always/if 块",100% 填充率, CLI 端到端可用,完整回应用户"把赋值语句对应的 always 或者 if block 完整召回"的核心需求。**

---

## Stage 5: 多命令 evidence 扩展 (2026-06-04)

> 状态: ✅ 完成
> 范围: trace / cdc / verify / risk / dataflow / controlflow 6 个命令
> 提交: 5 commits (1 refactor + 4 feat)

### 起点问题

Evidence 最初只在 `trace evidence` 命令上可用。用户问:

> "其他的功能还缺少 evidence 的输出，考虑如何实现。"

即: cdc / verify / risk / dataflow / controlflow 等命令的结果也应该能告诉用户"这个信号在源码的哪一行 / 哪个 always 块"。

### 设计原则

1. **可选项 (--evidence flag)**: 默认关闭,不破坏现有输出
2. **共享 graph**: 命令入口 `make_resolver(graph, adapter)` 一次,后续 evidence 解析共享同一 graph,避免重复 build
3. **JSON + text 双格式**: JSON 加 `evidence` 字段,text 模式贴 1 行 summary (└─ file:line: source)
4. **公共 helper**: `src/cli/_evidence_helpers.py` 集中 build_resolver / evidence_to_dict / summary_line,避免复制

### 命令集成

| 命令 | evidence 位置 | 用户场景 |
|------|-------------|---------|
| `trace evidence` | (已有) | 一个信号的完整 always/if 块 |
| `trace fanin/fanout/impact` | 同模块扩展 (未做) | 路径上每个 hop 的来源 |
| `cdc analyze` | `paths[].source_evidence` / `target_evidence` | 跨域点 source/target 的 always_ff 块 |
| `verify gap` | `top_signals[].evidence` / `gap_signals[].evidence` | "dout 风险高缺 SVA, 它在哪个 always 块?" |
| `risk analyze` | `data_signals[].evidence` | 数据信号排名前 20 的驱动代码位置 |
| `dataflow analyze` | `paths[].segments[].evidence` | "从 din 到 dout 的中间 hop 都在哪?" |
| `controlflow analyze` | `conditions[].evidence` | "dout 的每个条件驱动 (if / else / reset) 都在哪?" |

### 实施变更

**1. 抽公共 helper** (`src/cli/_evidence_helpers.py`, 124 行)

```python
def build_resolver(file, log_level="ERROR") -> tuple: ...  # 统一 build graph + adapter + resolver
def make_resolver(graph, adapter) -> TraceEvidenceResolver: ...  # 复用已有 graph
def evidence_to_dict(ev) -> dict: ...  # Evidence → JSON
def snippet_to_dict(snippet) -> dict: ...  # SourceSnippet → JSON
def evidence_summary_line(ev) -> str: ...  # 1 行文本摘要
def evidence_summary_indented(ev, indent="  └─ ") -> str: ...  # 缩进版本
```

**2. trace.py 切到公共 helper**

`_snippet_to_dict` / `_evidence_to_dict` 从 trace.py 移到 helper 文件,行为完全等价,1458 测试全过。**副作用**: JSON 多暴露 `is_verified` + `credibility_score` 字段 (Stage 4 后已有,现在外部可见)。

**3. 5 个命令加 --evidence flag**

每个命令:
- 加 `evidence: bool = typer.Option(False, "--evidence", "-e", ...)` 参数
- 入口 build 一次 resolver: `evidence_resolver = _make_evidence_resolver(graph, tracer._get_adapter())`
- JSON 模式: 在 result dict 里给每条信号结果加 `evidence` 字段 (完整 dict)
- text 模式: 在每条结果下方贴 1 行 summary (└─ file:line: source)

**4. cdc 命令修了一个旧 bug**

`cdc_report` 返回的 `domain_pairs` 用 tuple 当 key (类似 `(clk_a, clk_b)`),`json.dumps` 之前会 crash。新加 `_json_safe()` 转换函数,递归把 dict 的非 str key 转 str,`cdc --json` 现在能正常用。

### 验收

- ✅ 5 命令支持 `--evidence` flag (默认 off, 向后兼容)
- ✅ 公共 helper 抽完,trace.py 切完,等价 refactor
- ✅ 23 个新测试 (TestVerifyGapEvidence / TestRiskAnalyzeEvidence / TestDataflowEvidence / TestControlflowEvidence / TestCdcEvidence / TestEvidenceSummaryInputs)
- ✅ 全量 1481 测试通过 (Stage 4 后 1458, +23 新增)
- ✅ cdc --json 旧 bug 一并修

### 真实效果示例

**`risk analyze --evidence` 输出**:
```
风险分析: sim/test_simple.sv
================================================================================
  ⏰ 时钟信号 (1): clk
  🔄 复位信号 (1): rst_n

  数据信号风险排名:
  排名   信号                        类型     fan_in fan_out 功能分    时序分
  ──── ───────────────────────── ────── ────── ─────── ────── ──────
     1 dout                      ?           4       0 🔴  47.3 ⏱🟠  38.0  SVA:✗ Cov:✗
  └─ sim/test_simple.sv:16: if (!rst_n)
     2 data                      ?           1       1 🟠  25.3 ⏱🟡  17.0  SVA:✗ Cov:✗
  └─ sim/test_simple.sv:12: data = din;
```

**`cdc analyze --evidence` 输出**:
```
[1] 🔴 top.reg_a → top.dout_b
    域: top.clk_a → top.clk_b
    边: EdgeKind.DRIVER | 同步器: ✗
        source: sim/test_cdc.sv:23: if (!rst_n)
        target: sim/test_cdc.sv:31: if (!rst_n)
```

### 未来可选 (未做)

- `trace fanin/fanout/impact` 加 evidence (同模块扩展, helper 已就绪, 估计 1 commit)
- `coverage suggest` 加 evidence (把覆盖度建议跟 atomic 信号源码位置关联)
- `sva analyze` 加 evidence (SVA 绑定位置)
- evidence 嵌入 coverage decompose (Stage 3 留的 TODO)
- LRU 缓存跨命令共享 (现在每次命令 build 一次, 单命令内已共享)
