# 4 步工作流程 + 关键技术细节 (agent 必读)

> 来源: SKILL.md 提取, 描述跑 sv_query 的标准工作流

---

## 关键技术细节 (agent 必读)

### 1. evidence 是什么

不是 LLM 生成! 是 sv_query 直接读取 SV 源码的 enclosing always/initial 块 (含嵌套 if), 提取出该信号被赋值的完整上下文。

例如信号 `top.q` 在:
```systemverilog
always_ff @(posedge clk) begin
    if (!rst_n) begin
        q <= 0;            // 这里
    end else if (enable) begin
        q <= d;            // 还有这里
    end
end
```

`trace evidence top.q` 会返回 2 段 evidence, 包含上面 6 行 always_ff 块。

### 2. 跨模块追踪

`trace fanin top.sub_inst.sub_signal` 跨任意深度。底层是 pyslang 的 `InstanceSymbol.portConnections` + `DefinitionSymbol` 反查, agent 不用关心。

### 3. 风险分类 (audit --checks risk)

> 旧的 `risk analyze` 命令已退役 (iter_263), 风险分类现在由 `audit --checks risk` 提供。

信号按 `role` 分 3 类 (实测值):
- `clock`: clock 信号
- `reset`: reset 信号
- `data`: 数据信号

每条含 `signal` / `role` / `loads` / `drivers` / `score` (score 越大越该先看)。
注意: audit 的 risk 项**不含** evidence 字段, 要源码位置请另外跑 `trace evidence`。

### 4. CDC 检测 (audit --checks cdc)

> 旧的 `cdc analyze` 命令已退役 (iter_263)。

```bash
python3 run_cli.py audit -f top.sv --checks cdc --json -q
```

每条 finding: `{signal, domains[], has_sync_hint, confidence}`。
`domains` 长度 > 1 即表示跨域; `confidence` 常见值 `heuristic` (启发式) /
`pattern` / `measured`。

**它是启发式判定, 不是 CDC 求解器** —— 要确认是否真跨域, 配合 `trace evidence` +
`trace fanin` 看真实驱动链。

### 5. LLM-friendly 输出模式

【给 LLM 调用方必读】所有命令支持统一模式:

```bash
# 标准 LLM 调用模板 (推荐):
python3 run_cli.py <command> <args> --json -q
#  - --json: stdout 是合法 JSON, 无 tab/混合
#  - -q 或 --quiet: 抑制所有 stderr (SWAP warning, INFO log), 防止污染 stdout JSON
#  - --max-results/-N: cap 结果数量 (仅 trace fanin/fanout 支持)
#  - --max-paths/-n: cap 路径数量 (dataflow analyze 用这个, 不是 --max-results)
#  - 没有 --summary flag (随旧 cdc/risk 命令一起退役了)
#  - flag 必须放在子命令之后: 'trace fanin X -f F --json' ✅ / 'trace --json fanin' ❌
```

JSON schema 顶层结构 (所有命令一致):
```json
{
  "ok": true|false,
  "command": "trace_fanout",
  "params": {"signal": "...", ...},
  "result": {...},  // 命令特定 schema (见 tools/llm_schema.json)
  "errors": [],  // human-readable error messages
  "error_code": "E_XXX"  // [B2] stable code, LLM 用来分类错误
}
```

15 种 stable error codes (OK + 14 个 E_ 前缀, LLM 应基于此分支处理):
- `E_FILE_NOT_FOUND`, `E_FILELIST_NOT_FOUND`, `E_FILELIST_INCOMPLETE`, `E_FILELIST_INVALID`
- `E_INVALID_INPUT`, `E_ELABORATION_FAILED`, `E_PARSE_ERROR`
- `E_TARGET_NOT_FOUND`, `E_SIGNAL_NOT_FOUND`, `E_SIGNAL_AMBIGUOUS`
- `E_NO_DATA`, `E_PARTIAL_RESULT`
- `E_USAGE`, `E_INTERNAL`

权威定义: `src/cli/errors.py` 的 `ErrorCode` 枚举。

⚠️ **不是每条失败都带 error_code** —— 通用失败信封是 `{"ok": false, "error": ...}`,
`error` 可能是字符串也可能是对象 `{"type": ..., "message": ...}`。解析要兼容两种形状。

正式 schema: `tools/llm_schema.json` (Draft 2020-12, 5 commands + 6 definitions + 14 error codes)
一致性守卫: `sim/tests/unit/test_schema_aligns_with_code.py` (断言 schema enum == 代码 ErrorCode 减去 OK)
验证脚本: `python3 tools/llm_schema_validate.py`

evidence 召回 score (LLM 用来决定是否人工确认):
分数由公式算出, 只会是 {0.0, 0.2, 0.4, 0.6, 0.8, 1.0}:
- `1.0`: snippet + expr 匹配 + name 匹配 + 交叉验证 → 信任
- `0.8`: snippet + expr + name → 信任
- `0.6` / `0.4`: 部分匹配 → 报告用户判断
- `0.2`: 只有 snippet → 报告用户判断
- `0.0`: 没有 enclosing 块 (如未赋值的 input 端口) → **必须**告知用户

详见 [evidence.md](evidence.md) 第 2 节。

---

