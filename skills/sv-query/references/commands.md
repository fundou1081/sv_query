## 0. LLM 友好通用约定

**权威命令清单** (机器可读, 含 recommended / cost / kind / stability):
```bash
python3 run_cli.py capabilities --json -q
python3 run_cli.py capabilities --include-exp --json -q   # 追加 6 个 exp 命令
```

| Flag | Short | 作用 | 推荐 LLM 用法 |
|------|-------|------|---------------|
| `--json` | `-j` | stdout 输出 JSON | **永远**加 |
| `--pretty` | `-p` | JSON pretty-print | debug 时加 |
| `--quiet` | `-q` | 抑制所有 stderr 警告 (SWAP, INFO) | **永远**加 |
| `SVQ_QUIET=1` | (env) | 同 `--quiet` | 适合 CI |

### 三个必须知道的约束

1. **flag 放在子命令之后**: `run_cli.py trace fanin X -f F --json -q` ✅ / `run_cli.py trace --json fanin X` ❌ (Typer 报 unknown option)
2. **`--max-results/-N` 只有 `trace fanin` / `trace fanout` 支持**; `dataflow analyze` 用的是 `--max-paths/-n`; `search` 用 `--max-results/-n` (小写)。用错会直接报错。
3. **没有 `--summary` / `--strict` / `--no-strict`**: 这些 flag 已被移除 (旧版 cdc/risk 命令随之退役)。

### 标准 LLM 调用模板

```bash
# 查询 (小结果, 全量返回):
python3 run_cli.py trace fanout top.q -f sim/test_simple.sv --json -q

# 查询 (大结果, cap 100 + 检查 truncated):
python3 run_cli.py trace fanout clk -f sim/test_simple.sv --json -q --max-results 100
# 返回: result.loads = [...100 items], result.truncated = true/false

# 错误处理 (看 error_code 而非 error 字符串):
python3 run_cli.py trace fanin nonexistent -f sim/test_simple.sv --json -q
# 返回: {"ok": false, "error_code": "...", "error": "..."}
```

### JSON schema 资源

- 正式 schema: `tools/llm_schema.json` (Draft 2020-12)
- 验证脚本: `python3 tools/llm_schema_validate.py`
- schema 与代码的一致性由 `sim/tests/unit/test_schema_aligns_with_code.py` 守卫

---

# sv_query 命令速查 (39 core + 6 exp)

> 主入口: `cd <PROJ_DIR>/sv_query && python3 run_cli.py <command> [subcommand]`
> 每个命令都有 `--help`; 下表是实测过的常用 flag。

---

## 1. semantic — 语义事实 (24 个 core, agent 推理链主力)

### 1.1 drivers / loads (规范入口, 别名 trace fanin / trace fanout) ⭐

```bash
python3 run_cli.py drivers <signal> -f <file.sv>
python3 run_cli.py loads <signal> -f <file.sv>

# 等价别名 (兼容老路径):
python3 run_cli.py trace fanin <signal> -f <file.sv>
python3 run_cli.py trace fanout <signal> -f <file.sv>

# 常用 flag:
python3 run_cli.py trace fanin top.q -f top.sv --depth 3
python3 run_cli.py trace fanin top.q -f top.sv --max-results 50   # 仅 fanin/fanout
python3 run_cli.py trace fanout clk -f top.sv --include-clock --include-reset
```

返回 (JSON): `result.signals[]`, `result.total_count`, `result.total_pre_filter`, `result.truncated`, `result.failed_signals`

### 1.2 trace evidence (源码 evidence) ⭐

```bash
python3 run_cli.py trace evidence <signal> -f <file.sv>
python3 run_cli.py trace evidence <signal> -f <file.sv> --chain
python3 run_cli.py trace evidence <signal> -f <file.sv> --json --pretty
```

常用 flag: `--chain/-c`, `--tree/-T`, `--human/-H`, `--batch`, `--batch-file`, `--from-snapshot`, `--no-cache`

返回: `result.signals[].evidence` (含 `source_text` / `source_location` / `credibility_score`), 顶层另有 `evidence` 字段。
详见 [evidence.md](evidence.md)。

### 1.3 trace profile / lookup / manifest

```bash
python3 run_cli.py trace profile -f <file.sv>
python3 run_cli.py trace lookup --path top.u_inst.sig -f <file.sv>
python3 run_cli.py trace manifest --path top.u_inst.sig -f <file.sv>
```

lookup / manifest 都支持 `--path` (可重复) 和 `--paths-file`。

### 1.4 trace constraints 系列

```bash
python3 run_cli.py trace constraints <property> -f <file.sv>
python3 run_cli.py trace constraint-neighborhood <property> -f <file.sv>
python3 run_cli.py trace constraint-chain <source> <target> -f <file.sv>
```

constraint-neighborhood: `--max-depth` (默认 6), `--max-nodes` (默认 200)
constraint-chain: `--max-depth` (默认 6), `--max-nodes` (默认 200)

### 1.5 trace tb-join / frontier

```bash
python3 run_cli.py trace tb-join <field> --from-snapshot <tag> --filelist <tb.f>
python3 run_cli.py trace frontier <signal> -f <file.sv> --direction fanin --max-depth 8
```

frontier flag: `--direction/-d` (fanin|fanout|both, 默认 both), `--max-depth` (8), `--max-frontier` (50), `--max-visits`

### 1.6 trace covergroups / coverpoints / covergroup

```bash
python3 run_cli.py trace covergroups -f <file.sv>
python3 run_cli.py trace coverpoints <signal> -f <file.sv>
python3 run_cli.py trace covergroup <name> -f <file.sv> --rand
```

covergroup flag: `--coverpoint`, `--instance`, `--rand`; covergroups flag: `--class`

### 1.7 controlflow analyze / list-conditioned

```bash
python3 run_cli.py controlflow analyze <signal> -f <file.sv>
python3 run_cli.py controlflow analyze top.dout -f top.sv --evidence --json
python3 run_cli.py controlflow list-conditioned -f <file.sv>
```

返回: `result.conditioned_drivers[]` (每条含 `to_node` + `conditions[]`, condition 有 `expr` + `edge`)

### 1.8 dataflow analyze ⭐

```bash
python3 run_cli.py dataflow analyze <from> <to> -f <file.sv>
python3 run_cli.py dataflow analyze top.din top.dout -f top.sv --evidence --json
python3 run_cli.py dataflow analyze top.din top.dout -f top.sv --max-paths 20
```

**注意**: cap 用 `--max-paths/-n` (默认 100), **不是** `--max-results`。
其它 flag: `--max-expansions`, `--timeout`, `--bits`, `--human/-H`, `--tree/-T`, `--from-snapshot`

返回: `result.paths[]` (每条含 `segments[]`, segment 含 `evidence`), 以及 `is_reachable` / `truncated` / `truncation_reason` / `timing_risk`

### 1.9 scope / instances / connections / hierarchy / params / ports / paths / class

```bash
python3 run_cli.py scope <path> -f <file.sv>
python3 run_cli.py instances -f <file.sv> --module top --depth 3
python3 run_cli.py connections <target> -f <file.sv>
python3 run_cli.py hierarchy -f <file.sv>
python3 run_cli.py params <path> -f <file.sv>
python3 run_cli.py ports <module> -f <file.sv>
python3 run_cli.py paths <src> <dst> -f <file.sv> --all --max 50
python3 run_cli.py class -f <file.sv>
```

paths flag: `--all/-a`, `--canonical`, `--directed/-d`, `--evidence`, `--max/-n`, `--max-depth`, `--max-expansions`, `--timeout`, `--bits`
class flag: `--member`, `--relations`

---

## 2. verify — 客观检查, 结论可反驳 (3 个)

```bash
python3 run_cli.py verify consistency -f <file.sv>
python3 run_cli.py verify consistency -f <file.sv> --checks reciprocity,bit,connection
python3 run_cli.py verify consistency -f <file.sv> --signal top.data --full
python3 run_cli.py verify structural -f <file.sv> --checks symmetry
python3 run_cli.py verify claim --claim '{"signal": "top.data"}' -f <file.sv>
python3 run_cli.py verify claim --claim-file <claim.json> -f <file.sv>
```

- `verify consistency`: `--checks` (默认 reciprocity,bit,connection), `--signal/-s`, `--max-nodes` (200), `--full`, `--from-snapshot`
- `verify structural`: `--checks` (默认 symmetry), `--max-findings` (100)
- `verify claim`: `--claim` (JSON 字符串) 或 `--claim-file` (JSON 文件)

返回: `result.verified` / `result.total_violations` / `result.checks[]` (每项含 `check` + `status` + `findings`)

> 旧的 `verify gap` 已退役 —— 验证缺口用 `audit --checks verification_gaps` (见 §5)。

---

## 3. locate — 定位与统计 (7 个)

```bash
python3 run_cli.py stats -f <file.sv> --json -q
python3 run_cli.py stats -f <file.sv> --fanout-rank --top 20
python3 run_cli.py search "always_ff" -f <dir> --context 3 --ignore-case
python3 run_cli.py graph nodes -f <file.sv> --kind SIGNAL --detail
python3 run_cli.py graph edges -f <file.sv> --kind DRIVER --src top.a
python3 run_cli.py graph subgraph top.data -f <file.sv> --depth 2 --evidence
python3 run_cli.py filelist prune --filelist <big.f> --top top --output <pruned.f> --apply
```

- `stats`: `--file/-f`, `--filelist`, `--fanout-rank`, `--top/-n` (20), `--json/-j`, `--pretty/-p`
- `search`: `--file/-f` (必填, 文件或目录), `--context/-C` (2), `--regex/-E`, `--ignore-case/-i`, `--max-results/-n` (50), `--line-numbers/-l`
- `graph nodes`: `--kind/-k`, `--module/-m`, `--match`, `--detail`
- `graph edges`: `--kind/-k`, `--src/-s`, `--dst/-d`
- `graph subgraph`: `--depth` (2), `--direction` (in/out/both), `--edge-kinds`, `--max-nodes` (80), `--max-edges` (160), `--evidence`
- `filelist prune`: `--filelist` (必填), `--top` (必填), `--output/-o`, `--apply` (默认只预览), `--force`

---

## 4. scope 清单 + state 状态 (1 + 4)

```bash
python3 run_cli.py snapshot save <path> --tag v1.2.3 --git
python3 run_cli.py snapshot list
python3 run_cli.py snapshot compare <tag1> <tag2> --top 20 --show-edges
python3 run_cli.py snapshot delete <tag> --force
```

> **旧 `diff` 命令已退役** —— 版本对比用 `snapshot compare <tag1> <tag2>`。

---

## 5. exp 层 (6 个, 默认不在 capabilities 列出)

需要 `--include-exp` 才会出现在 `capabilities` 里, 但命令本身**可以直接调用**。

```bash
# 5.1 audit —— 设计审计 (CDC / 风险 / 验证缺口 / 覆盖率 / 协议 ...) ⭐
python3 run_cli.py audit -f <file.sv> --checks cdc,risk,verification_gaps --json -q
python3 run_cli.py audit -f <file.sv> --target top --json -q

# 5.2 diagnose —— 只读诊断 (imports / report / timescale / widths)
python3 run_cli.py diagnose imports --filelist <file.f>
# diagnose 的 check 是位置参数 (imports / report / timescale / widths), 文件走 --filelist (必填)

# 5.3 trace overview —— A→B 综合视图 (dataflow + controlflow + evidence)
python3 run_cli.py trace overview top.a top.b -f <file.sv> --json

# 5.4 review render —— 单个 structural finding 的局部 SVG/HTML
python3 run_cli.py review render <findings.json> --file <file.sv> --svg out.svg

# 5.5 architecture graph —— 模块/实例架构图
python3 run_cli.py architecture graph -f <file.sv> --module top --depth 3 --json
```

### 5.6 trace impact (exp, 默认隐藏)

```bash
python3 run_cli.py trace impact <signal> -f <file.sv>
python3 run_cli.py trace impact <signal> -f <file.sv> --min-risk 0.5
```

常用 flag: `--min-risk/-r`, `--human/-H`, `--tree/-T`, `--bits`, `--batch`


### audit 的 10 个检查项

`protocols`, `handshakes`, `backpressure_cycles`, `assertions`, `coverage`, `verification_gaps`, `risk`, `constraints`, `cdc`, `timing`

```bash
python3 run_cli.py audit -f <file.sv> --checks cdc --json -q
# {"target": null, "checks": ["cdc"], "sections": {"cdc": [...]}, "summary": {"checks": 1, "findings": N}}
```

每条 finding 形状 (cdc / risk / verification_gaps):
- cdc: `{signal, domains[], has_sync_hint, confidence}`
- risk: `{signal, role (clock/reset/data), loads, drivers, score}`
- verification_gaps: `{signal, role, loads, has_assertion, has_coverage}`

> **audit 替换了旧的 `cdc analyze` / `risk analyze` / `verify gap` / `sva` / `coverage` / `timing` 命令。**

---

## 6. 退出码 (实测)

| Code | 含义 |
|------|------|
| 0 | 成功 (含"信号找不到"这种**业务层空结果** —— 看 `ok` 字段, 不要只看退出码) |
| 1 | 文件不存在 / elaboration 失败 / parse error |
| 2 | 用法错误 (未知命令 / 未知 flag / 缺必填参数) |

---

## 7. error_code (15 种, stable)

`OK`, `E_INTERNAL`, `E_USAGE`, `E_FILE_NOT_FOUND`, `E_FILELIST_NOT_FOUND`,
`E_FILELIST_INCOMPLETE`, `E_FILELIST_INVALID`, `E_INVALID_INPUT`,
`E_ELABORATION_FAILED`, `E_PARSE_ERROR`, `E_TARGET_NOT_FOUND`,
`E_SIGNAL_NOT_FOUND`, `E_SIGNAL_AMBIGUOUS`, `E_NO_DATA`, `E_PARTIAL_RESULT`

权威定义: `src/cli/errors.py` 的 `ErrorCode` 枚举。

---

## 8. JSON envelope 形状 (实测, **不统一**)

大多数命令用标准 envelope:
```json
{"ok": true, "command": "trace_fanin", "params": {...}, "result": {...}, "errors": []}
```

但这些命令**不是**标准 envelope (别写代码硬套):

| 命令 | 顶层键 |
|------|--------|
| `audit` | `target`, `checks`, `sections`, `summary` |
| `paths` | `ok`, `src`, `dst`, `found`, `hop_count`, `path`, ... |
| `search` | `keyword`, `target`, `total_matches`, `file_count`, `files` |
| `ports` | `ok`, `module`, `count`, `by_direction`, `ports` |
| `instances` | `ok`, `count`, `module`, `instances` |
| `hierarchy` | `ok`, `root_count`, `instance_count`, `tree` |
| `connections` / `params` | `ok`, `error`, `target`/`path`, `resolved_as`, `hint` |
| `class` | `ok`, `count`, `classes` |
| `capabilities` | `schema_version`, `layers`, `core_groups`, `commands`, ... |

---

## 9. CoralNPU 分析案例 (已按真实命令更新)

```bash
cd <PROJ_DIR>/sv_query

# Step 1: 最小 subset 验证
cat > /tmp/coralnpu_two.f << 'EOF'
+incdir+<PROJ_DIR>/coralnpu/hdl/verilog
<PROJ_DIR>/coralnpu/hdl/verilog/ClockGate.sv
<PROJ_DIR>/coralnpu/hdl/verilog/RstSync.sv
EOF

python3 run_cli.py stats --filelist /tmp/coralnpu_two.f --json -q

# Step 2: trace 内部信号
python3 run_cli.py trace evidence rst_delay_reg --filelist /tmp/coralnpu_two.f --json -q

# Step 3: 找 rstn_o 怎么赋值
python3 run_cli.py trace fanin rstn_o --filelist /tmp/coralnpu_two.f --json -q

# Step 4: CDC check (用 audit, 不是旧的 cdc analyze)
python3 run_cli.py audit --filelist /tmp/coralnpu_two.f --checks cdc --json -q

# Step 5: 风险评分 (用 audit --checks risk)
python3 run_cli.py audit --filelist /tmp/coralnpu_two.f --checks risk --json -q
```

### 限制

- RvvCore.sv 包含 RISC-V Vector Ext 完整实现 (~3500 行), 需 RISC-V package 链
- 在 low-memory machine (<16GB) 上全 filelist (84 files) stats 跑 3+ 分钟, 可能 OOM
- 推荐: 渐进式 filelist (先 2 module, 再加 common cells, 最后全量)
