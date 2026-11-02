# Iteration 353: parent width 元数据根因（PLAN P52）

**Metadata**:
- **Iteration #**: 353
- **Task Tree Level**: L2（PLAN `P52`）
- **Created**: 2026-11-02 GMT+8
- **Author**: 方豆 / AI 助手（方豆: "继续调查看看"）
- **Outcome**: ✅ 完成（bit consistency 三项目全 pass；2718 passed）

## 🎯 问题

P51 后仍剩：

```text
verilog-axi  out_hdr_next[10..]  parent width=[1:0]  (应为 23)
picorv32     mem_done[1]         parent width=[0:0]
```

## 🔎 根因 1：`_get_data_decl_names` 假设错误

`get_data_declarations()` 在 pyslang 11 对内部 `reg` 直接返回
`VariableSymbol`，没有 `.declarators`。旧实现：

```python
declarators = getattr(data_decl, "declarators", None)
if not declarators:
    return []          # ← out_hdr_next / mem_done 全部丢
```

修复：`VariableSymbol` 直接取 `.name`；`signal_widths` 终于有
`axi_vfifo_enc.out_hdr_next = (23,0)`。

## 🔎 根因 2：只更新 module 定义节点

即使拿到宽度，代码只更新：

```text
axi_vfifo_enc.out_hdr_next          (module 定义)
```

而图中使用：

```text
axi_vfifo.axi_vfifo_enc_inst.out_hdr_next  (实例节点)
```

新增 `_propagate_instance_widths()`：

- 通过 `adapter.get_module_instances()` 拿实例路径 + module type；
- 把 `module_type.signal` 的 width 传播到 `instance_path.signal`。

结果：

```text
axi_vfifo.axi_vfifo_enc_inst.out_hdr_next.width = (23,0)
```

## 🔎 根因 3：module 定义节点污染 instance scope

修 names 后 `_extract_all_widths` 开始创建 `module.out_hdr_next` 节点，
破坏 instance_scope 契约。改为：

- 只更新已有节点；
- 不在 module 定义命名空间创建节点；
- instance 节点由实例宽度传播更新。

## 📉 结果

| 项目 | P51 后 | P52 后 |
|---|---:|---:|
| verilog-axi bit violations | 12 | **0** |
| picorv32 | 2 | **0** |
| strict_uart | 0 | **0** |

`mem_done[1]` 也不再生成，parent width 修复后消失。

## 🧪 测试

- `test_internal_reg_parent_width_propagates`；
- 6 个 graph baseline 因 width 修正**有意重采**（Scheduler `[1,0]→[7,0]` 等）；
- 全量 **2718 passed / 0 failed**。

## ⚠️ 边界

- 实例宽度传播依赖 `get_module_instances()`；枚举失败会 logger.debug 跳过；
- 未做 parameter-specific width（同一 module type 不同参数仍取声明 width）；
- 这属于 width 元数据，不是位逻辑证明。

## 🔗 相关

- 计划: [PLAN.md P52](../../../PLAN.md)
