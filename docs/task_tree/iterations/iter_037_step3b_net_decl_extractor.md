# Iteration 037: #1 Step 3b — 拆 _create_net_decl_edges 到 net_decl_extractor

**Metadata**:
- **Iteration #**: 037
- **Task Tree Level**: L2
- **Parent Task**: ARCHITECTURE_TODOLIST #1 (拆 driver_extractor 4101 行 → 10 个文件)
- **Created**: 2026-08-28 15:20 GMT+8
- **Author**: 方豆 / DSH Agent
- **Outcome**: ✅ **成功** — 0 回归, 两条代码路径实测 byte-identical

---

## 🎯 本次目标

用户指令: **"先提交，再开 3b"** → 提交 #2 (`a45827b`) 后开始 Step 3b。

拆出 `driver_extractor._create_net_decl_edges` (line 905-1014, 110 行):
处理 `wire X = expr;` 形式的 net 声明, 为 RHS 每个真实信号建 DRIVER 边。

---

## 📊 当前状态 / 预期结果

**开工时记录的估计** (来自 `wire_init_extractor.py` 头部注释 + todolist):
> 依赖 7 个 driver_extractor 内部 helper, 工程量 **1+ 天**

**预期**: 按此估计, 需要先把 7 个 helper 提到 `_common`, 再搬主函数。

---

## 🔬 实际结果

### 先探索: 依赖链实测比记录的更复杂, 但耦合更浅

直接依赖 **6 个** helper (记录说 7 个), 传递闭包 **12 个 / 563 行**:

| helper | 行数 | 实例状态耦合 |
|---|---|---|
| `_build_signal_source` | 89 | — 无 |
| `_filter_compile_time_signal_names` | 99 | — 无 |
| `_detect_binary_op` | 76 | `self._signal_visitor` |
| `_store_expr_tree` | 71 | — 无 |
| `_append_edge` | 51 | `self._edge_factory` |
| `_detect_casts` | 51 | — 无 |
| `_parse_bit_range` / `_detect_inner_ops` / `_get_readable_expr` | 29/29/27 | — 无 |
| `_get_all_real_signals` | 16 | `self._signal_visitor` |
| `_get_signal` | 13 | 已是薄壳 (Step 3 已迁 `_common`) |
| `_ensure_signal_node` | 12 | — 无 |

**8/12 已可纯函数化, 仅 3 个碰实例状态, 且各只 1 处调用点。**

### 🔑 关键决策: 不搬 helper, 改依赖注入

进一步实测这些 helper 在 `driver_extractor.py` 内的**调用点数**:

```
_get_signal            35 处
_store_expr_tree        7 处
_build_signal_source    6 处
_append_edge            6 处
_get_all_real_signals   5 处
_ensure_signal_node     4 处
```

→ **它们是全文件共享的基础设施**, 服务于 assign / always / function 等
**Step 4-7 尚未拆分**的部分。把它们搬进 `_common` 会波及那些区域,
属于跨 Step 的大改动, **不在 Step 3b 范围内**。

**改用 Step 1+2 (`alias_extractor`) 已验证的模式**: helper 以 `Callable`
参数注入, 定义留在 `driver_extractor`。Step 3b 只搬"业务逻辑", 不动共享基础设施。

**因此实际工程量约 0.5 小时, 而非记录里的 1+ 天** — 卡住前一轮的不是代码复杂度,
而是"必须先搬 helper"这个错误前提。

### 顺手消除的重复

原函数是**两段近乎逐行重复**的循环 (顶层 net decl / generate-for 展开的 net decl),
边发射逻辑完全相同, 只有 `lhs_id` 构造方式不同。抽出 `_emit_driver_edges()`
消除重复 — 110 行 → 主函数 ~95 行 + 共用发射器 ~40 行, 且逻辑只剩一份。

### 产出

- 新增 `src/trace/core/extractors/net_decl_extractor.py` (207 行, 含契约注释)
- `driver_extractor.py`: **3836 → 3754 行** (净减 82 行)
- `_create_net_decl_edges` 改为 28 行薄壳 (保留签名, 调用方零改动)

---

## 📈 验证 (git worktree A/B 对照, 基线 = `a45827b`)

### 回归: 全套 0 新增失败

| 测试套 | 基线 `a45827b` | Step 3b 后 | 结论 |
|---|---|---|---|
| `integration` | 13 failed | **13 failed** | ✅ 0 回归 |
| `cli` | 20 failed | **20 failed** | ✅ 0 回归 |
| `unit` | 13 failed | **4 failed** | ✅ 0 回归 (见下) |
| `test_case27_1to1_truth` | — | **4 passed** | ✅ 全绿 |

`unit` 从 13 降到 4: 实测 4 个失败**全部**报 `Operation not permitted`
(AI 沙箱不可写 `~/.svq/cache`)。此前的 13 个包含 9 个 cache 争用导致的
**波动性失败**, 非真实回归 — 属我执行环境的噪声, 与本次改动无关。

### 🔑 行为等价性: 两条路径实测 byte-identical

不止依赖测试通过, 另写探针直接对比图输出:

**路径 1 (顶层 net decl)** — `wire sum = a + b; wire mix = sum ^ b;`
```
('top.a','top.sum','continuous','a + b')
('top.b','top.mix','continuous','sum ^ b')
('top.b','top.sum','continuous','a + b')
('top.sum','top.mix','continuous','sum ^ b')
```

**路径 2 (generate-for 展开)** — `for(i) begin: gen_accum wire prod = data * weights[i]; end`
```
('top.data','top.gen_accum[0].prod','continuous','data * weights[i]')
('top.data','top.gen_accum[1].prod','continuous','data * weights[i]')
('top.data','top.gen_accum[2].prod','continuous','data * weights[i]')
('top.weights','top.gen_accum[0..2].prod', ...)
```

在 `a45827b` worktree 与当前工作区分别跑同一探针, `diff` **完全一致**。
特别确认了 Plan G3 注释警告的关键行为仍在: 3 个 entry 的 `prod` 是
**3 个独立节点** (`gen_accum[N].prod`), 没有被 merge 成一个。

---

## 💡 关键发现 / 关键技术 / 决策

### 发现 1: 前一轮的"1+ 天"估计基于一个错误前提

`wire_init_extractor.py` 头部注释写 "依赖 7 个 helper, 工程量 1+ 天, 留到 Step 3b"。
实际卡点不是代码难度, 而是默认了"**必须先把 helper 提到 `_common`**"。
但 Step 1+2 早已建立依赖注入模式 (`alias_extractor` 接 `ensure_signal_node` /
`append_edge` 两个 Callable) —— 沿用它, 0.5 小时即可完成。

**教训**: 遗留的工作量估计要重新验证, 尤其当它附带"必须先做 X"的隐含前提时。

### 发现 2: 共享 helper 该留在原处, 不该跟着业务逻辑走

判断标准是**调用点分布**: `_get_signal` 有 35 处调用、横跨 assign/always/function,
它是基础设施而非 net-decl 的私有工具。跟着搬会把 Step 4-7 的代码也牵动。

这与 `#2` 的判断同源: 拆分依据是**职责**, 不是"这个函数用到了它"。

### 发现 3: 测试通过 ≠ 行为等价

integration/cli 全绿只说明"没测出差异", 不等于"逐边一致"。
额外写探针做 A/B byte-level 对比, 才真正验证了 110 行搬迁没有语义漂移 ——
尤其 generate-for 的 node id 构造 (`hierarchical_path` vs fallback) 是历史 bug 高发区
(Plan G3 曾因此把 4 个 prod merge 成 1 个)。

---

## 📌 下一步

Step 3b 完成, #1 进度 **9 步完成 4 步**。

下一步 **Step 4: 拆 assign_extractor** (估 1 天) — 涉及 `_create_assign_edges`
+ 4 个 sub-method (`_handle_concat_assign` / `_handle_call_assign` / ...),
可继续沿用本次的依赖注入模式。
