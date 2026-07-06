# sv_query CLI 命令速查 (Cheatsheet)
#
# Generated 2026-07-06 from `sv_query --help` + `sv_query <cmd> --help`
# 21 top-level commands, 50 subcommands

用法: `sv_query <command> [subcommand] [OPTIONS]`

══════════════════════════════════════════════════════════════════════

## 顶层命令总览

  stats         Show graph statistics
  search        Grep-like keyword search across .sv/.v files
  trace         Trace signal drivers (fanin), loads (fanout), or impact
  diff          Compare two versions of SystemVerilog code
  snapshot      Snapshot management for graph diff
  dataflow      Analyze dataflow paths between signals
  controlflow   Analyze control flow conditions for signals
  risk          [EXPERIMENTAL] Signal risk analysis: classify nodes by
  sva           SVA (SystemVerilog Assertions) analysis: extract properties,
  timing        [EXPERIMENTAL] Timing critical path analysis: register depth,
  cdc           [EXPERIMENTAL] CDC (Clock Domain Crossing) detection: identify
  coverage      [EXPERIMENTAL] Control coverage generation: decompose signals
  verify        [EXPERIMENTAL] Verification gap detection: find high-risk
  backpressure  Bus backpressure topology analysis: AXI/TL-UL ready/valid
  handshake     Bus handshake semantic analysis: AXI/TL-UL ready/valid
  protocol      Bus protocol detection (Phase A)
  visualize     Signal graph visualization: DOT, Mermaid, HTML with data flow
  arch          Project architecture visualization (L1 + L2 overview)
  fix           自动修复 elaboration 问题 (MissingTimeScale 等)
  expression    Build expression nodes
  graph         Inspect signal graph

──────────────────────────────────────────────────────────────────────
## ⟨1⟩ 核心统计 / 检索

  * `sv_query stats`
    显示 graph statistics (single)
  * `sv_query search KEYWORD -f FILE`
    grep-like 文本搜索 (single)
  * `sv_query diff compare FILE FILE`
    两版代码 graph diff

──────────────────────────────────────────────────────────────────────
## ⟨2⟩ 快照管理

  * `sv_query snapshot save PATH --tag T --filelist F`
    保存当前代码 state 为 snapshot
  * `sv_query snapshot list`
    列所有 snapshot
  * `sv_query snapshot show TAG`
    显示 snapshot 详情
  * `sv_query snapshot compare TAG1 TAG2`
    对比两 snapshot
  * `sv_query snapshot delete TAG [--force]`
    删除 snapshot

──────────────────────────────────────────────────────────────────────
## ⟨3⟩ 信号 trace / 影响力

  * `sv_query trace fanin --file F SIGNAL`
    追溯源头 drivers
  * `sv_query trace fanout --file F SIGNAL`
    追溯下游 loads
  * `sv_query trace impact --file F SIGNAL`
    影响范围 (downstream reach)
  * `sv_query trace evidence --file F SIGNAL`
    显示 always/if 源码 (50+ fields)

──────────────────────────────────────────────────────────────────────
## ⟨4⟩ 数据流 / 控制流 / 时序

  * `sv_query dataflow analyze --file F FROM TO`
    从 FROM 信号到 TO 信号的连接路径
  * `sv_query controlflow analyze --file F SIGNAL`
    信号控制条件 (if/case 树)
  * `sv_query controlflow list-conditioned --file F`
    列出条件化信号 (有 if/case 控制)
  * `sv_query controlflow conditions --file F SIGNAL`
    信号的条件细节
  * `sv_query timing analyze --file F [--max-paths N]`
    关键路径分析 (寄存器深度, DAG longest path, SCC)

──────────────────────────────────────────────────────────────────────
## ⟨5⟩ 总线协议 (AXI/TL-UL) — Phase A/B/C

  * `sv_query protocol detect --file F`
    协议识别 (Phase A)
  * `sv_query protocol show PROTOCOL [AXI4|TL-UL|...]`
    显示 protocol schema
  * `sv_query protocol list`
    列支持的协议
  * `sv_query protocol semantics PROTOCOL`
    显示 protocol 语义规则 (供 deadlock)
  * `sv_query backpressure analyze --file F`
    反压链路 (Phase B-Mermaid)
  * `sv_query backpressure deadlock --file F [--protocol AXI4|TL-UL]`
    静态死锁候选检测 (Phase C)
  * `sv_query handshake scan --file F [--channel AW|W|...]`
    ready/valid 配对扫描 + 分类
  * `sv_query handshake analyze --file F [--signal S]`
    单 signal 握手语义
  * `sv_query handshake pair --file F --ready R [--valid V]`
    ready/valid 配对分析 (短名自动 resolve)

──────────────────────────────────────────────────────────────────────
## ⟨6⟩ 验证 / 风险 / 覆盖率

  * `sv_query cdc analyze --file F`
    时钟域跨域检测 (Clock Domain Crossing)
  * `sv_query sva extract --file F`
    提取 SVA properties/assertions
  * `sv_query sva coverage --file F`
    SVA 覆盖率分析
  * `sv_query sva timing --file F`
    SVA 时序分析
  * `sv_query risk analyze --file F [--summary]`
    信号风险评分 (clock/reset/data 分类 + 风险分)
  * `sv_query verify gap --file F`
    验证缺口 (高风险但无 SVA/Coverage 的信号)
  * `sv_query coverage suggest --file F --signal S [--max-signals N]`
    控制覆盖率分解 (列原子信号 + 控制块)
  * `sv_query coverage gap --file F`
    覆盖率缺口检测 (现有 covergroup 漏掉什么)
  * `sv_query coverage generate --file F -s SIGNAL [--related R]`
    自动生成 covergroup .sv (sample 条件 + bins + cross)

──────────────────────────────────────────────────────────────────────
## ⟨7⟩ 可视化

  * `sv_query visualize graph --file F`
    DOT graph (单视图)
  * `sv_query visualize dataflow --file F`
    数据流 + Mermaid (.mmd + .dot)
  * `sv_query visualize pipeline --file F`
    时序管道 (寄存器串联链) 图
  * `sv_query visualize gap --file F`
    覆盖率缺口图
  * `sv_query visualize module --file F`
    module 结构图
  * `sv_query arch show --file F --depth N [--format mermaid|dot|html]`
    项目架构视图 (L1 modules + L2 sub-modules)

──────────────────────────────────────────────────────────────────────
## ⟨8⟩ 自动修复 / 工具

  * `sv_query fix timescale --filelist F`
    MissingTimeScale 检测 + 修复
  * `sv_query fix report --filelist F`
    所有 diagnostic 报告
  * `sv_query fix imports --filelist F`
    缺模块 → 推荐补 filelist
  * `sv_query fix widths --filelist F`
    typedef $clog2 真实位宽分析
  * `sv_query expression build --operands O -e EXPR -r RESULT`
    构造 expression node (e.g. a + b)
  * `sv_query expression func --name N --args A,B -r RESULT`
    构造 function call node
  * `sv_query expression cond --cond C --true T --false F -r RESULT`
    构造 ternary conditional node
  * `sv_query graph dump --file F [--json]`
    graph 整图 JSON dump (含 TraceNode extra metadata)
  * `sv_query graph nodes --file F`
    列所有节点 ([KIND] id)
  * `sv_query graph edges --file F`
    列所有边 (src → dst kind)
  * `sv_query graph find --file F PATTERN`
    按名字模式搜索节点 (substring match)

──────────────────────────────────────────────────────────────────────
## 通用模式

  * `-f FILE`: 单文件模式 (--file 是 top.sv)
  * `--filelist LIST`: 多文件项目模式 (LIST 是 .f/.fl)
  * `-I PATH1,PATH2`: include 目录 (comma-separated)
  * `--strict` / `--no-strict`: elaboration error 行为 (默认 strict)
  * `--json -j`: JSON 输出 (programmatic)
  * `--pretty -p`: pretty-print JSON
  * `--summary -S`: summary only (counts + domains, no paths)
  * `--no-strict`: elaboration fail 仍存部分 graph

──────────────────────────────────────────────────────────────────────
## 今日 (2026-07-06) 修的命令

  🆕 新启用 2 顶层:
     * expression  3 sub (build/func/cond)
     * graph       4 sub (dump/nodes/edges/find)

  🔧 真 bug 修了 6 个:
     * handshake.analyze  调用 scan.callback typo → AttributeError
     * handshake.pair     短 signal 名 (e.g. mem_axi_bready) auto-resolve
     * snapshot.show      用 manager.get_snapshot (旧 API) → AttributeError
     * snapshot.delete    用 manager.delete_snapshot (旧 API) → AttributeError
     * coverage.suggest   truncation 时 stderr 完全空 (现在报 ❌ 错误)

  📍 Commits (origin/main):
     * 0b489d0: 启用 expression + TraceNode metadata kwargs
     * cee3757: 修 expression with-file dead-code + 启用 graph + TraceNode attr bug
     * e2ade20: handshake analyze `scan.callback` typo + pair 短名 resolve
     * a1a91b5: snapshot 4 subcommand API mismatch
     * 8103e3f: coverage suggest truncation stderr 错信息

──────────────────────────────────────────────────────────────────────
## Quick Examples

# picorv32.v (9133行 RISC-V) 是常用 fixture
sv_query trace fanin picorv32.cpuregs -f /Users/fundou/my_dv_proj/picorv32/picorv32.v

# OpenTitan filelist 模式
sv_query cdc analyze --filelist sim/tests/pyslang_type_fixtures/industrial_filelists/openTitan_prim_max_tree.f

# 输出 covergroup .sv
sv_query coverage generate -f top.sv -s data_o --related mode_i --related valid_i -o cg_data.sv

# Trace 反压拓扑 (Mermaid 图)
sv_query backpressure analyze -f axi_adapter.sv --output bp.mmd

# 找所有 cpu 相关 signals
sv_query graph find cpu -f picorv32.v

──────────────────────────────────────────────────────────────────────
## 测试统计

  * 21/21 顶层 commands enabled ✅
  * 48/50 subcommands 直接跑 picorv32.v PASS ✅
  * 0 真 bug 残留 ✅
  * 130 cli tests pass, 0 regression ✅
  * 唯一 'fail' 是 user 传太小 --max-signals 触发的 truncation (预期 + stderr 错信息)
