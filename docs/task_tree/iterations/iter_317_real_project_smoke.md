# Iteration 317: 真实工程查询 smoke（PLAN P21.1）

**Metadata**:
- **Iteration #**: 317
- **Task Tree Level**: L2（PLAN `P21.1`）
- **Created**: 2026-10-30 GMT+8
- **Author**: 方豆 / AI 助手（方豆: "先1 后2"）
- **Outcome**: ✅ 完成（3 个真实工程 smoke 通过；新增仓库内回归测试）

## 🎯 为什么

P13~P20 改了很多图语义（dynamic/function 标记、缓存 key v9），但全量门禁以 fixture 为主。
在真实多文件工程上验证：构建规模、agent 查询、precision 标记、缓存复用。

## 🛠 工具

新增 [tools/smoke_real_projects.py](../../../../tools/smoke_real_projects.py)：

```bash
python3 tools/smoke_real_projects.py --project all --json
```

- `force=True` 强制**当前代码重建**（不吃旧缓存），再写缓存供 CLI 查询复用
- 检查：节点/边规模、dynamic/function 节点数、查询 `ok`、字段齐全、
  `precision/coarse_fallback/dynamic_index/function_call` 期望、缓存二次加载标记不丢
- 外部工程缺失 → 显式 `skipped`，不算失败

## 📊 实测（fresh build）

| 工程 | 规模 | dynamic / function | 查询 | 结果 |
|---|---|---|---|---|
| strict_uart | 35 nodes / 51 edges | 5 / 0 | `fanin rx_data_o` | `unknown, dynamic=true` |
| | | | `fanin rx_data_o[3]` | `unknown, dynamic=true` |
| | | | `fanout rx_fifo.mem` | `unknown, dynamic=true`, 2 loads |
| verilog-axi（56 文件） | **14,329 nodes / 28,062 edges**（25.36s） | 2,110 / 0 | `fanin ...m_axi_araddr[0]` | `bus, coarse=true`, 2 drivers |
| picorv32（单文件） | 1,789 nodes / 3,748 edges（1.91s） | 501 / 0 | `fanin mem_rdata[16]` | `bit, coarse=false`, 2 drivers |

- 全部 `ok=true`；strict_uart 缓存二次加载 dynamic 集合一致
- axi/pico 无 function 节点（工程本身无 function），函数条件由 fixture 覆盖

## ⚠️ 观察

- verilog-axi 有 **2,110** 个 dynamic 节点：RAM 动态写 `mem[addr]` 污染整个数组元素子树，
  下游读全部 unknown——这是 P16 的保守语义，符合“不静默精确”
- axi 位查询出现 `bus + coarse=true`：该位节点不存在，回落总线并显式标记（预期）

## 🧪 测试

新增 `sim/tests/cli/test_smoke_real_projects.py`（strict_uart，仓库内，~0.8s）：
断言 smoke 返回 0、dynamic>0、3 个查询均 `unknown + dynamic`。
外部 verilog-axi/picorv32 不进全量门禁（路径/内存环境相关），由 smoke 工具按需跑。

## ✅ 验证

全量：2585 → **2586 passed / 0 failed**（+1）。

## 📌 边界

- smoke 只验证**行为/标记**，不做逐信号 baseline（真实工程节点数会随图语义演进）
- verilog-axi 构建 25s；不适合每次全量门禁，按需跑
- OpenTitan 受 8GB 内存限制，当前未纳入

## 🔗 相关

- 计划: [PLAN.md P21.1](../../../PLAN.md)
- 工具: [tools/smoke_real_projects.py](../../../../tools/smoke_real_projects.py)
