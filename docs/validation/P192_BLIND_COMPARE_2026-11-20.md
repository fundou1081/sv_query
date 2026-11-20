# P192.2 — source-only vs sv_query blind comparison

> **日期**: 2026-11-20
> **任务**: CVA6 issue #3404 blind solve
> **输入包**: [P192_blind_3404](P192_blind_3404/README.md)（symptom-only，无 fix）
> **独立 run**: 两臂均由 `opencode/hy4-flash-free` 执行，隔离目录 `/tmp/p192_so` / `/tmp/p192_sq`
> **完整答案**: [source_only](p192_blind_compare_2026-11-20/source_only/ANSWER.md) /
> [sv_query](p192_blind_compare_2026-11-20/sv_query/ANSWER.md)

## 1. 结果

| 臂 | wall time | root cause | patch | 动态验证 |
|---|---:|---|---|---|
| source-only | 547 s | 精确：`canonical_addr_check` 用 live `_i` 却消费在 `_q` response 级 | 有效替代方案：增加 `canonical_addr_check_n/_q` 寄存器（6 行） | Verilator pre/post 仿真，复现 13/15，修复后消失 |
| sv_query | 516 s | 精确：同一 root cause | 与上游 fix 等价：`lsu_req_i/lsu_vaddr_i → _q`（2 行） | 未跑动态仿真；用结构证据链 |

**结论：两臂都找到了正确 root cause；sv_query 给出的 patch 更接近上游最小修复，
source-only 给出了语义等价但更大的替代修复。**

## 2. sv_query 用了什么

安装的是 PyPI `sv_query 0.3.1`，通过：

- `search canonical --file rtl --json` 定位信号；
- `drivers canonical_addr_check --filelist filelist.f --json` 得到
  `lsu_vaddr_i[63:38]` 位选 driver（P191 bit hint 链路）；
- `trace profile canonical_addr_check` 显示无 clock domain，而
  `lsu_vaddr_q` 是 stage-0 flop；
- `controlflow analyze lsu_exception_o.valid --evidence` 把
  `canonical_addr_check` 与 `dtlb_hit_q && lsu_req_q` 绑定，并显示
  `tval` 来自 `lsu_vaddr_q`；
- 由此提出与 fix diff 等价的 2 行修改。

关键价值不是“自动发现”，而是：

```text
query 直接给出信号驱动/条件/寄存器阶段的结构证据；
不需要先猜一个仿真场景。
```

## 3. source-only 做了什么

只用阅读/grep/Verilator：

- 读 `cva6_mmu.sv` 找到 live `_i` 与 response `_q` 的错位；
- 自己写 `tb_mmu.sv`，用玩具 Sv39 页表/合法 PTE 复现：
  - spurious cause 13/15；
  - `tval = N`（canonical）；
- 把替代 patch 应用到 `rtl_fixed`，重新仿真：
  - spurious fault 消失；
  - 真正的非 canonical 访问仍然 fault；
- 没有修改原 `rtl/`，用 `SHA256SUMS` 验证。

这个臂的结论更强地经过了动态验证；代价是额外写 testbench 和仿真。

## 4. 怎么读这个对比

### 它支持什么

- 两个独立盲解都收敛到同一 root cause，说明症状/包没有歧义；
- sv_query 的 evidence 链足以在 **不写 testbench** 的情况下给出最小 fix；
- P191 bit-select hint 确实让 `[63:38]` 这种位选 driver 可见；
- source-only 需要额外仿真来确认，sv_query 主要靠结构证据，路径不同。

### 它不支持什么

- **不能**说“sv_query 比 source-only 快很多”：516 s vs 547 s，只差 31 s，
  且 source-only 额外跑了仿真；
- **不能**说“sv_query 自动发现 bug”：任务已经给了症状和范围；
- **不能**外推到其他 bug 类型：N=1，两个臂同模型，题目仍是 CVA6 #3404；
- **不能**忽略 source-only 的动态 oracle：它比 sv_query 臂多了一层实测验证。

## 5. 观察

1. source-only 的 patch 不是上游最小 patch，但语义上可接受；说明“找到 root cause”
   与“给出最小 patch”是两个不同能力。
2. sv_query 臂的 `drivers` + `controlflow` 组合正好覆盖 C1 型缺陷；
   C2 型 LHS 位选仍需 P191 的 hint/下钻。
3. 时间差异不显著，真正的差异是 **证据形态**：
   ```text
   source-only: 需要构造 stimulus / 仿真
   sv_query:    直接读取结构条件/阶段
   ```
4. 两臂都受限：没有人类交互、没有真实波形、没有多案例统计。

## 6. 判定

```text
P192.2 完成：blind comparison 有结果
但它是 N=1、同模型、症状已知的对照，不是准确率/提速 benchmark
```

后续若要对外讲价值，应表述为：

> 在一个真实 CVA6 历史缺陷上，sv_query 能给出可验证的结构证据链，
> 并导出与上游修复等价的最小 patch；source-only 也能收敛，但需要额外仿真。

不应表述为：

> sv_query 自动发现 bug / 比人工快数倍。

## 7. 复现

```bash
# 包
docs/validation/P192_blind_3404/

# 两臂安装/运行记录
docs/validation/p192_blind_compare_2026-11-20/
```

原始 `ANSWER.md` 和 run log 已归档；固定了模型、耗时、工具使用和 oracle。
