# DSH 会话真实 telemetry（P90.3）

**日期**: 2026-11-07
**用途**: 调查 `queries` 自报与真实执行不一致的问题
**数据**: [session_telemetry_96_2026-11-07.json](session_telemetry_96_2026-11-07.json)
**工具**: [tools/benchmark/session_telemetry.py](../../tools/benchmark/session_telemetry.py)

---

## 1. 发现

DSH 的 `session.v4.jsonl.zstd` 里有真实的：

- `tool/call`
- `job/registered` / `job/settled`
- `assistant/message.usage`
- `turn/start` / `turn/end`

这比 agent 最终 JSON 的 `queries` 可靠。

### 96 cells 审计

| 臂 | cells | 有实际 sv_query | 实际 sv_query 数 |
|---|---:|---:|---:|
| source | 48 | 1（尝试/被拒） | 4 |
| T2 | 48 | **48** | **389** |

T2：

```text
48/48 有实际 sv_query 调用
44/44 direct fanin/fanout 实际使用 --depth 1
query list 与真实命令数经常不一致
```

### 自报 vs 真实

示例：

| task | 自报 queries | 实际 sv_query |
|---|---:|---:|
| SERV clk path | 2 | 5 |
| Pico mem_valid fanout | 5 | 8 |
| AXI araddr | 6 | 6 |

所以 `queries` 是 **lossy self-report**，不能用于：

- 精确耗时归因；
- 证明某条命令真的执行；
- 证明没有执行额外命令。

### source 隔离

source 有 1 个 cell 尝试调用 `sv_query`（DeepSeek AXI），但命令失败/被 sandbox 拒绝；
没有成功读取图结果。source 其余 47 cells 没有实际 `sv_query`。

---

## 2. 3 个 cell 的实际成本

| task | wall | tool | model residual | sv_query | tokens |
|---|---:|---:|---:|---:|---:|
| AXI araddr | 16.1s | 3.8s | 12.3s | 6 | 61,935 |
| SERV clk path | 60.2s | 11.2s | 49.0s | 5 | 84,224 |
| Pico mem_valid | 22.9s | 6.4s | 16.5s | 8 | 111,971 |

结论：

```text
tool 占 19–28%
model residual 占 72–81%
```

模型生成仍是主要 wall 成本。

---

## 3. AXI 的异常解释

重放完整 `connections` 需要 26.8s。  
但真实 session 里 agent 的命令是：

```bash
sv_query connections ... | head -60
```

它在 0.729s 内被 `head` 截断退出，**没有完成完整构图**。  
最终 JSON 里却写成简化后的 `connections ... --json`。

因此：

- 不是简单“agent 伪造命令”；
- 是 self-report 丢失了 pipe/截断/未完成信息；
- 用最终 `queries` 重放会得到完全不同的成本。

---

## 4. 对评测的影响

之前说的：

```text
T2 query/depth audit 48/48
```

更准确是：

```text
T2 48/48 有实际 sv_query；
44/44 direct fanin/fanout 实际 --depth 1；
query 文本本身不精确。
```

这不改变：

- T2 exact 48/48；
- source exact 32/48；
- T2 无 high-confidence 错误。

但要求以后：

- 协议审计读 DSH session telemetry，不读最终 `queries`；
- 成本归因读真实 tool duration/token，不重放自报命令。

---

## 5. 边界

- 每个 workspace 有多个历史 session；本次取最新 session，且 wall 与结果接近；
- 未对全部 96 个 session 做人工逐条核验；
- token 包含 cache read，不是账单；
- source 的 1 次 sv_query 尝试不能证明隔离失败，只能说明命令被拒绝/失败。
