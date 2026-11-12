# sv_query Evidence 机制详解

> **核心 feature**: 把 RTL 静态分析结果跟原始 SystemVerilog 源码精确对齐, 不靠 LLM 猜。

---

## 1. 什么是 evidence

当 sv_query 分析信号 X 的来源/驱动/CDC 路径时, 不只返回"X 被 Y 驱动", 还返回:

- **source_text**: 信号被赋值的那一行源码
- **source_location**: `{file, line_start, line_end, column}` 精确位置
- **enclosing_always / enclosing_if / enclosing_assign / ...**: 嵌套上下文的完整源码
- **enclosing_chain**: 嵌套链 (从最内到最外)
- **is_verified**: 是否已机器验证
- **credibility_score**: 来源可信度 (0-1)

evidence 是 **sv_query 直接读 SV 源文件** 提取, 不是 LLM 生成的 (重要!)

---

## 2. credibility_score 含义

**分数是算出来的, 不是手工打的分** (实现见 `src/trace/core/trace_evidence.py` 的
`credibility_score` property), 由 4 项相加后取 `min(1.0, ...)`:

| 加分项 | 值 | 条件 |
|--------|-----|------|
| snippet_present | +0.2 | 找到 enclosing 源码块 (always / always_comb / if / assign / class / constraint 任一) |
| matches_source_expr | +0.4 | 源表达式匹配上 |
| matches_signal_name | +0.2 | 信号名匹配上 |
| 交叉验证 | +0.2 | 上面两项**同时**成立 |

所以**实际只可能出现 {0.0, 0.2, 0.4, 0.6, 0.8, 1.0}** 这 6 个值 —— 没有 0.9 / 0.7 这种中间值。

| 分数 | 含义 | agent 处理 |
|------|------|-----------|
| `1.0` | snippet + expr 匹配 + name 匹配 + 交叉验证 | **直接采用** |
| `0.8` | snippet + expr 匹配 + name 匹配 (无交叉验证) | 采用 + 标 line_start/line_end |
| `0.6` | snippet + expr 匹配 | 采用 + 标"间接" |
| `0.4` | snippet + name 匹配 | 采用 + 标 module 边界 |
| `0.2` | 只有 snippet | **报告用户让他选** |
| `0.0` | 没有任何 enclosing 块 (如 input 端口, 没被赋值) | **必须标"需人工确认"** |

实测参考 (`sim/test_simple.sv`):
- `top.data` / `top.dout` (有赋值) → `1.0`, `is_verified=true`
- `top.clk` / `top.rst_n` (input 端口, 无赋值) → `0.0`, `is_verified=false`

---

## 3. evidence 在各命令里的形态

> 下表命令都是**现存的**。旧的 `verify gap` / `risk analyze` / `cdc analyze` 已退役,
> 对应能力改由 `audit --checks ...` 提供 (audit 不返回 evidence 字段)。

### 3.1 trace evidence

```bash
python3 run_cli.py trace evidence top.q -f top.sv --json
```

text 输出:
```
Signal: top.q
============================================================
Source: 'q <= d;'
============================================================
```

JSON 输出 (agent 必用, **实际结构**):
```json
{
  "ok": true,
  "signal": "top.q",
  "evidence": {
    "signal": "top.q",
    "source_location": {
      "file": "top.sv",
      "line_start": 42,
      "line_end": 47,
      "column": 5
    },
    "source_text": "q <= d;",
    "enclosing_always": {
      "file": "top.sv",
      "line_start": 38,
      "line_end": 47,
      "column": 5,
      "text": "always_ff @(posedge clk) begin\n    if (...) begin\n        q <= d;\n    end\nend"
    },
    "enclosing_if": null,
    "enclosing_assign": null,
    "enclosing_chain": [...],
    "is_verified": true,
    "credibility_score": 0.95
  }
}
```

### 3.2 验证缺口 (audit --checks verification_gaps)

> 旧的 `verify gap` 命令已退役 (iter_263)。验证缺口现在由 `audit` 提供。

```bash
python3 run_cli.py audit -f top.sv --checks verification_gaps --json -q
```

```json
{
  "target": null,
  "checks": ["verification_gaps"],
  "sections": {
    "verification_gaps": [
      {
        "signal": "top.rst_n",
        "role": "reset",
        "loads": 2,
        "has_assertion": false,
        "has_coverage": false
      }
    ]
  },
  "summary": {"checks": 1, "findings": 1}
}
```

注意: `audit` 的返回**没有**标准信封 (没有 `ok` / `command` / `result` 顶层键),
顶层直接是 `target` / `checks` / `sections` / `summary`。

### 3.3 风险评分 (audit --checks risk)

> 旧的 `risk analyze` 命令已退役 (iter_263)。风险评分现在由 `audit --checks risk` 提供。

实际返回结构 (agent 必看):
```json
{
  "target": null,
  "checks": ["risk"],
  "sections": {
    "risk": [
      {"signal": "top.rst_n", "role": "reset", "loads": 2, "drivers": 0, "score": 4.43},
      {"signal": "top.clk_a", "role": "clock", "loads": 1, "drivers": 0, "score": 3.9},
      {"signal": "top.reg_a", "role": "data", "loads": 1, "drivers": 4, "score": 1.78}
    ]
  },
  "summary": {"checks": 1, "findings": 6}
}
```

**关键字段**:
- `role`: 信号角色 (`clock` / `reset` / `data`)
- `loads` / `drivers`: 扇入扇出计数
- `score`: 风险分 (越大越值得先看)

> `audit` 的 risk 项**不含** evidence 字段 —— 要源码位置请另外跑 `trace evidence`。

### 3.4 dataflow analyze --evidence

```json
{
  "result": {
    "paths": [
      {
        "from": "top.din",
        "to": "top.dout",
        "segments": [
          {
            "signal": "top.temp",
            "edge_type": "blocking_assign",
            "evidence": {
              "source_text": "temp = din;",
              "source_location": {"line_start": 38, "line_end": 38},
              "credibility_score": 1.0
            }
          }
        ]
      }
    ]
  }
}
```

### 3.5 controlflow analyze --evidence

```json
{
  "result": {
    "conditioned_drivers": [
      {
        "signal": "top.dout",
        "conditions": [
          {
            "predicate": "rst_n == 0",
            "line": 41,
            "evidence": {
              "source_text": "if (!rst_n) dout <= 0;",
              "credibility_score": 0.95
            }
          }
        ]
      }
    ]
  }
}
```

### 3.6 跨时钟域 (audit --checks cdc)

> 旧的 `cdc analyze` 命令已退役 (iter_263)。CDC 检查现在由 `audit --checks cdc` 提供。

```bash
python3 run_cli.py audit -f top.sv --checks cdc --json -q
```

```json
{
  "target": null,
  "checks": ["cdc"],
  "sections": {
    "cdc": [
      {
        "signal": "top.reg_a",
        "domains": ["clk_a", "clk_b"],
        "has_sync_hint": false,
        "confidence": "heuristic"
      }
    ]
  },
  "summary": {"checks": 1, "findings": 1}
}
```

**关键字段**:
- `domains`: 该信号涉及的时钟域 (>1 个说明跨域)
- `has_sync_hint`: 是否检测到同步器提示
- `confidence`: 判定置信度 (`heuristic` / `pattern` / `measured`)

注意: `audit` 的 cdc 项是**启发式**判定 (`confidence: heuristic`), 且**不含** evidence 字段。
要确认是否真跨域, 请配合 `trace evidence` + `trace fanin` 看实际驱动链。

---

## 4. evidence 失败的常见原因

### 4.1 信号在 generate 块内

```systemverilog
genvar i;
generate
  for (i=0; i<4; i++) begin : gen_array
    logic [7:0] data;
    always_ff @(posedge clk) data <= ...;
  end
endgenerate
```

`top.gen_array[0].data` 可以 evidence, 但需要 `--chain` 看到完整 generate 路径。

### 4.2 跨模块的 port 映射

```systemverilog
sub_inst.sub_sig (内部 always 驱动)
```

`trace evidence sub_inst.sub_sig` 会递归, evidence 返回 **内部** always 块, 不是 sub_inst 端口 mapping 行。如果用户问"映射关系", evidence 不够, 需要 trace fanin 配合。

### 4.3 多 driver (always 块冲突)

如果信号被 2 个 always 驱动 (SV 语法允许但实际错误), evidence 列表会含 2 个, score 都是 0.6-0.7, agent 应报告冲突。

### 4.4 evidence 完全缺失 (无 always)

initial 块, function return, parameter 都不一定有 evidence 块。会有 fallback `credibility_score < 0.5` 标记, agent **必须** 当作"未知"。

---

## 5. evidence 跟 LLM 工具对比

| 维度 | sv_query evidence | LLM (GPT/Claude) 直读 SV |
|------|------------------|-------------------------|
| 准确度 | 100% (机械提取) | 70-90% (易幻觉) |
| 大文件 | O(n) n=行数 | O(n²) token |
| 跨模块 | 1 次 API 调用 | 手动 follow |
| 时序 | 实时 | 受上下文限制 |
| 信任度 | 机器可验证 | 不可验证 |

**sv_query 设计的核心理念**: evidence 字段是 **machine-verifiable** 的, agent 拿到 JSON 可以直接相信, 不需要二次确认 (除非 score < 0.7)。

---

## 6. agent 使用 evidence 的正确姿势

### 6.1 ✅ 应该

```python
result = json.loads(cli("trace evidence top.q -f top.sv --json"))
if result["ok"]:
    ev = result["evidence"]
    if ev["credibility_score"] >= 0.7:
        # 直接采用 + 标 source_location 让人能跳过去
        loc = ev["source_location"]
        print(f"top.q 在 {loc['file']}:{loc['line_start']}-{loc['line_end']} 被驱动: {ev['source_text']}")
    else:
        print(f"top.q 来源模糊 (score={ev['credibility_score']}), "
              f"需人工检查 {ev['source_location']}")
```

### 6.2 ❌ 不应该

- 用 LLM 自己读 SV 文件, 重新生成 evidence (会幻觉)
- 在 score=0.6 时硬给结论 (应该问用户)
- 不传 `--json` 直接解析 text 输出 (脆弱)
- 忽略 `ok=false` 错误 (信号找不到/parser 失败)
- 只看 `credibility_score` 不看 `enclosing_always.text` (CDC 场景 score 不可靠)
