# L2 — P18 可信性与测试入口补强

**Created**: 2026-10-29 GMT+8
**方豆指令**: 按顺序做 1 2 3；不做 4（函数 inline）、5（signed 逐位算术）。

## 背景与排序理由

| # | 项 | 为什么先做 |
|---|---|---|
| 1 | 层次化条件作用域 | 实测静默假阴性：`if (u.q)` 端口接不同线名时 y 仍 `precision=bus`，动态依赖丢失 |
| 2 | 函数调用诚实标记 | 实测 `fanin` 返回 `top.f` 函数符号且 precision=bus，看起来像普通信号（误导 agent） |
| 3 | `--bits` 范围/显式映射 | 纯 CLI、低风险；测试矩阵生成更稳（方豆: "后续更有利于测试"） |

## P18.1 验收

- `if (u.q)`（`u.q` → 内部动态 `mem[i]`，端口接任意线名）→ `fanin(y)` = `unknown, dynamic=true`
- 更深层 `u.sub.q`、绝对路径 `top.u.q` 同样解析
- 参数/常量条件（`a[P-1:0]`）仍不误报
- 新增 CLI/回归测试；全量门禁 0 failed

## P18.2 验收

- 函数调用节点 `top.f` 输出 `function_call=true`、`precision=unknown`
- `fanin(y)` 不再把 `top.f` 当普通 bus 源（信号级 `precision=unknown`）
- 不影响非函数信号
- 新增测试；全量门禁 0 failed

## P18.3 验收

- `--bits 7:4,3:0` 支持范围（按 `hi:lo`）
- `--bits src=1,dst=5` 显式映射（避免位置错）
- 范围节点缺失 → 显式 `precision=bus/unknown` + `coarse_fallback`
- 原有单 bit 用法保持兼容
- 新增测试；全量门禁 0 failed

## 边界（不做）

- 函数 inline：`SubroutineExpander` 保持未接入；只做诚实标记
- 有符号算术逐位：保持总线粒度 + `coarse_fallback`
