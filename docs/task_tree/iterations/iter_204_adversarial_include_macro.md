# Iteration 204: 对抗性测试第四轮 — 跨文件 include/宏/filelist (发现 R4-1 / R4-2)

**Metadata**:
- **Iteration #**: 204
- **Task Tree Level**: L2 (分析核心 / CLI 可用性)
- **Parent Task**: 方豆 "继续" (对抗第四轮)
- **Created**: 2026-09-08 GMT+8
- **Author**: 方豆 / AI 助手 (deepseek-v4-flash)
- **Outcome**: ⚠️ 2 个发现 (R4-1 UX 缺口 / R4-2 真 bug), 均已最小复现

## 🎯 本次目标

打**跨文件预处理器边界**: `` `include `` + `+incdir+` / 跨文件 `` `define `` / 嵌套 filelist /
`--include` / 宏 token paste / 自包含 include 循环。

## 🔬 实际结果

### 通过 (正确用法下)

| 用例 | 结果 |
|---|---|
| `` `include "simple.svh" `` + filelist `+incdir+inc` | ✅ rc=0 (include 解析正确) |
| 跨文件 `` `define `` (defs 在 A, 用在 B) | ✅ |
| 嵌套 filelist (`-f sub/inner.f`) | ✅ |
| filelist 指向不存在文件 | ✅ 明确报错 (iter_194 的契约) |
| 自包含 include (循环) | ✅ 不挂死, 干净报错 |

### R4-2 ❌ 真 bug: 宏 **token paste (` `` `)** 不生效 → 级联未声明标识符

最小复现 (3 行):

```systemverilog
// inc/defs.svh
`define WIDTH 8
`define MAKE_REG(nm) logic [`WIDTH-1:0] nm``_q;

// top.sv
`include "defs.svh"
module top (input logic clk, input logic [`WIDTH-1:0] d, output logic [`WIDTH-1:0] q);
  `MAKE_REG(data)                       // 期望: logic [7:0] data_q;
  always_ff @(posedge clk) data_q <= d; // ← [UndeclaredIdentifier] data_q
  assign q = data_q;
endmodule
```

对照实验 (决定性): **同样的 include 链路, 宏体不含 `` `` `` 时 rc=0**;
含 token paste 就报 `UndeclaredIdentifier` 2 处 → 结论: include 没问题,
**token paste 展开有问题** (项目自研 `sv_preprocessor` 做跨文件宏展开, 疑似重新
输出宏体时未处理 `` `` ``)。

### R4-1 ⚠️ `-f <filelist>` 误用给出**误导性错误**

`-f` = `--file` (单文件), 不是 filelist —— 这是 iter_189 记录的脚枪。误用时
(iter_189 加了"非设计单元"守卫) 本次却**没**触发清晰提示, 而是:

```
[ERROR] ... top_inc.sv:5:28: [UndeclaredIdentifier]
       Use --no-strict to analyze the partial AST only as a last resort.
```

原因: filelist 内容形如 `+incdir+inc\ntop_inc.sv`, 解析根节点**不是表达式**
(iter_189 守卫判据只覆盖"表达式根") → 守卫不触发, 用户看到的是一堆下游错误 +
被禁 flag 的提示。**建议**: 守卫判据扩展为"filelist 特征内容"
(扩展名 `.f/.fl` 或首行以 `+`/`-` 开头 / 首行像路径) → 给明确提示
"看起来是 filelist, 请用 --filelist"。

## 💡 关键发现 / 关键技术 / 决策

1. **对照实验定位层次**: "简单 include 通过 / token paste 失败" 一步就把问题从
   "include 解析" 缩小到"宏展开" —— 对抗测试的价值在于**用最小对照切开层次**。
2. **守卫判据要覆盖真实误用形态**: iter_189 的守卫只认"表达式根", 而真实误用
   (filelist 内容 `+incdir+...`) 走的是另一条解析路径 → 提示退化。**已知的脚枪
   必须有对应的识别**, 否则守卫只是心理安慰。
3. **自研预处理器是高风险层**: 跨文件宏展开属于"我们自己的实现"(非 pyslang),
   token paste 这类边角语法最容易漏。

## 📢 建议修复 (待方豆拍板)

| # | 问题 | 建议 | 代价 |
|---|---|---|---|
| R4-2 | 宏 token paste 不生效 | 在 `sv_preprocessor` 的宏展开里处理 `` `` `` (拼接相邻 token 后重新分词); 补单测 (含 `nm``_q` / `` `a``b``c `` 多段) | 中 |
| R4-1 | `-f <filelist>` 误用提示退化 | 扩展守卫判据 (filelist 特征内容 → 明确提示用 `--filelist`) | 小 |
| — | 建议固化 | 把第四轮矩阵 (9 用例) 变成 `test_preprocessor_adversarial.py` | 小 |

## 📎 关联

- 相关: `iter_189_addsyntaxtree_sigtrap_guard.md` (守卫), `iter_194_*.md` (filelist 契约)
- 涉及代码: `src/trace/core/sv_preprocessor.py`、`src/trace/core/compiler.py::_reject_non_design_unit`
