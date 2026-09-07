# L1: Class 域既有隐患修复 (logic 实参展开断 + 连续重建退化)

> **Created**: 2026-09-06 GMT+8
> **Status**: ✅ CLOSED (iter_164) — P1 修复; P2 = P1 混淆 (不存在)
> **来源**: iter_163 (covergroup G2) 实证 — 非 covergroup 引入, class 域既有:

## 背景问题

### P1: 方法调用实参 logic (4 态) 端口 → 方法展开断

复现 (plain, 无 covergroup):
```
class packet;
  bit [7:0] addr;
  function void set(input bit [7:0] d); addr = d; endfunction
endclass
module top(input bit clk, input bit [7:0] din);   // din bit → 通
module top(input logic clk, input logic [7:0] din); // din logic → 断
  packet p = new();
  always_ff @(posedge clk) p.set(din);
```
- bit din: top.p.addr 节点建 + fanin(top.p.addr) = {din} ✅
- logic din: top.p.addr 不建, fanin 空 ❌ (clk 类型无关)
- class truth 全用 bit 端口 → 从未暴露

### P2: unified_tracer 同一实例连续 build 状态退化

build(use_cache=False, target='top') → trace_class_instances (内部无参重建)
→ 再 build(target='top') → 第二次不展开实例成员 (top.p.addr 缺)。
class 测试单 build 未暴露。

## 结果 (iter_164)

- **P1 修复**: _parse_invocation_call 实参 + Assignment rhs 剥 Conversion 壳
  (logic→bit 形参隐式 4→2 态壳, 无 .expr/.symbol → 旧守卫静默 continue 丢
  实参)。测试 6 + Q4 fixture 升级 logic 端口回归覆盖。
- **P2 判定 = 混淆**: bit fixture 连续 build 无退化 (原复现 fixture 全 logic
  端口 = P1 同现象误归因)。unified_tracer 零改动。

## 迭代

- iter_164: P1 根因 (插桩定位) + 修复 + 测试 + P2 澄清

## 关联

- iter_163: 首次实证两问题
- class 追踪: function_extractor (方法展开) / unified_tracer (查询重建)
