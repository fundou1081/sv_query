# P187 — CVA6 真实历史缺陷 value case 对照（2026-11-19）

> 基线：`6616b39d1d50793bf0e7f89106604a87c1552335`。本任务**只改本文档**（外加
> `agents/dev-deepseek/` 的 iteration/handoff）；未改 `src/` / CLI，未 commit/push。
> 数据源：只读 blobless 历史 clone `/tmp/p187-cva6-history`（8118 commits，`origin`
> = openhwgroup/cva6，promisor `[blob:none]`）。未改 `~/my_dv_proj/openrtl/cva6`。

## 0. 结论摘要（现状 → 问题 → 建议 → 代价）

- **现状**：选定 2 个真实 CVA6 fix，均只改 `core/cva6_mmu/cva6_mmu.sv`，parent/fix
  diff 已逐行核对；在**每个 commit 各自的历史依赖**上构建了最小可编译 filelist，
  4 个变体全部通过 sv_query 编译（10715 / 10715 / 10673 / 10676 节点）。
- **问题**：完整 `core/Flist.cva6` 不可行（生成文件 + 未拉取的 vendor submodule；
  全量 worktree checkout 因 promisor RPC/EOF 失败）。总线级查询漏掉位选缺陷。
- **建议**：把"驱动表达式 / 条件"作为 sv_query 对这类历史 bug 的主查询面；
  对位选赋值必须先 `graph nodes --match` 下钻到 bit-select 节点。
- **代价**：需一个**非历史**的 elaboration harness 提供 concrete top + 桩接口类型；
  动态仿真 oracle 未本地复现，本报告的 oracle 是上游 fix diff（+ case 1 的 issue
  描述中外部 Spike tandem reproducer，未本地重跑）。

## 1. 案例选择表（已自行核对 diff）

| # | fix commit | parent | 文件 / diff 规模 | 症状（来源） | oracle |
|---|---|---|---|---|---|
| C1 | `47b72e3193708e870d9e3f333de6e39b95b6e9bc` "fix: canonical address check to use registered LSU signals (#3410)" | `6fe7b95910343aa81d67eb07527b7590770464bc` | `core/cva6_mmu/cva6_mmu.sv`，2+/2- | issue #3404（2026-11-19 抓取）：Sv39 下 canonical check 采未寄存的 `lsu_req_i/lsu_vaddr_i`，而同块响应采 `_q`；紧随其后的非 canonical 访问 N+1 会让前一个合法访问 N 误报 LOAD/STORE_PAGE_FAULT，且 `tval` 指向 canonical 地址。pre-fix `tohost=13/15`，Spike tandem 通过；影响 v5.2.0/v5.3.0 | 上游 fix diff 为 oracle；issue 给出独立动态 oracle（Verilator+Spike 复现 patch），本任务未本地重跑 |
| C2 | `378ed3bcfc3f59fe3be544e9764b8720bd6f5704` "mmu: fix DTLB same-cycle PPN and indexing defect (#3347)" | `ed2efa51744387f510bfa4dcec29eb2e1f5697cf` | 同文件，10+/2- | commit message 明列两处缺陷：① `lsu_dtlb_ppn_o` 的 VA 位被拷到高 12 位的 PPN 槽（[33:24]）而非未移位槽；② same-cycle 地址生成被寄存信号 `dtlb_is_page_q` 门控而非 live `dtlb_is_page_n`，页大小切换时输出陈旧 | 上游 fix diff + commit message；未本地重跑动态复现 |

历史文件 blob 核对（`git rev-parse <commit>:<path>`）：

| 变体 | blob |
|---|---|
| C1 parent `cva6_mmu.sv` | `323030289e6dbcea7edefeeecbcd077cc1fc3d91` |
| C1 fix `cva6_mmu.sv` | `2a58aceedc0162c91989223bf614156320abcccf` |
| C2 parent `cva6_mmu.sv` | `595daaf8102a223ab0dee6d5e2a90b79b0863575` |
| C2 fix `cva6_mmu.sv` | `81917afbb1c819d801f535e0d691447afa60406e` |

## 2. 最小可编译 filelist（方法）

### 2.1 为什么不用完整 core/Flist.cva6

- `core/Flist.cva6` 依赖 `${CVA6_REPO_DIR}` / `${HPDCACHE_DIR}` / `${TARGET_CFG}`，
  并含 `core/include/cva6_config_pkg.sv`、`l15.tmp.h`（构建期生成，不在 git tree）、
  `core/cvfpu`、`vendor/pulp-platform/{axi,common_cells}`、`core/cache_subsystem/hpdcache`
  等 submodule。blobless clone 中这些 submodule 目录为空。
- 全量 worktree checkout 实测失败（后台运行 ~2 min）：
  `error: RPC failed; curl 18 transfer closed ... fatal: could not fetch <blob> from promisor remote`，
  `RC=128`，`/tmp/p187-parent` 未生成。失败后 `git worktree prune` 确认历史 clone 无残留注册。
- 因此按任务允许回退到**模块级最小 filelist**：用 `git show <commit>:<path>` 逐 blob
  抽取该 commit 自身的真实历史文件（**不使用生成 RTL、不伪造历史源码**）。

### 2.2 每个 case 的 pinned 依赖（均取自该 case 的 parent commit）

- C1 取自 `6fe7b959`，C2 取自 `ed2efa51`（两 commit 的 `config_pkg.sv` /
  `riscv_pkg.sv` / 配置包 / `build_config_pkg.sv` / `cva6_ptw.sv` blob 确实不同，故分别抽取）。
- `config_pkg.sv`、`cv64a6_imafdc_sv39_config_pkg.sv`（定义 `package cva6_config_pkg`）、
  `riscv_pkg.sv`、`ariane_pkg.sv`、`dummy_l15_pkg.sv`、`build_config_pkg.sv`、
  `cf_math_pkg.sv`；RTL：`cva6_mmu.sv`、`cva6_tlb.sv`、`cva6_shared_tlb.sv`、
  `cva6_ptw.sv`、`lzc.sv`、`lfsr.sv`、`pmp.sv`、`pmp_entry.sv`。
- `l15.tmp.h` 只在 `` `ifdef PITON_ARIANE `` 下被 include，未定义该宏 → 不需要。

### 2.3 非历史 elaboration harness

`p187_mmu_top.sv` 只是为了让 pyslang 有 concrete top；桩接口的**字段名逐字取自该
历史 `cva6_mmu.sv` 的使用点**，宽度取真实 `cv64a6_imafdc_sv39` 配置。它不是 CVA6
RTL，也不冒充历史产物。注意 CVA6 命名错位：输入口 `icache_areq_i` 的类型是
`icache_arsp_t`，输出口 `icache_areq_o` 的类型是 `icache_areq_t`（按原源码如实建模）。

```systemverilog
module p187_mmu_top;
  import config_pkg::*;
  import cva6_config_pkg::*;
  localparam cva6_cfg_t CVA6Cfg = build_config_pkg::build_config(cva6_cfg);

  typedef struct packed {
    logic valid; logic [CVA6Cfg.XLEN-1:0] cause; logic [CVA6Cfg.XLEN-1:0] tval;
    logic [CVA6Cfg.GPLEN-1:0] tval2; logic [31:0] tinst; logic gva;
  } p187_exception_t;
  typedef struct packed { logic fetch_req; logic [CVA6Cfg.VLEN-1:0] fetch_vaddr; } p187_icache_arsp_t;
  typedef struct packed { logic fetch_valid; p187_exception_t fetch_exception;
                          logic [CVA6Cfg.PLEN-1:0] fetch_paddr; } p187_icache_areq_t;
  typedef struct packed {
    logic data_req, data_we, kill_req, tag_valid; logic [2:0] cbo_op; logic [3:0] data_id;
    logic [CVA6Cfg.DCACHE_INDEX_WIDTH-1:0] address_index;
    logic [CVA6Cfg.DCACHE_TAG_WIDTH-1:0]   address_tag;
    logic [3:0] data_be; logic [2:0] data_size;
    logic [CVA6Cfg.XLEN-1:0] data_wdata, data_wuser;
  } p187_dcache_req_i_t;
  typedef struct packed { logic data_gnt, data_rvalid; logic [CVA6Cfg.XLEN-1:0] data_rdata; } p187_dcache_req_o_t;

  logic clk_i, rst_ni, lsu_req_i;
  logic [CVA6Cfg.VLEN-1:0] lsu_vaddr_i;
  cva6_mmu #(.CVA6Cfg(CVA6Cfg), .exception_t(p187_exception_t),
             .icache_areq_t(p187_icache_areq_t), .icache_arsp_t(p187_icache_arsp_t),
             .icache_dreq_t(logic), .icache_drsp_t(logic),
             .dcache_req_i_t(p187_dcache_req_i_t), .dcache_req_o_t(p187_dcache_req_o_t))
  u_mmu (.clk_i(clk_i), .rst_ni(rst_ni), .lsu_req_i(lsu_req_i), .lsu_vaddr_i(lsu_vaddr_i));
endmodule
```

### 2.4 编译结果（`stats --filelist ... --json`，单次 wall clock，本机）

| 变体 | filelist | ok | nodes | edges | 耗时 |
|---|---|---|---|---|---|
| C1 parent | `/tmp/p187-min/fl_parent.f` | true | 10715 | 15408 | 20.98 s |
| C1 fix | `/tmp/p187-min/fl_fix.f` | true | 10715 | 15408 | 20.79 s |
| C2 parent | `/tmp/p187-case2/fl_parent.f` | true | 10673 | 15335 | 20.65 s |
| C2 fix | `/tmp/p187-case2/fl_fix.f` | true | 10676 | 15338 | 20.73 s |

C1 的 diff 只改表达式文本 → 图规模不变；C2 新增 `MegaPageSubstWidth` 位选节点 → +3 nodes/edges。

## 3. Case C1 — canonical address check 的周期错位

**fix diff（parent 542-543 行）**

```diff
-    canonical_addr_check = (lsu_req_i && en_ld_st_translation_i &&
-           !((&lsu_vaddr_i[CVA6Cfg.VLEN-1:CVA6Cfg.SV-1]) == 1'b1 || (|lsu_vaddr_i[CVA6Cfg.VLEN-1:CVA6Cfg.SV-1]) == 1'b0));
+    canonical_addr_check = (lsu_req_q && en_ld_st_translation_i &&
+           !((&lsu_vaddr_q[CVA6Cfg.VLEN-1:CVA6Cfg.SV-1]) == 1'b1 || (|lsu_vaddr_q[CVA6Cfg.VLEN-1:CVA6Cfg.SV-1]) == 1'b0));
```

**手工 grep（buggy parent，0.024 s）**

```bash
grep -n 'canonical_addr_check' /tmp/p187-min/cva6_mmu_parent.sv
grep -nE 'lsu_req_[qi]|lsu_vaddr_[qi]' /tmp/p187-min/cva6_mmu_parent.sv | head -30
```

输出要点：`canonical_addr_check` 在 542 行由 `lsu_req_i`/`lsu_vaddr_i` 产生；527-528 行
才把 `_i` 寄存成 `_n`，535/592/623 行的响应逻辑使用 `_q`。**grep 能并列看到 `_i` 与
`_q`，但不会把它们组织成"检查信号与消费它的响应块处于不同流水级"**。

**wrong conclusion（若不追语义）**：布尔式本身是正确的 canonical 判别（issue 亦确认
"The check itself is correct"），grep 只读到这一行时容易得出"canonical 检查无问题 /
与 daccess_err 同域"的错误结论；无法回答"哪一个访问会误 fault、`tval` 指向谁"。

**sv_query（parent vs fix）**

```bash
python3 run_cli.py drivers p187_mmu_top.u_mmu.canonical_addr_check \
  --filelist /tmp/p187-min/fl_parent.f --json --evidence    # 0.92 s (cache hit)
python3 run_cli.py drivers p187_mmu_top.u_mmu.canonical_addr_check \
  --filelist /tmp/p187-min/fl_fix.f    --json --evidence    # 23.29 s
```

| 查询 | buggy parent | fix | 对照 fix diff |
|---|---|---|---|
| `drivers ... --evidence` 的 driver expression | `(lsu_req_i && en_ld_st_translation_i && !((&lsu_vaddr_i[...]) == 1'b1 \|\| (\|lsu_vaddr_i[...]) == 1'b0))` | `(lsu_req_q && en_ld_st_translation_i && !((&lsu_vaddr_q[...]) == 1'b1 \|\| (\|lsu_vaddr_q[...]) == 1'b0))` | **精确命中**：`_i → _q`，两处信号都命中 |
| `trace profile`（resolution/driver_count/load_count） | `exact/3/0` | `exact/3/0` | 不区分（结构性元数据相同） |
| `dataflow analyze lsu_vaddr_i → canonical_addr_check` | `is_reachable=false, complete, 0 paths` | 同左 | **未命中**（见 §6 限制） |

**判定**：C1 是 sv_query 的真实命中案例 —— 无需读整个 always 块，`drivers --evidence`
一行即暴露 fix diff 要改的两个信号；手工 grep 也能看到文本，但缺少"该表达式驱动哪个
信号、被哪个响应块消费"的语义绑定。

## 4. Case C2 — DTLB same-cycle PPN / 页大小门控

**fix diff（parent 567/571/574-575 行 → fix 570/575-576/580/584-585 行）**

```diff
+  localparam int unsigned MegaPageSubstWidth = PPNWMin - (CVA6Cfg.VpnLen / CVA6Cfg.PtLevels) - 8 - CVA6Cfg.PtLevels;  // Sv39 => 9
   // (q 门控的 lsu_paddr_o 位选赋值保持不动)
-        lsu_dtlb_ppn_o[PPNWMin-(CVA6Cfg.VpnLen/CVA6Cfg.PtLevels):9+CVA6Cfg.PtLevels] = lsu_vaddr_n[PPNWMin-(CVA6Cfg.VpnLen/CVA6Cfg.PtLevels):9+CVA6Cfg.PtLevels];
+      if (CVA6Cfg.PtLevels == 3 && dtlb_is_page_n[CVA6Cfg.PtLevels-2]) begin
+        lsu_dtlb_ppn_o[0+:MegaPageSubstWidth] = lsu_vaddr_n[(9+CVA6Cfg.PtLevels)+:MegaPageSubstWidth];
+      end
       if (dtlb_is_page_q[0]) begin
-        lsu_dtlb_ppn_o[PPNWMin:12] = lsu_vaddr_n[PPNWMin:12];
         lsu_paddr_o[PPNWMin:12] = lsu_vaddr_q[PPNWMin:12];
       end
+      if (dtlb_is_page_n[0]) begin
+        lsu_dtlb_ppn_o[PPNWMin-12:0] = lsu_vaddr_n[PPNWMin:12];
+      end
```

**手工 grep（buggy parent，0.022 s）**

```bash
grep -nE 'lsu_dtlb_ppn_o|dtlb_is_page_[qn]' /tmp/p187-case2/cva6_mmu_parent.sv | head -50
```

输出含 555/561 的两个基础赋值、567/571 的 q 门控高位 PPN 拷贝、574/575 的 q
门控 `[PPNWMin:12]` 拷贝，以及 767 行的 `dtlb_is_page_q <= dtlb_is_page_n`。

**wrong conclusion**：grep 能看到 `_q` 门控和一条奇怪的位选 `[PPNWMin-(VpnLen/PtLevels):9+PtLevels]`，
但单靠文本无法判定①这段位选相对正确 PPN 槽偏了 12 位、②`q` 是寄存值而 `n` 才是
same-cycle live 值（需要把它和 526 行 `dtlb_is_page_n = dtlb_is_page`、767 行寄存
联系起来）。总线级阅读极易只记住"PPN 来自 dtlb_content.ppn 或 vaddr_n，看起来合理"。

**sv_query — 总线级查询为负（诚实记录）**

`drivers`/`controlflow analyze`/`dataflow analyze` 直接查 `p187_mmu_top.u_mmu.lsu_dtlb_ppn_o`：
parent 与 fix 都只返回 3 个基础 driver（`lsu_vaddr_n[55:12]`、两个 content.ppn），
条件只有 `en_ld_st_translation_i || en_ld_st_g_translation_i && !misaligned_ex_q.valid`；
**两处缺陷在该粒度完全不可见**（耗时 20.9–22.5 s/次）。原因：位选被建模成独立节点。

**sv_query — 下钻到位选节点后命中**

```bash
# 1) 发现位选节点（先对 parent 与 fix 各跑一次）
python3 run_cli.py graph nodes --filelist /tmp/p187-case2/fl_parent.f \
  --match lsu_dtlb_ppn_o --json
python3 run_cli.py graph nodes --filelist /tmp/p187-case2/fl_fix.f \
  --match lsu_dtlb_ppn_o --json
# parent: [PPNWMin - CVA6Cfg.VpnLen / CVA6Cfg.PtLevels:9 + CVA6Cfg.PtLevels], [PPNWMin:12]
# fix   : [0:MegaPageSubstWidth], [PPNWMin - 12:0]

# 2) 驱动表达式 + 条件证据（每个节点 ~0.6-0.8 s cache hit / ~20 s 重建）
python3 run_cli.py drivers '<bit-node>' --filelist <fl> --json --evidence
python3 run_cli.py controlflow analyze '<bit-node>' --filelist <fl> --json --evidence
```

| 位点 | buggy parent | fix | 对照 fix diff |
|---|---|---|---|
| 高位 PPN 拷贝节点名 | `lsu_dtlb_ppn_o[PPNWMin - CVA6Cfg.VpnLen / CVA6Cfg.PtLevels:9 + CVA6Cfg.PtLevels]` | `lsu_dtlb_ppn_o[0:MegaPageSubstWidth]` | **命中**节点/位段被整体替换 |
| 该节点 driver expr | `lsu_vaddr_n[PPNWMin-(CVA6Cfg.VpnLen/CVA6Cfg.PtLevels):9+CVA6Cfg.PtLevels]` → `lsu_vaddr_n[32'd20:32'd12]` | `lsu_vaddr_n[(9+CVA6Cfg.PtLevels)+:MegaPageSubstWidth]` | **命中** |
| 该节点条件（含 evidence 行） | `... && CVA6Cfg.PtLevels == 3 && dtlb_is_page_q[CVA6Cfg.PtLevels - 2]`，`cva6_mmu_parent.sv:568` `if (...dtlb_is_page_q...)` | `... && dtlb_is_page_n[CVA6Cfg.PtLevels - 2]`，`cva6_mmu_fix.sv:575` | **命中** q→n |
| 低位 PPN 拷贝节点名 | `lsu_dtlb_ppn_o[PPNWMin:12]` | `lsu_dtlb_ppn_o[PPNWMin - 12:0]` | **命中**索引下移 12 |
| 该节点 driver expr | `lsu_vaddr_n[PPNWMin:12]` → `lsu_vaddr_n[29:12]` | `lsu_vaddr_n[PPNWMin:12]` → `lsu_vaddr_n[29:12]` | 表达式相同，差异在目标位段（上一行） |
| 该节点条件（含 evidence 行） | `... && dtlb_is_page_q[0]`，`cva6_mmu_parent.sv:575` `if (dtlb_is_page_q[0]) begin` | `... && dtlb_is_page_n[0]`，`cva6_mmu_fix.sv:584` | **命中** q→n |

**判定**：C2 是"**分层命中**"案例 —— 总线级查询漏报，位选级查询精确复现 fix diff
的位段和 `q→n` 门控；且 `controlflow analyze --evidence` 给出源文件行号与 `if`
原文，形成可核对的证据链。

## 5. grep vs sv_query 汇总

| case | 手工 grep（耗时 / 结论） | sv_query（耗时 / 结论） | 命中 oracle？ |
|---|---|---|---|
| C1 | 0.024 s；看到 `_i` 与 `_q` 并列，但无法绑定"检查 vs 响应块"流水级；易误判布尔式正确即无 bug | `drivers --evidence`：24 s 冷 / 0.9 s 热；直接给出 driver 表达式，parent `_i` vs fix `_q`，与 fix diff 逐 token 一致 | **是**（驱动表达式） |
| C2 | 0.022 s；看到 q 门控和怪异位选，但无法确定 12-bit 偏移与 q/n 时序语义 | 总线级 20–23 s **漏报**；`graph nodes --match` + 位选级 `drivers`/`controlflow --evidence` 0.6 s 热 / ~20 s 冷：节点位段 + 条件 `dtlb_is_page_q → _n` + 源码行号全部复现 fix diff | **是，但需下钻位选** |

诚实口径：这两例不是"盲测"—— case 是先按 fix diff 选的，查询目标信号由 diff 决定；
因此本文证明的是 **sv_query 对已知信号级缺陷的验证/定位能力**，不是"自动发现任意历史 bug"的命中率。

## 6. 限制与未验证项（不可外推）

1. **未做完整 CVA6 编译**：只用模块级最小 filelist + 非历史 harness（桩类型）；
   跨模块集成效应、宏/生成配置差异未覆盖。完整 `Flist.cva6` 的缺失依赖是生成文件
   `cva6_config_pkg.sv`/`l15.tmp.h` 与未拉取的 vendor submodule（见 §2.1）。
2. **dataflow 总线级负结果**：C1 的 `lsu_vaddr_i → canonical_addr_check`、C2 的
   `lsu_vaddr_n → lsu_dtlb_ppn_o` 均返回 `is_reachable=false, complete, 0 paths`，
   尽管 driver 边确实存在（位选节点建模使总线端点不直接可达）。需要 `--bits` 或
   位选节点 ID 才能形成路径；本任务未进一步验证该路径查询的正确性。
3. **`trace evidence` 在 live graph 模式对 `canonical_addr_check` 返回空 `source_text`
   （`is_verified=false`）**；有效证据来自 `drivers --evidence` 的 edge expression
   与 `controlflow analyze --evidence` 的 condition evidence。按契约不把空 evidence
   写成 verified。
4. **C2 动态 oracle 未本地复现**：oracle 是上游 fix diff 与 commit message；未运行
   Verilator/Spike DV。C1 的 issue 中有外部 tandem reproducer（pre-fix tohost=13/15、
   post-fix 全过），本次只抓取描述、未在本地重跑。故"修复后功能正确"是**未验证**声明。
5. **耗时是单次墙钟**：同一 filelist+完全相同命令第二次约 0.5–0.9 s（cache hit）；
   换命令/选项约 20–23 s（重建图）。不同机器/缓存状态不可直接比较。
6. **不新增公开 claim**：未改 `CLAIMS.md`；本文结论标 `unverified`（无 gate）。

## 7. 复现命令（从零重建，约 30 s 抽取）

```bash
H=/tmp/p187-cva6-history
# C1 parent/fix
git -C $H show 6fe7b959:core/cva6_mmu/cva6_mmu.sv > /tmp/p187-min/cva6_mmu_parent.sv
git -C $H show 47b72e31:core/cva6_mmu/cva6_mmu.sv > /tmp/p187-min/cva6_mmu_fix1.sv
# C2 parent/fix (其依赖 pin 在 ed2efa51)
git -C $H show ed2efa51:core/cva6_mmu/cva6_mmu.sv > /tmp/p187-case2/cva6_mmu_parent.sv
git -C $H show 378ed3bc:core/cva6_mmu/cva6_mmu.sv > /tmp/p187-case2/cva6_mmu_fix.sv
# 其余依赖文件见 §2.2（每个文件用 git show <parent>:<path> 抽取）
cd .
python3 run_cli.py stats --filelist /tmp/p187-min/fl_parent.f --json
python3 run_cli.py drivers p187_mmu_top.u_mmu.canonical_addr_check \
  --filelist /tmp/p187-min/fl_parent.f --json --evidence
python3 run_cli.py drivers p187_mmu_top.u_mmu.canonical_addr_check \
  --filelist /tmp/p187-min/fl_fix.f --json --evidence
python3 run_cli.py graph nodes --filelist /tmp/p187-case2/fl_parent.f \
  --match lsu_dtlb_ppn_o --json
python3 run_cli.py controlflow analyze \
  'p187_mmu_top.u_mmu.lsu_dtlb_ppn_o[PPNWMin:12]' \
  --filelist /tmp/p187-case2/fl_parent.f --json --evidence
python3 run_cli.py controlflow analyze \
  'p187_mmu_top.u_mmu.lsu_dtlb_ppn_o[PPNWMin - 12:0]' \
  --filelist /tmp/p187-case2/fl_fix.f --json --evidence
```

原始 JSON/耗时记录：`/tmp/p187-results/{summary,bit_summary,stats_times}.json` 及
同目录 `c1_*__*.json` / `c2_*__*.json`（`/tmp` 临时，非仓库产物）。

## 8. 变更范围

- 新增：本文件。
- 新增：`agents/dev-deepseek/iterations/iter_039_P187.md`、
  `agents/dev-deepseek/handoff/P187_handoff.md`。
- 未改：`src/`、`src/cli/`、`PLAN.md`、`CURRENT_TODO.md`、`CLAIMS.md`、外部仓库；
  无 commit / push。


## 9. Main-session verification (2026-11-19)

- Re-ran C1 `drivers --evidence`: parent expression contains `lsu_req_i`/`lsu_vaddr_i`; fix contains `_q`.
- Re-ran C2 `graph nodes --match lsu_dtlb_ppn_o`: parent bit nodes include
  `[PPNWMin:12]` and the shifted `[PPNWMin - ...:...]`; fix exposes `[0:MegaPageSubstWidth]`.
- `check_docs`/`check_plan` green; no src/CLI changes; no commit/push.
