## 0. LLM 友好通用 flags

**所有命令** 都支持下面这些 flag (除少数不适用):

| Flag | Short | 作用 | 推荐 LLM 用法 |
|------|-------|------|---------------|
| `--json` | `-j` | stdout 输出合法 JSON | **永远**加 |
| `--pretty` | `-p` | JSON pretty-print (方便人读) | debug 时加 |
| `--quiet` | `-q` | 抑制所有 stderr 警告 (SWAP, INFO) | **永远**加 |
| `SVQ_QUIET=1` | (env) | 同 --quiet, 适合脚本 | 适合 CI |
| `--strict`/`--no-strict` | | 严格模式 (默认 strict, elaboration 失败立即报错) | 默认就行 |

### 标准 LLM 调用模板

```bash
# 查询 (小结果, 全量返回):
python3 run_cli.py trace fanout top.q --json -q

# 查询 (大结果, cap 100 + 优先看是否 truncated):
python3 run_cli.py trace fanout clk --json -q --max-results 100
# 返回: result.loads = [...100 items], result.truncated = true/false

# CDC/risk (大结果, 只要 summary):
python3 run_cli.py cdc analyze --json -q --summary
# 返回: counts + domains, 没有 paths (省 token)

# 错误处理 (看 error_code 而非 error 字符串):
python3 run_cli.py trace fanin nonexistent --json -q
# 返回: {"ok": false, "error_code": "E_FILE_NOT_FOUND", "error": "..."}
```

### JSON schema 资源

- 正式 schema: `tools/llm_schema.json` (Draft 2020-12)
- 验证脚本: `python3 tools/llm_schema_validate.py`

---

# sv_query 命令速查

> 主入口: `cd <PROJ_DIR>/sv_query && python3 run_cli.py <command> [subcommand]`
> 跑 `--help` 看完整 options

---

## 1. trace — 信号追踪

### 1.1 fanin (找驱动)
```bash
python3 run_cli.py trace fanin <signal> -f <file.sv>
# 默认 depth=10
python3 run_cli.py trace fanin top.q -f top.sv --depth 3

# [C1 2026-06-28] cap 结果数 (LLM 上下文安全)
python3 run_cli.py trace fanin top.q -f top.sv --max-results 50
# 返回字段: result.drivers + result.truncated (bool) + result.total_count (int)
```

### 1.2 fanout (找读取)
```bash
python3 run_cli.py trace fanout <signal> -f <file.sv>

# [C1 2026-06-28] cap 结果数
python3 run_cli.py trace fanout clk -f top.sv --max-results 100
# 返回字段: result.loads + result.truncated + result.total_count
```

### 1.3 impact (改信号影响谁)
```bash
python3 run_cli.py trace impact <signal> -f <file.sv>
```

### 1.4 evidence (源码 evidence) ⭐
```bash
# 1 行文本
python3 run_cli.py trace evidence <signal> -f <file.sv>

# 整条 driver chain
python3 run_cli.py trace evidence <signal> -f <file.sv> --chain

# JSON (agent 必用)
python3 run_cli.py trace evidence <signal> -f <file.sv> --json --pretty
```

返回结构 (JSON):
```json
{
  "ok": true,
  "signal": "top.q",
  "evidence": {
    "source_text": "q <= d;",
    "source_range": [42, 47],
    "block_kind": "always_ff",
    "credibility_score": 0.95,
    "block_start_line": 38
  }
}
```

---

## 2. dataflow — 数据流分析

```bash
# 单条路径
python3 run_cli.py dataflow analyze <from> <to> -f <file.sv>

# 多条
python3 run_cli.py dataflow analyze top.din top.dout -f top.sv

# 加 evidence
python3 run_cli.py dataflow analyze top.din top.dout -f top.sv --evidence --json
```

返回 paths[].segments[].evidence

---

## 3. controlflow — 控制流分析

```bash
# 找信号被驱动时的条件
python3 run_cli.py controlflow analyze <signal> -f <file.sv>
python3 run_cli.py controlflow analyze top.dout -f top.sv --evidence --json
```

返回 conditioned_drivers[].conditions[].evidence (if/case 路径)

---

## 4. cdc — 时钟域交叉

```bash
python3 run_cli.py cdc analyze -f <file.sv>
python3 run_cli.py cdc analyze -f top.sv --evidence --json
# 返回 paths[].source_evidence + target_evidence

# [C2 2026-06-28] summary 模式 (LLM 上下文紧时)
python3 run_cli.py cdc analyze -f top.sv --summary --json -q
# 只返回 counts + domains, 不返回 paths (省 token)
```

输出 (JSON):
- 完整: result.paths (可能几百条), result.domains, result.domain_pairs, ...
- summary: result.domains, result.total_cdc, result.high_risk, result.low_risk, summary=True

检测:
- 跨 clk 的 `always_ff` 赋值
- async reset 路径
- 灰色码同步器

---

## 5. risk — 风险评分

```bash
python3 run_cli.py risk analyze -f <file.sv>
python3 run_cli.py risk analyze -f top.sv --evidence --json
# 4 类: clock / reset / data / unknown

# [C2 2026-06-28] summary 模式 (LLM 上下文紧时)
python3 run_cli.py risk analyze -f top.sv --summary --json -q
# 只返回 top-10 高风险信号 + counts
```

输出 (JSON):
- 完整: result.data_signals (可能几百个) + clocks + resets + summary
- summary: result.top_risks (前 10), result.clocks_count, result.resets_count, summary_mode=True

风险分公式: `risk = (1 - has_sva) × fanin_depth × unconstrained_factor`

---

## 6. sva — SVA 提取

```bash
# 提取所有 SVA 属性
python3 run_cli.py sva extract -f <file.sv>

# 检查覆盖率
python3 run_cli.py sva cover -f <file.sv>

# 找缺口
python3 run_cli.py verify gap -f <file.sv> --evidence
```

---

## 7. verify — 验证缺口

```bash
# 找高风险但没 SVA 的信号
python3 run_cli.py verify gap -f <file.sv>
python3 run_cli.py verify gap -f top.sv --evidence --json

# 双向 cross-check
python3 run_cli.py verify cross -f top.sv
```

---

## 8. timing — 时序分析

```bash
# 关键路径 (DAG longest path)
python3 run_cli.py timing critical -f <file.sv>

# 寄存器深度
python3 run_cli.py timing depth -f <file.sv>

# SCC 检测 (组合环)
python3 run_cli.py timing scc -f <file.sv>
```

---

## 9. coverage — 覆盖率生成

```bash
# 把复合信号拆成 atomic
python3 run_cli.py coverage decompose -f <file.sv>

# 生成 covergroup 模板
python3 run_cli.py coverage template -f <file.sv>
```

---

## 10. visualize — 可视化

```bash
# Graphviz DOT
python3 run_cli.py visualize graph -f <file.sv> --dot out.dot
dot -Tsvg out.dot -o out.svg

# Mermaid
python3 run_cli.py visualize graph -f <file.sv> --mermaid out.md

# HTML
python3 run_cli.py visualize graph -f <file.sv> --html out.html
```

---

## 11. diff / snapshot — 版本对比

```bash
# 建 snapshot
python3 run_cli.py snapshot save <name> -f <file.sv>

# 对比
python3 run_cli.py diff <name1> <name2>

# 列 snapshot
python3 run_cli.py snapshot list
```

---

## 12. search — 全文搜索

```bash
# grep-like, 但跨 .sv/.v 范围 + 上下文
python3 run_cli.py search "always_ff" -d <dir>
```

---

## 13. stats — 图统计

```bash
python3 run_cli.py stats -f <file.sv>
# 输出节点数、边数、模块数、信号数
```

---

## 全局 flag

| Flag | 说明 |
|------|------|
| `--file / -f` | 单个 .sv 文件 (常用) |
| `--filelist / -fl` | Verilator 风格 filelist |
| `--json / -j` | JSON 输出 (agent 必用) |
| `--pretty / -p` | 缩进 JSON |
| `--evidence / -e` | 在每条结果贴源码 evidence (text 1 行 / JSON 完整字段) |
| `--human / -H` | 人类友好箭头输出 (6 命令: trace fanin/fanout/impact, dataflow, controlflow, cdc) |
| `--depth N` | trace fanin/fanout 深度 (默认 10) |
| `--help` | 命令帮助 |

## --human 输出示例 (Stage 6 part 3)

当用户问"给我看个图"或"人话解释"时, 加 `--human` 给箭头式输出:

```bash
# trace fanin:  反向链 (源头到信号)
python3 run_cli.py trace fanin -f top.sv top.dout --human
#   Fanin of top.dout
#     1'b0 → top.din → top.data → top.dout

# trace fanout: 正向链 (信号到叶)
python3 run_cli.py trace fanout -f top.sv top.din --human
#   Fanout of top.din
#     top.din → top.data → top.dout

# dataflow:    路径 + 条件 + evidence
python3 run_cli.py dataflow analyze -f top.sv top.din top.dout --human
#   DataFlow: top.din → top.dout
#     paths: 1
#     Path 0:
#       top.din → top.data → [when !!rst_n && en] top.dout

# controlflow: 条件 + 驱动
python3 run_cli.py controlflow analyze -f top.sv top.dout --human
#   ControlFlow: top.dout
#     when !rst_n: top.clk → top.dout
#     when !!rst_n && en: top.data → top.dout

# cdc:         跨时钟域 + 同步器状态
python3 run_cli.py cdc analyze -f cdc.sv --human
#   CDC Paths:
#     clk_a: top.reg_a → top.dout_b  [NO SYNC] [HIGH]
```

**不破坏**: 不加 --human 时输出跟以前完全一样, --json 也照常工作。

## 退出码

| Code | 含义 |
|------|------|
| 0 | 成功 |
| 1 | 通用错误 |
| 2 | 参数错误 / 文件不存在 |
| 3 | SV 解析错误 |
| 4 | 信号找不到 |
| 5 | 配置错误 |

---

## 14. CoralNPU 分析案例

### 完整跑一遍 (验证 skill 工作流)

```bash
cd <PROJ_DIR>/sv_query

# Step 1: 最小 subset 验证
cat > /tmp/coralnpu_two.f << 'EOF'
+incdir+<PROJ_DIR>/coralnpu/hdl/verilog
<PROJ_DIR>/coralnpu/hdl/verilog/ClockGate.sv
<PROJ_DIR>/coralnpu/hdl/verilog/RstSync.sv
EOF

python3 run_cli.py stats --filelist /tmp/coralnpu_two.f --json -q
# → 19 nodes, 23 edges, 0 errors ✅

# Step 2: trace 内部信号 (RstSync.rst_delay_reg 是内部 REG)
python3 run_cli.py trace evidence rst_delay_reg --filelist /tmp/coralnpu_two.f --json -q
# → credibility_score=1.0 (always_ff 内赋值, 最可信)

# Step 3: 找 RstSync 内 rstn_o 怎么赋值
python3 run_cli.py trace fanin rstn_o --filelist /tmp/coralnpu_two.f --json -q
# → drivers: [rst_delay_reg] (assign rstn_o = rst_delay_reg[RST_DELAY-1])

# Step 4: CDC check (单 module 内通常无 CDC, 但测试)
python3 run_cli.py cdc analyze --filelist /tmp/coralnpu_two.f --summary --json -q
# → 0 跨域 (单 clk)

# Step 5: 风险评分
python3 run_cli.py risk analyze --filelist /tmp/coralnpu_two.f --summary --json -q
# → top_risks (前 10), counts
```

### 关键发现

- ClockGate + RstSync 是 **210 行内**的纯 SV 模块, 没有 cross-module 依赖
- RstSync 用 4-FF 同步器 + 时钟门控 (ASIC-style reset)
- ClockGate 用 latched-and-or 实现 clock gating
- 单文件 filelist (2 modules) elaboration 完全干净, 证明 sv_query 工具链正常

### 限制

- RvvCore.sv 包含 RISC-V Vector Ext 完整实现 (~3500 行), 需 RISC-V package 链
- 在 low-memory machine (<16GB) 上全 filelist (84 files) stats 跑 3+ 分钟, 可能 OOM
- 推荐: 用 [progressive filelist strategy](../SKILL.md#实际项目分析工作流-coralnpu-案例-2026-06-28) 分层
