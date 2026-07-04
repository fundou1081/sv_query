# Experimental Features (实验性功能)

**Status**: Experimental. Not part of primary investment. Use with caution.

**Audience**: 探索性使用, 可能不准确 / flaky / 有 bug. **不承诺稳定**.

**Last updated**: 2026-07-04

---

## ⚠️ 实验性声明

以下 19 个命令/子命令**标记为实验性**:
- 不保证准确 (可能有 false positive / false negative)
- 不保证稳定 (可能 flaky)
- 不保证文档/测试完整
- **可能有 bug** (e.g. `verify gap` 之前在真项目报 traceback)
- **API 可能变**

**主推功能** (稳定, 重点投入): 见 `docs/PRIMARY_FEATURES.md`.

**使用建议**:
- ⛔ **不推荐** 依赖这些功能做 production 工作
- ⚠️ **可用** 但需要**自己 verify** 结果
- 🐛 **报告 bug** 但**不保证** 立即修
- 🚧 **欢迎** 贡献改进 (PR / 反馈)

---

## 📋 19 个实验性命令

### 🔴 真实验性 (高风险, 已知问题)

#### 1. `cdc analyze`
**问题**:
- 刚修算法 (2026-07-04), **没在真 CDC 项目验证过**
- CVA6 仍有 28 standard cell false positive
- 没处理真 CDC 项目 (e.g. axi_cdc + cdc_fifo_gray)

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

#### 3. `visualize dataflow / pipeline / gap / module`
**问题**:
- 单 module OK, **跨 module 边不可靠**
- namespace rewrite 偶有错
- CVA6 arch 0 port edges (跨 module 没连上)

**使用建议**:
- 单 module 画图 OK
- 跨 module 画图需手动 verify
- **别依赖** 跨 module 边

#### 4. `backpressure deadlock`
**问题**:
- 静态死锁检测, 算法不成熟
- 没测试覆盖, 不知道 false positive 率

**使用建议**:
- **不推荐** 依赖
- 只用 `backpressure analyze` (基本拓扑 OK)

#### 5. `coverage generate`
**问题**:
- 简单 case 准, 复杂 case 不确定
- 嵌套 coverpoint, cross coverage 可能生成不完整

**使用建议**:
- 简单 covergroup 用
- 复杂 covergroup 自己 review

#### 6. `timing analyze`
**问题**:
- basic critical path 算法 OK
- 大项目不测

**使用建议**:
- 小项目 OK
- 大项目自己 review

#### 7. `risk analyze`
**问题**:
- graph-based heuristic 评分
- 跟 "designer 觉得重要" 不完全一致

**使用建议**:
- 评分作**参考**, 不要照单全收

---

### 🟢 其他 13 个 (标记 experimental, 但相对稳定)

虽然相对稳定, 但**既然方豆决定"主推 dataflow + controlflow"**, 其他也标 experimental:

#### 8. `stats`
简单 count, 真. 但不主推.

#### 9. `search`
grep-like, 简单. 不主推.

#### 10. `arch show`
CVA6 跑出 10 instances 完美 6-stage, 真. 但不主推.

#### 11. `trace fanin / fanout / impact`
简单 graph BFS, 准. 但不主推.

#### 12. `protocol detect / show / list / semantics`
业界标准协议, 真. 但不主推.

#### 13. `handshake scan / analyze / pair`
ready/valid 检测, 真. 但不主推.

#### 14. `backpressure analyze`
ready/valid 拓扑, 真. (但 `deadlock` 标 experimental).

#### 15. `sva extract / coverage / timing`
sva extract 抽 id+kind+signals (不抽 body, 限制). coverage 是 SVA 覆盖分析.

#### 16. `snapshot save / list / show / delete / compare`
graph 快照, 简单. 不主推.

#### 17. `diff compare`
2 个版本对比, 简单. 不主推.

#### 18. `fix timescale / report / imports / widths`
elaboration 修, 真. 但**只对常见 error pattern**, edge case 不保证.

#### 19. `coverage suggest / gap`
自动 covergroup 建议. `suggest` 简单 OK, `gap` 不测.

---

## 📊 实验性分级

| 等级 | 数量 | 命令 | 严重度 |
|------|------|------|--------|
| 🔴 真实验 | **2** | `cdc`, `verify gap` | 高 (可能挂) |
| 🟡 部分实验 | **5** | `visualize`/`backpressure deadlock`/`coverage generate`/`timing`/`risk` | 中 (限制已知) |
| 🟢 标实验 (相对稳) | **12** | `stats`/`search`/`arch`/`trace`/`protocol`/`handshake`/`backpressure analyze`/`sva`/`snapshot`/`diff`/`fix`/`coverage suggest/gap` | 低 (真但**不主推**) |

---

## 🪞 真实评估

我之前**夸大了**所有功能"都好用", 给所有承诺稳定 + 重点投入. 实际:
- 之前 21 个都"主推", 用户用啥都承诺
- 方豆决定: **2 个主推 + 19 个实验性**
- 这策略**对** — 资源集中, 承诺明确
- 用户知道啥能用, 啥是探索

**真实情况**:
- 19 个里**真稳**的 12 个 (`stats`/`search`/`arch`/`trace`/`protocol`/`handshake`/`backpressure analyze`/`sva`/`snapshot`/`diff`/`fix`/`coverage suggest/gap`)
- 但既然方豆要**主推 dataflow + controlflow**, 这 12 个也**降级**到 experimental, 资源不投
- 6 个真不稳的 (cdc / verify gap / visualize / backpressure deadlock / coverage generate / timing / risk) 该修就修, 修完不升 stable

---

## 🎯 维护策略

### 不会修 (资源集中)
- 19 个实验性**不主动修**, 不主动测
- 只在用户**报告 bug** 时修
- 不承诺 SLA

### 会修
- **真 bug** (e.g. verify gap traceback) - 1 次修
- **flaky** - 1 次修
- **核心限制** (e.g. cdc standard cell FP) - 1 次修
- 修完仍标 experimental (除非方豆升 stable)

### 升级路径
如果某实验性功能**变得非常重要** (用户大量用), 方豆可决定:
- 升 stable (进入 PRIMARY_FEATURES)
- 加测试 + 文档 + 维护承诺

---

## 📚 相关 doc

- `docs/PRIMARY_FEATURES.md` - 重点加强的 2 个
- `docs/DATAFLOW_CONTROLFLOW_USAGE.md` - 完整 workflow
- `sim/tests/` - 测试覆盖 (主要功能有 2567+ tests, 实验性 0 承诺)

---

## 🪞 总结

**19 个命令标 experimental**:
- 2 个 🔴 真不稳 (`cdc`, `verify gap`)
- 5 个 🟡 部分不稳 (`visualize`/`backpressure deadlock`/`coverage generate`/`timing`/`risk`)
- 12 个 🟢 标实验但相对稳 (资源不投)

**2 个主推 (`dataflow` + `controlflow`)**:
- 13 tests + 7 真项目 100% 准
- 持续投入
- 承诺稳定
- 任何 bug 立即修

**资源分配**: 90% 给主推, 10% 给实验性 (bug fix).

这是**真战略** — 用户知道啥能用, 啥是探索.
