# Experimental Features (实验性功能)

**Status**: Experimental. Not part of primary investment. Use with caution.

**Audience**: 探索性使用, 可能不准确 / flaky / 有 bug. **不承诺稳定**.

**Last updated**: 2026-07-04 (3-层切分 v2)

---

## ⚠️ 实验性声明

以下 **6 个**命令/子命令**标记为实验性** (在 `sv_query --help` 可见 `[EXPERIMENTAL]` tag):

- ⛔ **不保证** 准确 (可能有 false positive / false negative)
- ⛔ **不保证** 稳定 (可能 flaky)
- ⛔ **不保证** 文档/测试完整
- ⛔ **可能有 bug** (e.g. `verify gap` 之前在真项目报 traceback)
- ⛔ **API 可能变**

**主推功能** (稳定, 重点投入): 见 `docs/PRIMARY_FEATURES.md` — **3 个** (`dataflow` + `controlflow` + `visualize`)
**稳定功能** (真能用, 不主推): 12 个 — 不在本 doc

**使用建议**:
- ⛔ **不推荐** 依赖这些功能做 production 工作
- ⚠️ **可用** 但需要**自己 verify** 结果
- 🐛 **报告 bug** 但**不保证** 立即修
- 🚧 **欢迎** 贡献改进 (PR / 反馈)

---

## 📋 6 个实验性命令

### 🔴 真实验性 (高风险, 已知问题)

#### 1. `cdc analyze`
**问题**:
- 刚修算法 (2026-07-04), **没在真 CDC 项目验证过**
- CVA6 仍有 28 standard cell false positive
- 没处理真 CDC 项目 (e.g. axi_cdc + cdc_fifo_gray)
- 5 cdc tests 都用**单 clk 项目** (0 CDC, 不是真验证)

**命令**:
```bash
sv_query -q cdc analyze --no-strict --file x.sv
```

**使用建议**:
- 单 clk 项目 OK (但返 0 CDC, 没价值)
- 多 clk 项目: 结果**不可信**, 需自己 verify
- **不推荐** 依赖 cdc 找 bug

#### 2. `verify gap`
**问题**:
- 之前在真项目 (axi_cdc_src) 上**直接报 traceback**
- pyslang 报 37 errors 后, gap detector 访问 None 报 JSONDecodeError
- 修没修不确定

**命令**:
```bash
sv_query -q verify gap --no-strict --file x.sv
```

**使用建议**:
- **很可能直接挂** (Python traceback)
- 不要在 CI 用
- 手工改前先单独跑一次试试

---

### 🟡 部分实验 (中等风险, 限制已知)

#### 3. `risk analyze`
**问题**:
- graph-based heuristic 评分
- 跟 "designer 觉得重要" 不完全一致
- 评分是**辅助**, 不是 ground truth

**使用建议**:
- 评分作**参考**, 不要照单全收
- 跟 verify gap / hand 评估结合

#### 5. `timing analyze`
**问题**:
- basic critical path 算法 OK
- 大项目不测, 不知道 pressure

**使用建议**:
- 小项目 OK
- 大项目自己 review

#### 6. `coverage generate`
**问题**:
- 简单 case 准, 复杂 case 不确定
- 嵌套 coverpoint, cross coverage 可能生成不完整

**使用建议**:
- 简单 covergroup 用
- 复杂 covergroup 自己 review

#### 7. `backpressure deadlock` (子命令)
**问题**:
- 静态死锁检测, 算法不成熟
- 没测试覆盖, 不知道 false positive 率

**使用建议**:
- **不推荐** 依赖
- 只用 `backpressure analyze` (基本拓扑 OK)

---

## 📊 实验性分级

| 等级 | 数量 | 命令 | 严重度 |
|------|------|------|--------|
| 🔴 真实验 | **2** | `cdc`, `verify gap` | 高 (可能挂) |
| 🟡 部分实验 | **4** | `risk` / `timing` / `coverage generate` / `backpressure deadlock` | 中 (限制已知) |
| 🟢 标实验 (相对稳) | **0** | (无) | - |

> **v3 (2026-07-04) 升级**: `visualize` 整体升 primary (3 子命令真稳 graph/dataflow/pipeline). 2 子命令 (gap/module) 修完 stable. 现在 6 个实验性 (从 7 减 1).

---

## 🟢 不在本 doc (因为相对稳)

下面 12 个命令**相对稳**, **不** 标 [EXPERIMENTAL]:

| 命令 | 用途 | 状态 |
|------|------|------|
| `stats` | 简单 count | 真稳 |
| `search` | grep-like | 真稳 |
| `arch show` | L1+L2 模块图 | 真稳 (CVA6 跑过) |
| `trace fanin/fanout/impact` | 信号追踪 | 真稳 |
| `trace evidence` | 拿源码 | 真稳 (1 秒) |
| `protocol detect/show/list/semantics` | AXI/AHB/APB | 真稳 |
| `handshake scan/analyze/pair` | ready/valid | 真稳 |
| `backpressure analyze` | ready/valid 拓扑 | 真稳 |
| `sva extract/coverage/timing` | SVA 抽 + 覆盖 | 真稳 |
| `snapshot save/list/show/delete/compare` | graph 快照 | 真稳 |
| `diff compare` | 2 版本对比 | 真稳 |
| `fix timescale/report/imports/widths` | elaboration 修 | 真稳 |

**承诺**: 真稳可用, 但**不主推, 资源不投** (主推给 dataflow + controlflow). 偶尔修 bug.

---

## 🎯 维护策略

### 不会修 (资源集中)
- 7 个实验性**不主动修**, 不主动测
- 只在用户**报告 bug** 时修
- 不承诺 SLA

### 会修
- **真 bug** (e.g. verify gap traceback) - 1 次修
- **flaky** - 1 次修
- **核心限制** (e.g. cdc standard cell FP) - 1 次修
- 修完仍标 experimental (除非方豆升 stable)

### 升级路径
如果某实验性功能**变得非常重要** (用户大量用), 方豆可决定:
- 升 stable (进入"稳定功能"列表)
- 加测试 + 文档 + 维护承诺

---

## 📚 相关 doc

- `docs/PRIMARY_FEATURES.md` - 重点加强的 2 个 (dataflow + controlflow)
- `docs/DATAFLOW_CONTROLFLOW_USAGE.md` - 完整 workflow
- `sim/tests/` - 测试覆盖 (主推功能有 13+ tests, 实验性 0 承诺)

---

## 🪞 总结

**7 个命令标 experimental** (v2 升级):
- 2 个 🔴 真不稳 (`cdc`, `verify gap`)
- 5 个 🟡 部分不稳 (`visualize` / `risk` / `timing` / `coverage generate` / `backpressure deadlock`)

**2 个主推** (`dataflow` + `controlflow`):
- 13 tests + 7 真项目 100% 准
- 持续投入
- 承诺稳定
- 任何 bug 立即修

**12 个稳定** (不标 experimental):
- 真稳可用
- 不主推, 资源不投
- 偶尔修 bug

**资源分配**: 90% 给主推, 10% 给实验性 (bug fix).
