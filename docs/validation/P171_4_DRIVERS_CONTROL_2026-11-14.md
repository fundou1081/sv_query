# P171.4.1 drivers control opt-in

**日期**: 2026-11-14
**状态**: ✅ 完成（P171.4.2 full merge 仍待做）

## 1. 结果

`drivers` / `trace fanin` 新增：

```text
--include-clock
--include-reset
--include-control (explicit unsupported)
```

行为：

```text
default                 CLOCK/RESET 不进入 drivers
--include-clock         追加直接 CLOCK sensitivity 源
--include-reset         追加直接 RESET sensitivity 源
--include-control       返回 explicit error，不静默忽略
```

实测 `top_minimal.sa1.ready_q`：

```text
default:   leaf_ready, data_o, 0
+clock:    ... + top_minimal.sa1.clk
+reset:    ... + top_minimal.sa1.rst_n
```

## 2. 共享构造

`fanin`/`fanout` 的输入校验与 tracer 构造抽到：

```text
_validate_trace_inputs
_build_trace_tracer
_prepare_trace_tracer
```

这是 P171.4.2 全量合并的第一步；输出循环尚未合并。

## 3. 测试

```text
sim/tests/unit/test_p171_drivers_control.py
  2 passed
```

## 4. 边界

- include flags 只追加 root 的直接 CLOCK/RESET 源，不做 control 边递归；
- `--include-control` 仍显式 unsupported（graph builder 没有 CONTROL 边）；
- fanin/fanout 输出层的重复还没消除（P171.4.2）。
