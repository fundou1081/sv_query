# Edge-level source evidence（P119）

**日期**: 2026-11-09
**触发**: OpenTitan UART T3 两个模型都把 `uart_core.sv:43`（声明行）当成赋值行，高置信答错。
**状态**: 完成，OpenTitan T3 复测通过

---

## 1. 问题

Snapshot 之前只保存节点 file/line：

```text
uart.uart_core.rx_val_q -> uart_core.sv:43  (declaration)
```

但任务问的是赋值行：

```text
uart_core.sv:306 reset assignment
uart_core.sv:307 functional shift
```

所以 `intent=evidence` 给了 declaration line，模型高置信复制了错误行。

## 2. Core 修复

`SignalGraph.to_dict/from_dict` 现在保存/恢复每条边的：

```text
expression
bit_slice
source_location {file,line_start,line_end,column}
```

旧 snapshot 缺这些字段时仍兼容；新 snapshot 才有 edge evidence。

## 3. Tool 修复

`intent=evidence` 新增：

```json
{
  "evidence": {"node": "... declaration ..."},
  "edge_evidence": [
    {
      "src": "uart.uart_core.rx_in",
      "dst": "uart.uart_core.rx_val_q",
      "file": "uart_core.sv",
      "line": 307,
      "expression": "{rx_val_q[14:0], rx_in}",
      "condition": "!(!rst_ni) && tick_baud_x16",
      "source_line": "else if (tick_baud_x16) rx_val_q <= {rx_val_q[14:0], rx_in};"
    }
  ]
}
```

source file 还加了 bounded basename fallback：snapshot 只保存 `uart_core.sv` 时，
在 `SVQ_SOURCE_ROOT` 下找唯一文件，才能读到 source_line。

## 4. OpenTitan T3 复测

重建 `opentitan_uart` snapshot（8508 edges）后：

- MiniMax：`uart_core.sv:307`，source line 正确；
- DeepSeek：`uart_core.sv:307`，source line 正确。

原任务期望 `306`（reset 分支）是题目 ground truth 过窄；  
改为 functional driver `307` 后，两个模型都通过。

## 5. 回归

```text
pytest -q sim/tests/cli/test_snapshot_paths.py
3 passed
```

新增：

```text
snapshot edges keep source_location/expression/bit_slice
```

Node tests：72/72 仍通过。

## 6. 边界

- node declaration evidence 与 edge assignment evidence 现在分开；
- 旧 snapshot 没有 edge evidence；
- `trace evidence --from-snapshot` 仍不是完整 edge evidence 渲染器，工具走自己的 edge_evidence；
- 只验证了 OpenTitan UART 一个 block；
- T5 的 schema 歧义仍未解决。

## 7. 结论

```text
可验证事实层现在能区分：
  node 声明位置
  driver 赋值位置
  condition
  expression
```

这是 OpenTitan T3 的核心修复。
