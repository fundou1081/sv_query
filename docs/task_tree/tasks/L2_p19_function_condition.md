# L2 — P19 函数条件诚实标记

**Created**: 2026-10-29 GMT+8
**方豆指令**: "函数出现在条件里且图上无结果，这个要改一下。"

## 问题

P18.2 通过“函数调用结果节点”识别函数：
```
a --(expr="f(a)")--> f --(expr="f")--> y
```
但函数只出现在条件里时，图上可能**没有 f 结果节点**：
```systemverilog
if (f(a)) y = b; else y = c;
case (f(a)) ...
assign y = f(a) ? b : c;
```
条件文本里是函数名/调用，没有节点可标记 → y 仍显示精确。

## P19.1 验收

- `if (f(a))` / `if (f(a) > 0)`：目标 y `function_call=true, precision=unknown`
- `case (f(a))`：同上
- `f(a) ? b : c`：同上
- 函数出现在 clock/reset 条件：同上
- 图上确认**没有** `top.f` 结果节点仍生效
- 真实信号与函数同名（跨 module）不误报

## P19.2 验收

- 新增 CLI/回归测试；全量门禁 0 failed
- PLAN/迭代/INDEX/overview/WORKFLOW 更新


## 完成记录（2026-10-29）

- P19.1 ✅ iter_315：if/case/ternary/clock/package 函数条件均标 function_call=true + unknown
- P19.2 ✅ 全量 2579 passed / 0 failed；检查全绿；图缓存 v7
