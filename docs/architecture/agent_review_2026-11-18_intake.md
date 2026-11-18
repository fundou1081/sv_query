# Agent-facing review intake (2026-11-18)

**状态**: 已分诊；采纳项已登记 PLAN  
**来源**: 外部锐评（测试/README/CLI 面/图模型/社区/价值验证）  
**原则**: 只采纳当前可复现的事实；旧快照数据不作为行动计划。

---

## 1. 事实核对

| 锐评说法 | 当前事实 | 判定 |
|---|---|---|
| 2958 tests / 97.1% / ~86 failures | canonical **3012 passed / 0 failed**；123 是 opensource deferred，不是失败 | **过期** |
| README 仍宣传 visualize/cdc/timing/sva/risk | README 已标注 2026-11-03 退役；USER_GUIDE §8 明确不做 | **已修** |
| 27 个 CLI 命令 | 当前 **45** 注册命令（39 core + 6 exp）；27 更接近 standard envelope 数 | **过期** |
| 核心 ~39K 行 | 当前 src ~50.8K 行 / 145 文件 | **过期** |
| CI / CONTRIBUTING 缺失 | 两者均存在 | **过期** |
| 影子节点占 30~38% | KNOWN_LIMITATIONS §3.3 登记，真实 | **成立** |
| diagnose timescale 形同虚设 | KNOWN_LIMITATIONS §3.2 登记，真实 | **成立** |
| 命令面仍偏大 | 45 命令；T2/P4 未收完 | **成立** |
| 单作者 / Issues 0 / PyPI 缺失 / issue 模板缺失 | 基本成立 | **部分成立** |
| 价值闭环未标定 | trace impact 仍是 heuristic；无真实 bug 对比案例 | **成立** |

## 2. 采纳与不采纳

### 采纳

| PLAN | 内容 | 来源 |
|---|---|---|
| **P185** | CLI command-surface subtraction：收完 T2/P4、别名/默认可见面目标 | 锐评 P2 + 既有 L1 |
| **P186** | shadow-node graph cleanup：先测量，再决定 definition namespace / drop_shadows | 锐评 P6 |
| **P187** | value case studies：真实历史 bug 的 grep vs sv_query 对比 | 锐评 P5 |
| **P188** | packaging/community：PyPI、issue/PR 模板、CI badge | 锐评 P3 |
| **P189** | docs surface consistency gate：README/USER_GUIDE 命令表 vs capabilities | 锐评 P0 的可执行部分 |
| **P190** | diagnose timescale 触发条件调查（known limitation） | 锐评 P4 |

### 不采纳

- **不以“86 个失败测试”为 P0**：当前 canonical 0 failed，问题不存在；
- **不把 CLI 压到 10 条**：语义不同的 core 命令不应合并；目标仍按 L1 的 ~52/默认可见 ~33 评估；
- **不现在就做全量 README 重写**：当前 README 已对齐退役命令；用 P189 的 gate 防再漂移；
- **不把 shadow cleanup 插队到 P185/P182.1 前面**：先测量，再决定方案。

## 3. 顺序

```text
P185.1（当前）收完 T2 同族合并
  -> P185.2/P185.3 域内合并 + 默认可见面/别名目标
  -> P182.1 envelope inventory/gate（命令面稳定后再做）
  -> P186 shadow-node 测量/方案
  -> P187/P188/P189/P190 按需
```

P184 ASTFrontend Phase 0 保持 `<待做>`，不与命令面削减争抢当前迭代。
