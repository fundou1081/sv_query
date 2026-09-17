# L1: CLI 分层与专注化 (从 64 个平铺命令到分层能力面)

**Metadata**:
- **Task Tree Level**: L1
- **Created**: 2026-09-09 GMT+8
- **Author**: 方豆 / AI 助手
- **Status**: 🟡 IN PROGRESS (P0 ✅ done / P1~P5 待做)
- **触发指令**: 方豆 "我们现在做的命令太多了，不够专注… 应该有取舍，至少分层。或者拆分为不同子项目单独开发。你来给一些建议"

---

## 🎯 问题 (实测, 不是感觉)

| 症状 | 数据 |
|---|---|
| 命令平铺混装 | **21 组 / 64 叶子命令** 全在一个命名空间 |
| 机器面/人眼面混在一起 | 支持 `--json` 仅 **42/64**; `visualize` 组只有 1/10 |
| 承诺等级不透明 | 5 组标 `[EXPERIMENTAL]` 却与正式命令并列 |
| 选项当 API | `trace fanin` **20** 个选项、`fanout` **23** 个 — agent 会猜错 |
| 零/薄测试命令在售 | `visualize datapath` **0 测试**、`diff` 3 文件、`design` 3 文件 |

## 📐 方豆的决策 (2026-09-09, 逐条落地)

| # | 决策 | 落地 |
|---|---|---|
| 1 | **sv_query 不改 RTL 代码** | R3 检查器: CLI 内禁止"隐式改文件"; 会写文件的 `fix timescale --apply` / `fix imports --write` → `out` 层, P2 移出到 `tools/` |
| 2 | **验证域统一降级** | `sva/coverage/verify/risk/randomize` → `exp/verif` |
| 3 | **总线结构域也降级** | `protocol/handshake/backpressure` → `exp/bus` |
| 4 | **主消费者 = agent; 人眼可视化之后重点开发** | `core` 一等公民(只读+JSON+稳定 schema); `view` 独立层 + 独立路线图 (V1~V5) |
| 5 | **从目录结构体现命令分层** | 目标树 `src/cli/{core,view,exp,dev}/` + `_registry.py` 声明 (见下) |
| 6 | **不拆仓** | kernel 与测试资产保持单仓 |
| 7 | **cdc/timing 算法不可靠 → 待定** | 暂放 `exp/struct`, 配可量化晋升门槛 (见 `docs/EXP_NAMESPACE.md`) |
| 8 | **snapshot/diff 放 core** | "比较的是 graph" → `core/state` (`stateful=True`) |
| 9 | **capabilities 默认包含 view** | 默认列出 core+view; `--recommended` 给 agent 最小集; `--include-exp` 才列降级区 |
| 10 | **fanin/fanout 改名 (方案 a: 顶层)** | ✅ `svq drivers` / `svq loads` 顶层; 老名保留为同实现别名 (iter_231 完成) |

## 🎯 目标结构

```
src/cli/
├── main.py            # 只做组装 (auto-discover), 不再 21 行手写注册
├── _registry.py       # ✅ P0 已建: 层规范 + 命令分类表 (单一真相源)
├── shared/            # (P1) 跨层共享: tracer/options/output/errors
├── core/              # ① agent 一等公民: 只读 + JSON + 稳定 schema  (semantic/locate/state/diagnose)
├── view/              # ② 人眼面: 图与叙述 (默认含于 capabilities, 重点开发)
├── exp/               # ③ 降级区: bus(9) + verif(13) + struct(2)
└── dev/               # ④ 内部调试: expression (3)
```

**当前规模 (P0 登记)**: core=23 / view=13 / exp=24 / dev=3 / out=2 = **65**。
**P1+ 计划新增**: `instances` / `instance` / `connections` / `hierarchy` (语义 core 缺口, 复用已有 API)。

## 📋 批次

| 批 | 内容 | 状态 |
|---|---|---|
| **P0** | `_registry.py` + `capabilities` 命令 + `check_cli_layers.py`(R1~R6) + `gen_cli_surface.py` + `docs/CLI_SURFACE.md` | ✅ **完成** |
| **P1a** | 规范入口 `drivers`/`loads` (顶层, 方案 a) + 同实现别名 + 补 3 条 `--json` + 检查器 R7 | ✅ **完成 (iter_231)** |
| **P1b-1** | `exp/` 层目录落地 (`src/cli/exp/{bus,verif,struct}/`, 9 文件) + `_paths.py` 锚点 + R8 + 引用扫描工具 | ✅ **完成 (iter_232)** |
| P1b-2 | `dev/` + `core/{locate,state,semantic}/` + `view/` 整文件搬迁 (fix*.py 留 P2) | 待做 |
| P1b-3 | 拆分 `trace.py` (core signal + view overview) 与 `visualize.py` (10 个 view 命令) | 待做 |
| P2 | 只读落地: `fix timescale --apply` / `fix imports --write` 移出到 `tools/`; `snapshot` 默认目录迁 `$SVQ_CACHE_DIR`; 只读证明测试 (目录树 hash 不变) | 待做 |
| P3 | `exp` 收纳 (bus/verif/struct 三域) + capabilities 分层过滤生效 | 待做 |
| P4 | 域内合并: bus 9→4; verif 13→~8; `diff compare` 并入 `snapshot compare` | 待做 |
| P5 | `view` 重点建设: 迁完 4 个旧渲染器 → VizData; 解冻 12 个 SVG 断言; `datapath` 补测试转正 | 待做 |
| P6 | `exp` 复审 (转正/归档) + cdc/timing 晋升门槛评估 | 待做 |

## 🔗 机械保障 (P0 已就位)

| 工具 | 作用 | 现状 |
|---|---|---|
| `python3 tools/check_cli_layers.py` | R1 未分层(含别名) / R2 反向依赖 / R3 隐式改文件 / R4 core 缺 JSON / R5 exp 名污染 / R6 exp 进默认清单 / **R7 builtin 遮蔽** / **R8 `__file__` 深度运算** | ✅ rc=0 (6 条已知基线不阻塞, 新违规即失败) |
| `python3 tools/gen_cli_surface.py [--check]` | 生成/校验 `docs/CLI_SURFACE.md` (清单不再手写) | ✅ 一致 |
| `python3 tools/find_module_refs.py <模块>` | **搬目录前**的引用扫描单 (import-dotted / from-import / 路径串 / `__file__` 深度运算) | ✅ 新增 (iter_232) |
| `svq capabilities [--json] [--recommended] [--include-exp]` | agent 的工具面真相源 | ✅ |

## 📎 相关

- 设计依据: `docs/CLI_SURFACE.md` (生成物) / `docs/EXP_NAMESPACE.md` (降级政策 + 晋升门槛)
- 迭代: [iter_230](../iterations/iter_230_cli_layering_p0.md)
- 关联决策: AGENTS 核心纪律 4 (`-f` 用法); iter_226~229 (只读/全绿基线)
