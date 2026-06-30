# 📘 LLM_INDEX.md - sv_query 文档索引 (LLM 专用)

> **受众**: 想**理解/扩展/调试** sv_query 的 LLM agent
> **触发**: 用户问"怎么改 sv_query"、"为什么这样设计"、"怎么加新功能"、"这个 bug 怎么 debug"、"性能问题"
> **不适用**: 用户想**使用** sv_query → 用 sv-query skill (`.openclaw/workspace/skills/sv-query/SKILL.md`)

---

## 🎯 何时读这个索引

| 用户问题模式 | 用什么 |
|-------------|--------|
| "用 sv_query 找信号驱动 / CDC / 风险评分" | **sv-query skill** (操作手册) |
| "怎么改 sv_query 加新功能" | **LLM_INDEX** (本文) → docs/PROJECT_PLAN.md + docs/PENDING_FEATURES.md |
| "为什么 sv_query 这样设计" | **LLM_INDEX** → docs/FINAL_SCHEMA_DECISION.md |
| "怎么扩展一个 handler 提取新 AST 数据" | **LLM_INDEX** → docs/HANDLER_WRITING_GUIDE.md + docs/SYNTAX_KIND_HANDLER_MAP.md |
| "跑测试挂了 / 怎么 debug" | **LLM_INDEX** → docs/CODE_DISCIPLINE_REVIEW.md + docs/REFACTOR_GUIDE_v2.md |
| "pyslang 报奇怪错 / OOM" | **LLM_INDEX** → docs/PYSLANG_MEMORY_ISSUE.md + docs/PYSLANG_COMPAT.md |
| "知道有哪些已知 bug / 限制" | **LLM_INDEX** → docs/KNOWN_LIMITATIONS.md + docs/ISSUES_SUMMARY.md |
| "怎么对接一个新开源项目" | **LLM_INDEX** → docs/OPENCHIP_QA_ROUND* + docs/NAPLESPU_HOWTO / OPENTITAN_HOWTO |

---

## 📚 文档分类 (按"何时读")

### 🟢 用户用 (跟 LLM agent 无关，给真实用户)

> **LLM 通常不需要读这些**, 但要知道存在, 避免给用户错误指引:

- `README.md` - 项目主页 (50K, 含 5 分钟快速上手 + 全部命令)
- `USER_GUIDE.md` - 完整用户指南 (CLI + Python API + Filelist)
- `EXAMPLES.md` - 18K 命令示例集
- `FILELIST.md` - Filelist 格式说明

### 🟡 架构理解 (LLM 改 sv_query 前必读)

按**推荐阅读顺序**:

1. **`FINAL_SCHEMA_DECISION.md`** ⭐ - 架构最终决定 (为什么用 pyslang AST + NetworkX)
2. **`ARCHITECTURE_DEEP_REVIEW.md`** ⭐ - 深度架构 Review
3. **`GRAPH_BUILDER_REVIEW.md`** - GraphBuilder 详细 Review
4. **`CORE_RESTRUCTURE.md`** - 核心模块重构记录
5. `architecture/architecture.md` - 总体架构图
6. `architecture/SV_SYNTAX_ROADMAP.md` - SV 语法支持路线图

**不推荐一次性全读**。先读 FINAL_SCHEMA_DECISION.md 了解核心决定, 再按需要深入.

### 🟠 功能模块设计 (改具体功能时)

| 想改的功能 | 必读 |
|-----------|------|
| **DataFlow 分析** | `DATAFLOW_ANALYSIS_ARCHITECTURE.md` + `DATAFLOW_IMPLEMENTATION_PLAN.md` + `SIGNAL_GRAPH_ANALYSIS_REQUIREMENTS.md` |
| **ControlFlow 分析** | `CONTROL_FLOW_ANALYSIS.md` + `CONTROL_FLOW_DESIGN.md` + `CONTROL_FLOW_IMPROVEMENTS.md` |
| **Coverage Generator** | `COVERAGE_GENERATOR.md` + `COVERAGE_GEN.md` + `COVERAGE_GENERATOR_V2.md` |
| **SVA / CDC / Timing** | `SVA_ANALYSIS.md` + `CDC_ANALYSIS.md` + `TIMING_ANALYSIS.md` |
| **Protocol Detection (AXI/AHB/APB)** | `PROTOCOL_DETECTION_PLAN.md` + `PROTOCOL_DETECTION_PLAN_REVIEW.md` |
| **可视化 (Graphviz)** | `VISUALIZATION.md` + `VIZ_GOLDEN_PLAN.md` |
| **新 handler** (提取 AST 数据) | `HANDLER_WRITING_GUIDE.md` ⭐ + `SYNTAX_KIND_HANDLER_MAP.md` |
| **基于 pyslang.visit()** | `DESIGN_PYSALNG_VISIT_BASED_ONHANDLER.md` + `PROPOSAL_REFLECTION_BASED_HANDLER.md` |

### 🔴 调试 / 排错 (碰到具体问题)

| 问题 | 读这个 |
|------|--------|
| **pyslang OOM / 内存不足** | `PYSLANG_MEMORY_ISSUE.md` ⭐ (有 8GB MBA 解决方案) |
| **pyslang v10/v11 不兼容** | `PYSLANG_COMPAT.md` + 内部 `src/trace/core/_pyslang_compat.py` |
| **测试失败** | `KNOWN_LIMITATIONS.md` + `ISSUES_SUMMARY.md` |
| **代码质量问题** | `CODE_DISCIPLINE_REVIEW.md` + `DISCIPLINE_VIOLATIONS.md` |
| **重构方向** | `REFACTOR_DETAILED_PLAN.md` + `REFACTOR_GUIDE_v2.md` |
| **CI 报错** | `CODE_DISCIPLINE_REVIEW.md` (有 ruff 配置) |
| **某个 feature 不 work** | `OPENCHIP_QA_ROUND*` (5 个开源项目 QA 记录) |
| **NaplesPU 项目** | `NAPLESPU_HOWTO.md` + `NAPLESPU_TEST_ISSUES_*.md` |
| **OpenTitan 项目** | `OPENTITAN_HOWTO.md` |

### 🟣 需求 / 规划 (新增 feature)

- `PROJECT_PLAN.md` - 项目整体规划
- `PENDING_FEATURES.md` - 待实现功能清单 (按优先级)
- `REQUIREMENT_*.md` (4 个) - 各方向需求评估
- `REQ5_6_7_8_*.md` (2 个) - REQ 阶段需求
- `DESIGNER_PLAN.md` - 设计师规划

### ⚪ 归档 (历史档案, 不读)

`archive/` 目录的 21 个文档都已过时, **不要读**. 如果某个 doc 在 archive 之外但仍指向 archive 里的内容, 说明它自己也可能过时.

---

## 🔥 必读 TOP 5 (改 sv_query 前最少要看)

1. **`FINAL_SCHEMA_DECISION.md`** ⭐⭐⭐ - 知道为什么 sv_query 是现在这个架构
2. **`ARCHITECTURE_DEEP_REVIEW.md`** ⭐⭐ - 理解核心组件边界
3. **`HANDLER_WRITING_GUIDE.md`** ⭐⭐ (改 AST 提取时) - 怎么写新 handler
4. **`KNOWN_LIMITATIONS.md`** ⭐ - 哪些坑已经有解决方案
5. **`PYSLANG_MEMORY_ISSUE.md`** ⭐ (OOM 时) - 8GB 内存下的 workaround

---

## 🛠️ 改 sv_query 的标准流程

```
1. 读 LLM_INDEX.md (本文) 决定读哪个 doc
   ↓
2. 读对应 doc 了解设计意图
   ↓
3. 看 src/ 里相关代码 (unified_tracer.py → graph_builder.py → semantic_adapter.py)
   ↓
4. 写 TDD 测试: python3 -m pytest sim/tests/ -k <new_feature>
   ↓
5. 改代码 → 跑全量: python3 -m pytest sim/tests/ -q (期望 2397 passed)
   ↓
6. ruff 检查: ruff check src/ tests/ (期望 0 错误)
   ↓
7. 写一个 doc 总结改动 (参考 docs/EVIDENCE_FEATURE.md 的 Stage 1-3 风格)
   ↓
8. git commit + git push origin main
```

---

## 🤖 给 LLM agent 的硬规则 (改 sv_query 时)

1. **永远** `cd ~/my_dv_proj/sv_query` (主目录, 不是 OpenClaw 别名 `~/my_dvproj/`)
2. **永远** 先跑 `python3 -m pytest sim/tests/ -q` 看基线 (期望 2397 passed)
3. **永远** TDD: 先写失败测试 → 改代码 → 测试 pass
4. **永远** 跑全量, 不要只跑改动的文件 (可能有 side effect)
5. **永远** 改 pyslang 相关代码先看 `PYSLANG_COMPAT.md` (v10/v11 差异)
6. **永远** 改 graph builder 先看 `GRAPH_BUILDER_REVIEW.md`
7. **不要** 改 doc/archive/ 里的过时文档
8. **不要** 跳过 ruff 检查就 commit
9. **不要** 跳过测试就 push
10. **不要** 用 `--no-strict` workaround (user 要求 strict mode)

---

## 📊 项目统计 (背景信息)

| 项 | 数值 |
|----|------|
| 测试数 | 2397 passed (含 7 xfail for 8GB MBA 环境限制) |
| 命令数 | 14 (`trace`/`dataflow`/`cdc`/`risk`/`sva`/`verify`/`timing`/`coverage`/`visualize`/`diff`/`snapshot`/`search`/`stats`/`arch`) |
| 文档数 | 90 (`docs/` + 24 `docs/archive/` + 9 `docs/architecture/`) |
| 验证过的开源项目 | 6 (PicoRV32, CVA6, darkriscv, serv, zipcpu, vortex) |
| 最近发布 | arch 命令 (2026-06-25), $clog2 macro fix (2026-06-25) |
| Python | 3.11+ |
| pyslang | v10/v11 (内置 `_pyslang_compat.py` shim) |

---

## 🔗 相关索引 (互补不重叠)

| 索引 | 受众 | 何时用 |
|------|------|--------|
| **本文 (LLM_INDEX.md)** | LLM agent 扩展/理解 sv_query | 改 sv_query 前 |
| [INDEX.md](INDEX.md) | 人类浏览 (按类别) | 找特定 doc |
| [DOC_INDEX.md](DOC_INDEX.md) | 文档维护者 (归档管理) | 整理 docs 时 |
| `~/.openclaw/workspace/skills/sv-query/SKILL.md` | LLM agent 使用 sv_query | 用户想跑 sv_query 时 |

**重要**: 本文不是 INDEX.md 的 LLM 版. INDEX.md 是给人按类别浏览的; 本文是给 LLM 按"用户问什么 → 读哪个 doc"决策的.

---

## 🔍 关键文档快速摘要 (1 行)

| Doc | 何时读 (1 行) |
|-----|--------------|
| FINAL_SCHEMA_DECISION | 改任何东西前 (知道为什么这样设计) |
| ARCHITECTURE_DEEP_REVIEW | 想动核心组件前 |
| GRAPH_BUILDER_REVIEW | 改 graph_builder.py 前 |
| HANDLER_WRITING_GUIDE | 加新 handler 提取 AST 数据时 |
| SYNTAX_KIND_HANDLER_MAP | 选 SyntaxKind → handler 映射时 |
| PYSLANG_MEMORY_ISSUE | OOM / elaboration 不完整时 |
| PYSLANG_COMPAT | 改 pyslang 调用前 (v10/v11 差异) |
| KNOWN_LIMITATIONS | 知道哪些坑已修 |
| ISSUES_SUMMARY | 找 issue 编号 / 状态 |
| CODE_DISCIPLINE_REVIEW | ruff 报错或代码风格问题 |
| DATAFLOW_ANALYSIS_ARCHITECTURE | 改 dataflow 时 |
| CONTROL_FLOW_ANALYSIS | 改 controlflow 时 |
| COVERAGE_GENERATOR | 改 coverage 命令时 |
| SVA_ANALYSIS / CDC_ANALYSIS / TIMING_ANALYSIS | 改对应功能时 |
| PROTOCOL_DETECTION_PLAN | 改协议识别 (AXI/AHB) 时 |
| VISUALIZATION | 改 Graphviz 生成时 |
| OPENCHIP_QA_ROUND* | 调试特定开源项目兼容时 |
| NAPLESPU_HOWTO / OPENTITAN_HOWTO | 这两个项目遇到问题时 |
| REFACTOR_DETAILED_PLAN / REFACTOR_GUIDE_v2 | 准备大重构前 |
| PROJECT_PLAN / PENDING_FEATURES | 决定下一步该做什么时 |

---

## 💡 Tip: 避免噪音

`docs/` 有 90 个文件, **80% 是历史/计划/特定项目 QA 记录**. 改 sv_query 时:

1. **不要** 默认全读
2. **不要** 读 `archive/` 下的文档 (已过时)
3. **不要** 读 `OPENCHIP_QA_ROUND*` (除非在调试对应开源项目)
4. **优先** 读 TOP 5 必读 + 你要改的功能模块设计 doc
5. **永远** 先跑测试基线 (期望 2397 passed), 再改

---

## 📞 找不到答案?

如果按本文索引读完还是不知道:

1. 看 `src/trace/unified_tracer.py` 入口
2. 看 `src/trace/core/` 核心组件
3. 看 `sim/tests/` 找类似测试当模板
4. **不要** 自己造新架构 — sv_query 已经有完整架构, 大部分需求是扩 handler, 不是改架构

如果还是没有, 跟 user 说"超出 skill 范围, 需要 author 介入"或提 issue.