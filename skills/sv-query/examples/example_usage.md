# sv-query skill 使用示例

---

## 场景 1: 找信号 X 的驱动源

用户问: "谁在驱动 `top.q`?"

**agent 正确做法**:

```bash
cd <PROJ_DIR>/sv_query
python3 run_cli.py trace evidence top.q -f sim/test_simple.sv --json
```

或用 helper:

```bash
python3 ~/my_dv_proj/sv_query/skills/sv-query/scripts/sv_analyze.py sim/test_simple.sv top.q --mode evidence
```

agent 解析 JSON:

```json
{
  "ok": true,
  "signal": "top.q",
  "evidence": {
    "source_text": "q <= d;",
    "source_range": [42, 47],
    "block_kind": "always_ff",
    "credibility_score": 0.95
  }
}
```

**回复用户**:
> top.q 在 [line 42-47] 由 `always_ff` 块驱动, 唯一 driver 是 `q <= d;` (可信度 0.95)。

---

## 场景 2: 数据流 X → Y

用户问: "数据从 `top.din` 怎么到 `top.dout`?"

```bash
python3 run_cli.py dataflow analyze top.din top.dout -f sim/test_simple.sv --evidence --json
```

返回 paths[].segments[].evidence, agent 拼成步骤:

```
top.din → top.temp (line 38, blocking) → top.dout (line 45, non-blocking)
```

---

## 场景 3: 找高风险信号

用户问: "这个模块哪些信号风险高?"

```bash
python3 run_cli.py risk analyze -f top.sv --evidence --json
```

返回 data_signals[] 按 risk 排序, agent 报告 top 5 + 各自的 evidence 位置。

---

## 场景 4: CDC 检查

用户问: "有没有跨时钟域问题?"

```bash
python3 run_cli.py cdc analyze -f top.sv --evidence --json
```

返回 paths[] 含 source_evidence + target_evidence, agent 报告每条 CDC 路径 + 跨的时钟 + 是否有同步器。

---

## 场景 5: 验证缺口

用户问: "哪些信号没 SVA 但风险高?"

```bash
python3 run_cli.py verify gap -f top.sv --evidence --json
```

返回 top_signals[] 含 risk_score + has_sva, agent 报告 (高风险 + 无 SVA) 的信号清单 + evidence 位置让人工补 SVA。

---

## 场景 6: 跨模块追踪

用户问: "改 `top.decoder.opcode` 影响谁?"

```bash
python3 run_cli.py trace impact top.decoder.opcode -f top.sv
```

跨任意深度的子模块, 返回所有受影响的信号 + 路径。

---

## 场景 7: evidence 模糊时

用户问: "这个信号哪来的?" 但 credibility_score = 0.5

**agent 正确做法**:

```json
{
  "ok": true,
  "evidence": {
    "source_text": "data = 0;",
    "source_range": [10, 12],
    "credibility_score": 0.5
  }
}
```

**不要直接采纳**, 回复:

> 信号 `top.data` 在 [line 10-12] 有 `data = 0;` 赋值, 但来源模糊 (score=0.5), 可能是 initial 块或 fallback。**建议人工查看 line 10-12 确认**。

---

## 场景 8: 升级 pyslang 后出问题

用户: "我刚 `pip install pyslang==12.0`, sv_query 跑不动了"

**agent 做法**:

1. 跑 `python3 -m pytest sim/tests/integration/test_pyslang_version_compat.py` 看哪些 smoke 挂
2. 跑全量看失败模式
3. 查 `_pyslang_compat.py` 适配
4. **建议**: 暂时 `pip install 'pyslang>=10.0.0,<12.0.0'` 回到支持范围
5. 如果用户想支持 12.0, 那是新工作: 扩 shim + 加新测试 + 跟用户说"超出 skill 范围, 需要单独任务"

---

## 场景 9: 性能问题

用户: "大文件 (1万行) 跑得很慢"

**agent 做法**:

```bash
# 限制 trace 深度
python3 run_cli.py trace fanin top.q -f big.sv --depth 3

# 用 filelist 分批
python3 run_cli.py stats -fl filelist.f
```

提醒用户: CDC / risk / verify 都会遍历整个图, 大文件慢是预期的。如果实在不行, 拆文件。

---

## 场景 10: 改 sv_query 代码后测试挂了

**agent 流程**:

```bash
# 1. 跑全量
cd <PROJ_DIR>/sv_query
python3 -m pytest sim/tests/ -q
# 9 failed (其余 passed)

# 2. 看具体失败
python3 -m pytest sim/tests/regression/test_X.py -v --tb=long

# 3. 修代码

# 4. 跑单个测试
python3 -m pytest sim/tests/regression/test_X.py -v

# 5. 跑全量
python3 -m pytest sim/tests/ -q
# 全量 passed (计数以 [docs/INDEX.md](../../../docs/INDEX.md) 为准)

# 6. commit + push
git add -A
git commit -m "fix: <description>"
git push origin main
```

**不要** 跳过测试就 commit。

---

## LLM 调用模式

LLM agent 调用 sv_query 必须用以下 flag 组合 (防 OOM + 提速 + 易解析):

### LLM 标准模板 (所有命令通用)

```bash
python3 run_cli.py <command> --json -q --max-results 100 --summary
```

| Flag | 必加? | 作用 |
|------|-------|------|
| `--json` / `-j` | ✅ 永远 | stdout 输出 JSON |
| `--quiet` / `-q` | ✅ 永远 | 抑制 stderr 污染 |
| `--max-results` / `-N` | 推荐 | cap 结果数 (默认 100) |
| `--summary` / `-S` | cdc/risk | LLM 友好 summary (不计 paths) |

### LLM 错误处理

sv_query 返回 JSON 含 `error_code` 字段 (stable, 13 种). LLM 不要 parse `error` 字符串!

```json
{
  "ok": false,
  "error_code": "E_FILE_NOT_FOUND",
  "error": "[Errno 2] No such file or directory: 'foo.sv'",
  "command": "trace_fanin"
}
```

LLM 应该用 `if result['error_code'] == 'E_FILE_NOT_FOUND': ...` 而不是 parse error string。

### 用 helper script (推荐)

不直接调 CLI, 用 `scripts/sv_analyze.py` wrapper:

```python
from sv_analyze import trace_fanin, trace_evidence, stats

# 自动加 --json -q --max-results 50
# 自动 parse JSON, 分类 error_code
result = trace_fanin("sim/test.sv", "top.q", depth=5, max_results=50)
if not result["ok"]:
    if result["error_code"] == "E_FILE_NOT_FOUND":
        # 提示用户文件不存在
        ...
```

详细看 [SKILL.md](../SKILL.md) 的 "辅助脚本" 段。

### LLM 真实工作流示例

```python
# 1. 先 stats 看图大小
graph = stats(filelist="/tmp/proj.f")
if not graph["ok"]:
    return  # 错误已经在 error_code 里分类
nodes = graph["result"]["total_nodes"]
if nodes > 10000:
    # 大图, 用 summary 模式
    risk = risk_analyze(filelist="/tmp/proj.f", summary=True)
else:
    risk = risk_analyze(filelist="/tmp/proj.f", summary=False)

# 2. 拿 top-5 高风险信号
top_risks = risk["result"]["top_risks"][:5]

# 3. 每个高风险信号 trace evidence
for r in top_risks:
    ev = trace_evidence(r["signal_path"], r["signal_name"])
    if ev["ok"]:
        credibility = ev["result"]["evidence"]["credibility_score"]
        if credibility < 0.7:
            r["warning"] = "⚠️ 需人工确认"
```
