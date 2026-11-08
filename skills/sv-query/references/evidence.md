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

| 分数 | 含义 | agent 处理 |
|------|------|-----------|
| `1.0` | 直接 assign 块内赋值, 唯一 driver | **直接采用** |
| `0.9` | 嵌套 always_ff 块 (if 分支) | **采用 + 标 line_start/line_end** |
| `0.8` | 跨 function call 间接驱动 | **采用 + 标"间接"** |
| `0.7` | 跨模块实例 port 驱动 | **采用 + 标 module 边界** |
| `0.5-0.6` | 时序逻辑有多个 always, 来源需消歧 | **报告用户让他选** |
| `<0.5` | 推测性来源 (parser 失败 + fallback) | **必须标"需人工确认"** |

---

## 3. evidence 在 5 个命令里的形态

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

### 3.2 verify gap --evidence

```bash
python3 run_cli.py verify gap -f top.sv --evidence --json
```

```json
{
  "ok": true,
  "top_signals": [
    {
      "name": "top.q",
      "risk_score": 0.8,
      "has_sva": false,
      "evidence": {
        "signal": "top.q",
        "source_location": {"line_start": 42, "line_end": 47, "column": 5},
        "source_text": "q <= d;",
        "credibility_score": 0.95,
        "is_verified": true
      }
    }
  ]
}
```

### 3.3 risk analyze --evidence

实际返回结构 (agent 必看):
```json
{
  "clocks": [{"id": "top.clk", "name": "clk"}],
  "resets": [{"id": "top.rst_n", "name": "rst_n"}],
  "data_signals": [
    {
      "node_id": "top.dout",
      "name": "dout",
      "kind": "NodeKind.REG",
      "fan_in": 4,
      "fan_out": 0,
      "width": 1,
      "is_reg": true,
      "has_sva": false,
      "has_cov": false,
      "func_score": 47.3,
      "func_level": "CRITICAL",
      "timing_score": 38,
      "timing_level": "HIGH",
      "evidence": {...}
    }
  ],
  "summary": {
    "total": 5,
    "critical": 1,
    "high": 1,
    "sva_covered": 0,
    "cov_covered": 0
  }
}
```

**关键字段** (不是 `risk` 而是 `func_level` + `timing_level`):
- `func_score` / `func_level`: 功能风险分 + 等级 (CRITICAL/HIGH/MEDIUM/LOW)
- `timing_score` / `timing_level`: 时序风险分 + 等级
- `fan_in` / `fan_out`: 扇入扇出
- `has_sva` / `has_cov`: 是否有 SVA / covergroup
- `evidence`: 标准 evidence 字段

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

### 3.6 cdc analyze --evidence

```bash
python3 run_cli.py cdc analyze -f top.sv --evidence --json
```

```json
{
  "ok": true,
  "result": {
    "paths": [
      {
        "source": "top.reg_a",
        "target": "top.dout_b",
        "source_domain": "top.clk_a",
        "target_domain": "top.clk_b",
        "source_domain_short": "clk_a",
        "target_domain_short": "clk_b",
        "edge_kind": "EdgeKind.DRIVER",
        "has_synchronizer": false,
        "sync_type": "NONE",
        "sync_flops": 1,
        "risk": "HIGH",
        "source_evidence": {
          "signal": "top.reg_a",
          "source_location": {"line_start": 23, "line_end": 23, "column": 13},
          "source_text": "if (!rst_n)",
          "enclosing_always": {"line_start": 22, "line_end": 27, "text": "..."},
          "enclosing_if": {"line_start": 23, "line_end": 26, "text": "..."},
          "enclosing_chain": [...],
          "is_verified": true,
          "credibility_score": 0.4
        },
        "target_evidence": {...}
      }
    ]
  }
}
```

注意: CDC evidence 的 `credibility_score` 通常 0.2-0.6 (parser 找到 `if (!rst_n)` 不是真正的 driver), agent **应该**读 `enclosing_always` 的 text 字段, 确认是哪个 always 块在驱动, 而不是只信 score。

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
