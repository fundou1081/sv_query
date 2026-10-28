# Iteration 310: 动态索引递归传播（PLAN P16）

**Metadata**:
- **Iteration #**: 310
- **Task Tree Level**: L2（PLAN `P16`）
- **Created**: 2026-10-28 GMT+8
- **Author**: 方豆 / AI 助手（方豆: "更深层动态索引递归标注，试着找到潜在问题"）
- **Outcome**: ✅ 完成（图级动态传播 + 4 个潜在问题修复；2547 passed）

## 🎯 背景

P14.1 只在**查询根直接边**上找动态索引：
`y = t + 1; t = mem[i]` → `fanin(y)` 不标 dynamic（边表达式 `t + 1` 没有 `mem[i]`）。
`depth=1` 更明显：只返回 `t`，更看不到上游动态。

## 🔧 实现：图级传播（`_mark_dynamic_provenance`，build 末尾）

| 步骤 | 规则 |
|---|---|
| 种子 | ① 动态索引节点（`mem[i]`）② 表达式含**运行期索引**的边目标 |
| 运行期判定 | `[...]` 内标识符解析为**同 module** 的节点（`i`/`sel`）；参数/常量（`W-1:0`）不算 |
| 动态写污染 | 有 DRIVER 入射的动态节点（`d → mem[i]`）→ 标记数组基址 + **整个已元素化子树** |
| 传播 | 沿 DRIVER/CONNECTION 向下游（跳过 BIT_SELECT） |
| 持久化 | `SignalGraph._dynamic_nodes` 进 `to_dict`/`from_dict`；`CACHE_VERSION` 1.6 |

CLI：`node_is_dynamic`（extra 标记或动态 id）→ `dynamic_index=true`，signal `precision=unknown`；
fanin/fanout 同时看根与结果节点（depth=1 也正确）。

## 🐛 找到并修复的 4 个潜在问题

1. **depth=1 漏标**：`fanin(y, depth=1)` 只返回 `t`，P14.1 直接边扫描看不到动态；
   现在 `t` 在图里已被标记 → unknown。
2. **参数名撞车误报**：`top #(parameter P) ... a[P-1:0]` + 其它模块端口 `top.u.P`
   被全局短名匹配误判动态。改为**按 module 作用域**解析（`f"{module}.{name}"`）。
3. **动态写不污染静态读**：`always_comb mem[i]=d; y=mem[1]; z=y[3];`
   旧逻辑 `z` 仍显示精确 `{y[3], mem[1][3]}`（漏了 `d` 可能写任意元素）。
   现在动态写标记整个数组元素子树 → `z` unknown/dynamic。
4. **缓存丢标记**：动态标记原是内存 `extra`，缓存 JSON 不存 → 热缓存后变回精确。
   现在 `dynamic_nodes` 随图序列化，缓存版本 1.6。

## 📊 效果

| 查询 | 修复前 | 修复后 |
|---|---|---|
| `fanin(y)`（深链） | `bus` | **`unknown, dynamic=true`** |
| `fanin(y, depth=1)` | `bus` | **`unknown, dynamic=true`**（只返 t） |
| `fanout(mem)`（深链） | `bus` | **`unknown, dynamic=true`** |
| 动态写后静态读 `z` | `bit`（错） | **`unknown, dynamic=true`** |
| 参数同名切片 | `unknown`（误报） | **`bus, dynamic=false`** |
| 静态 memory | 不变 | 不变 |

## 🧪 测试

- `test_trace_dynamic_index.py` +5：深链 fanin/depth=1/fanout、动态写污染静态读、参数撞车防误报
- 新增 `test_dynamic_provenance_serialization.py`（2）：to_dict/from_dict 保留标记；静态不标记
- `test_trace_batch` golden **有意重生成**：`uart_top.rx_data_o` 经 fifo 动态读
  （`mem[rd_ptr]`）→ 正确变为 `precision=unknown`（旧 golden 是漏标）

## ✅ 验证

- 全量：2540 → **2547 passed / 0 failed**
- check_docs / check_plan / check_cli_layers / check_except_pass 全绿

## 📌 边界（启发式）

- 运行期判定要求标识符是**同 module 节点**；包/宏/转义名可能漏判
- 传播只沿 DRIVER/CONNECTION；动态**条件**（`if (mem[i])`）暂不传播到控制依赖
- 动态读只标记读取结果；动态写才污染整个数组（已区分）

## 🔗 相关

- 计划: [PLAN.md P16](../../../PLAN.md)
- 前序: [iter_308 动态 unknown](iter_308_dynamic_index_unknown.md)
