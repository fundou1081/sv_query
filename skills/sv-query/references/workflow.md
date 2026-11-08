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

### 3. 风险分类 (risk analyze)

信号按 4 类分类:
- `clock`: clock 信号, 风险 0 (没被驱动)
- `reset`: reset 信号, 风险 0
- `data`: 数据信号, 风险 = (无 SVA 覆盖率) × (扇入深度)
- `unknown`: 解析失败的信号, 风险 0 但标记

### 4. CDC 检测范围

检测 2 种跨时钟域:
- 同步器 (`2-flop synchronizer` / `cdc_sync` 模块)
- 灰色码 (gray-coded) 跨域
**不检测**: 异步复位 (单独标志)

### 5. LLM-friendly 输出模式

【给 LLM 调用方必读】所有命令支持统一模式:

```bash
# 标准 LLM 调用模板 (推荐):
python3 run_cli.py <command> --json -q --max-results 100 --summary
#  - --json: stdout 是合法 JSON, 无 tab/混合
#  - -q 或 --quiet: 抑制所有 stderr (SWAP warning, INFO log), 防止污染 stdout JSON
#  - --max-results/-N: cap 结果数量 (trace fanin/fanout)
#  - --summary/-S: 只返回 counts + top-10 (cdc, risk)
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

13 种 stable error codes (LLM 应基于此分支处理):
- `E_FILE_NOT_FOUND`, `E_FILELIST_NOT_FOUND`, `E_INVALID_INPUT`
- `E_ELABORATION_FAILED`, `E_PARSE_ERROR`
- `E_TARGET_NOT_FOUND`, `E_SIGNAL_NOT_FOUND`
- `E_NO_DATA`, `E_PARTIAL_RESULT`
- `E_USAGE`, `E_INTERNAL`

正式 schema: `tools/llm_schema.json` (Draft 2020-12, 7 commands + 5 definitions + 11 error codes)
验证脚本: `python3 tools/llm_schema_validate.py` (3/3 pass)

evidence 召回 score (LLM 用来决定是否人工确认):
- `1.0`: 直接 always/initial 块赋值 → 信任
- `0.9`: 嵌套 block (always 里的 if) → 信任
- `0.7-0.8`: 跨函数/模块间接驱动 → 报告用户判断
- `<0.5`: 推测性来源 → **必须**告知用户

---

