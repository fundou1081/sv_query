# L1 — signedness 建模与符号扩展（PLAN P9）

**Status**: ✅ 完成（P9.1~P9.3，iter_297）
**Created**: 2026-10-26
**Owner**: 方豆 / AI

## 背景

位精确性已到常量位（P8），但 `4'shF` 这类**有符号字面量**仍回落常量总线：
符号扩展方向（sign vs zero）需要 signedness 信息，而 SignalGraph 目前不建模。

## 范围

1. **P9.1 图元数据**：`TraceNode.is_signed: bool | None`，从 pyslang `type.isSigned`
   提取端口/网表/变量声明；JSON 序列化 + 缓存版本（旧缓存失效）；图基线重生成。
2. **P9.2 查询层**：
   - 有符号字面量 `4'shF`：位查询按符号扩展（高位 = 符号位）
   - 无符号字面量：保持零扩展（P8 已有）
   - 有符号信号（`logic signed [3:0] a`）：`assign y=a` 加宽时高位 = `a[3]`（符号位）
   - 拼接内字面量自决定宽度（不做符号扩展，符合 SV）
   - `a & 4'shF` 的符号扩展常量：高位仍依赖信号位（不误判为恒 0）
3. **P9.3**：signed/unsigned 扩展矩阵测试 + 文档 + 图基线更新。

## 验收

- [x] `y = 4'shF`（y 8-bit）：`fanin(y[5]) = 1'b1`（符号扩展）
- [x] `y = 4'sh2`：`fanin(y[5]) = 1'b0`
- [x] `logic signed [3:0] a; y=a`：`fanin(y[5]) = a[3]`（符号位，位节点存在时）
- [x] 无符号 `logic [3:0] a`：`fanin(y[5]) = 1'b0`
- [x] `{a, 4'shF}`：低 4 位 = 1111（拼接自决定，不符号扩展）
- [x] 图节点 signedness 可序列化/反序列化；基线重生成有说明
- [x] 全量门禁 0 failed

## 非目标

- 有符号算术（乘法/比较）语义：位依赖规则不变（前缀/全位），signedness 只影响扩展方向
- packed struct/union 的 signedness：暂不建模（None = 未知，保守回退）
