# sv_query 对话/工作记录 (2026-11-09 ~ 2026-11-11)

> **性质**: 本轮多轮对话的**事实重建记录**，不是逐字 transcript。
> 目的: 让接手 agent 知道“当时用户要什么、做了什么决定、为什么、哪些尝试失败”。
> 逐字原始对话不随仓库保存；可复现事实以命令、commit、validation 文档为准。
> **当前 HEAD**: `475d1190`（P162 handoff）

---

## 0. 一句话

用户要做的不是“更多 RTL 分析”，而是：

> **让 agent 对 RTL 的结论可以被机器验证或反驳。**

因此整个过程中的主线是：

```text
查询能力 → 验证语义 → 证据等级 → 真实项目 corpus → 反例/确定性 → 交接
```

---

## 1. 用户明确表达的原则

这些是产品决策，不是 agent 可以自行改写的：

1. **核心不是做更多分析，而是让 agent 的 RTL 结论可验证。**
2. **不得自动做 OpenTitan 特定 FIFO/接口推断**；可以留接口/样例，但不要混进主目录。
3. **不得修改用户的 RTL/工程文件**；写能力只能放 tools 或显式 CLI 写命令。
4. **不得 silent fallback**；失败必须显式。
5. **不得用假指标/假通过/假 verified 骗过门禁。**
6. 真实项目优先于 fixture。
7. 发现问题要逐个记录，失败尝试也要如实写，不要事后美化。

---

## 2. 时间线

| 阶段 | 用户指令/事件 | 实际动作 | 结果 |
|---|---|---|---|
| 早期 | 建 agent 查询 + 校验层；不做项目特判 | 语义 AST、SignalGraph、MIG、CLI capabilities | 45 命令、JSON 契约 |
| P139/P140/P142 | 扩展 trace/frontier/constraint | frontier、boundary runner、constraint-chain | 能力扩展 |
| P145 | canonical gate + agent corpus | 15-task corpus、false-confident/false-found | canonical 基线 |
| P146 | 真实 UART/I2C matrix | worker 跑真实 snapshot，发现 21 个问题 | 手工 filelist 4 轮；问题入账 |
| P147 | “第三个 block SPI_HOST” | 建图、6 smoke task、worker RTL 核对 | 第三人真实 block |
| P148 | 修 width sentinel | 单 bit bit_range | SPI bit 718→171 |
| P149 | consistency from snapshot | `--from-snapshot`；MIG 缺失 unknown | 离线 check |
| P150 | 修 id_parent 误报 | 只检查直接 child | SPI bit 171→0 |
| P151 | snapshot MIG 持久化 | `to_dict/from_dict` + loader | connection 可离线 |
| P152 | “先 p152 吧” | SPI 9-task corpus；worker APPROVE WITH NITS | 9/9 手工通过 |
| P153 | 修 N-2 | wrapper passthrough 源 append | transitive verified |
| P154 | 修 N-3 | instances/connections/ports snapshot；probes 可执行 | snapshot probes |
| P155 | 修 reciprocity | 只比较 DRIVER/CONNECTION | SPI 128→0 |
| P156 | snapshot/MIG 问题 | MIG metadata、present/instances/ports | 旧 snapshot 可预检 |
| P157 | “那12个skip怎么回事” → “清理一下吧” | 删 deadlock、external 标 opensource | canonical 0 skipped（后来证明是错误指标） |
| 复盘 | “让worker全面复盘...最终汇总” | 4 个只读 worker：架构/产品/测试/性能 | 综合 6.2/10；R-001~R-028 |
| P158.0 | “修改纪律和补充唯一概念语义” | SEMANTIC_CONTRACTS / CLAIMS / GLOSSARY；AGENTS 铁律13；DISCIPLINE §0.1 | 规范先立 |
| P158.1 | 开始逐个修 | contracts.py；CLOCK 不再数据路径 | 假 verified 修复 |
| P158.2 | 有界 paths | max_expansions/deadline/truncated | SPI >30s → 0.6s |
| P158.3 | 构建确定性 | id(pyslang wrapper) GC 复用根因；强引用保活 | 3 次构建一致 |
| P158.4 | SPI corpus | runner + 9 tasks | 可执行 |
| P158.5 | filelist 安全 | dry-run/--apply/.f/.fl/--force/.bak | 不覆盖 RTL |
| P158.6 | truncated verified | coverage_complete/partial_checks | sample 不再 verified |
| P158.7 | snapshot 构造/损坏 | load_snapshot、module_ports、tag 权威 | 结构化错误 |
| P158.8 | true-positive/legacy | bit/reciprocity/legacy snapshot | 检查器不再空转 |
| P158.9.1 | capabilities/schema | core_groups、40 core contracts | 覆盖测试 |
| P158.10 | CI/gate | run_gates.sh、增量 ruff | CI 与本地同源 |
| P158.11.1 | dataflow snapshot | --from-snapshot、frontier --max-visits | 快照查询可用 |
| P159 | “把踩过的坑记录下来” | 独立 worker 写 1367 行复盘 | 22 坑/10 经验/20 反模式 |
| P160 | “下一步建议什么” → “去做吧” | 38 opensource 失败分诊 | 19 exp / 5 baseline / 4 env / 10 stale |
| P161 | “可以，去做吧” | 清退/修 ID/重定 baseline/显式 env skip | opensource 0 failed |
| P158.11.2a | snapshot size | SVQ_SNAPSHOT_MAX_MB + metadata | 超限不落盘 |
| P162 | “准备交接文档” | docs/dev/HANDOFF.md | 可交接 |
| P163 | “把对话记录写下来” | 本文档 | 可追溯 |

---

## 3. 关键决策记录

### 3.1 不做自动 FIFO 推断

用户明确：

> 不许自动识别；可以预留接口；可以作为样例代码，但不要合并在主目录。

执行：

```text
core 不按名字建 FIFO 边
project adaptation 只在 examples/project_adaptations/
无项目特定 heuristics
```

### 3.2 第三真实 block

用户批准 P147 SPI_HOST。实际使用外部 `/tmp` snapshot，不把 OpenTitan 源码/依赖塞进 repo。

### 3.3 P157 的“0 skipped”是错误决策

用户问“12 个 skip 怎么回事”。
当时目标是把 canonical 变干净，执行方式是把外部测试标 `opensource`、删 deadlock；
结果 opensource 套件实际有约 27% 失败，被移出了统计。

后续：

```text
P160 triage: 38 failed / 98 passed / 5 skipped
P161 remediation: 114 passed / 17 skipped / 0 failed
```

这个教训已写进 P159 复盘和 CLAIMS C-10：
**0 skipped 不是健康指标。**

### 3.4 四角度 review 后先改纪律

用户问：

> 纪律有漏洞，还是执行有歧义？

结论：

```text
主因是纪律覆盖漏洞：门禁只查形式，不查语义。
次因是概念定义缺失，导致执行歧义。
```

因此先做 P158.0：

```text
SEMANTIC_CONTRACTS
CLAIMS
GLOSSARY 唯一概念语义
AGENTS 铁律13
DISCIPLINE §0.1
```

再逐个修代码。

### 3.5 交接边界

用户要求其他 agent 接手一部分工作，再交回。
交接文档明确：

- 不允许改 PLAN/docs/CLAIMS（除非主会话明确）；
- worker 独立 worktree；
- 主会话复现 P0；
- 交回 checklist。

---

## 4. 失败尝试 / 误判记录

### 4.1 P158.3 源码位置 key 方案

worker 尝试用 pyslang 源码位置作为 genvar context key。
结果：generate-for 多个展开项共享位置，18 个 generate 测试失败，context 全错位。
处理：回退；最终用 `_ast_ctx_refs` 强引用保活 wrapper，让 id() 在生命周期内唯一。

**教训**：

```text
“更稳定”的 key 不一定更正确；
generate 展开项共享源码位置。
```

### 4.2 P157 的 skip 清理

以为把外部测试移出 canonical 就是“清理”，实际掩盖 27% 失败。
处理：P160/P161 重新分类、修复、显式 skip；不再用 fail→skip。

### 4.3 golden auto-bless

`_read_golden` 缺失时自动生成，导致期望被实现悄悄改写。
P160/P161：删除 auto-bless；缺失 baseline 直接失败；
重定 golden/baseline 必须记录理由。

### 4.4 worker APPROVE 不是证据

P152 worker 曾用一次 fresh parse 得到“byte-identical”；后来证明构建非确定。
处理：

- P158.3 用 3 次构建验证；
- 交接文档要求主会话复现 P0；
- CLAIMS C-12 记录“worker APPROVE ≠ 真实项目通过”。

### 4.5 配额/中断

- P160 worker 遇 MiniMax 429，主会话接管 triage；
- P158 edge/det worker 在收尾前 429，主会话从 worktree 取改动，重新验证；
- det 的改动还误带 AGENTS/repro 脚本，主会话只取 src 变更。

**教训**：worker 需要独立 worktree + 可审查 diff，合并前必须重跑。

---

## 5. 关键命令与证据

### canonical

```bash
cd /Users/fundou/my_dv_proj/sv_query
bash tools/run_gates.sh
```

当前：

```text
2678 passed / 0 skipped / 131 deselected / 0 failed
```

### opensource

```bash
python3 -m pytest sim/tests/ -m "opensource" -q -p no:randomly
```

当前：

```text
114 passed / 17 skipped / 0 failed
```

### SPI corpus

```bash
SVQ_SNAPSHOT_DIR=/tmp/opentitan_svq_spi/snapshots \
python3 tools/agent/run_spi_corpus.py --json
# 9/9
```

### 关键反例

```bash
# CLOCK 不得是数据路径
python3 run_cli.py paths top_minimal.sa1.clk top_minimal.sa1.ready_q \
  --filelist sim/tests/fixtures/minimal_3module/filelist.f --directed --json
# found=false

# 截断不得 verified
SVQ_SNAPSHOT_DIR=/tmp/opentitan_svq_spi/snapshots \
python3 run_cli.py verify consistency --from-snapshot opentitan_spi \
  --checks reciprocity --json
# verified=false, partial_checks=["reciprocity"]
```

---

## 6. Worker 记录

| worker | 目的 | 结果 |
|---|---|---|
| `svq-p152-spi` | SPI 9-task 独立验证 | APPROVE WITH NITS；N-2/N-3 后续修复 |
| `svq-p158-edge` | data edge + bounds | 改动被主会话接管；429 中断 |
| `svq-p158-det` | determinism | 源码位置方案失败；强引用方案被主会话采用；429 中断 |
| `svq-p158-corpus` | SPI corpus runner | 提交 `f52a6740` |
| `svq-lessons` | 踩坑历史 | 1367 行复盘；独立复核 opensource 27% |
| `svq-p160-opensource` | opensource triage | 429 中断；主会话完成 |

---

## 7. 当前状态（接手用）

```text
HEAD: 475d1190
canonical: 2678 passed / 0 skipped / 131 deselected / 0 failed
opensource: 114 passed / 17 skipped / 0 failed
```

剩余：

```text
P158.11.2b 通用长查询 timeout
P158.9    snapshot surface 矩阵
P158.12   P2 清理
17 个 opensource skip 分类
```

必读：

- [HANDOFF](../dev/HANDOFF.md)
- [SEMANTIC_CONTRACTS](../dev/SEMANTIC_CONTRACTS.md)
- [CLAIMS](../dev/CLAIMS.md)
- [P160 triage](../validation/P160_OPENSOURCE_TRIAGE_2026-11-11.md)
- [P161 remediation](../validation/P161_OPENSOURCE_REMEDIATION_2026-11-11.md)
- [P159 lessons](../lessons/2026-11-11_pitfalls.md)

---

## 8. 本文档的边界

- 不是逐字 transcript；
- 不复述所有工具输出；
- 对事实的最终判断以代码、测试、validation 文档、commit 为准；
- 如果发现本文与代码不一致，以代码 + 最新 PLAN 为准，并修正本文。
