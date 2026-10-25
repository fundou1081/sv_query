# Iteration 286: 拆 `UnifiedTracer` 三个巨型方法（PLAN P3.1）

**Metadata**:
- **Iteration #**: 286
- **Task Tree Level**: L2（PLAN `P3.1`）
- **Created**: 2026-10-25 GMT+8
- **Author**: 方豆 / AI 助手（方豆: "继续吧，都做完。不要妥协，不要跳过。"）
- **Outcome**: ✅ 完成（三个巨型方法拆成 step/helper；行为零变化；2348 passed）

## 🎯 目标

`UnifiedTracer`（1,138 行）里三个巨型方法混装了「编排 + 规则 + try/except」：

| 方法 | 原行数 | 问题 |
|---|---|---|
| `build_graph` | 153 | 11 个 step 以**内联闭包**写在方法体里，pipeline 声明淹没在实现中 |
| `_resolve_class_member_access` | 134 | 4 个阶段（class 名 / 实例识别 / 组合升级 / 成员链接）串在一个函数 |
| `_emit_conditional_op_nodes` | 173 | ternary 与 case 两段逻辑几乎复制粘贴，内嵌 `_walk` 与 `_collect_sigrefs` |

## 🔧 拆分结果

### 1. `build_graph`：11 个 step → 独立方法

```
build_graph (153 → 68 行, 主要是缓存读写 + pipeline 声明)
_step_compile / _step_adapter / _step_graph / _step_class / _step_class_member
_step_bit_select / _step_module_graph / _step_path_resolver / _step_tracers
_step_cond_ops / _step_backfill
```

`ctx` 里显式传入 `target` / `auto_target_single_top`（原来靠闭包捕获）。

### 2. `_resolve_class_member_access`：4 阶段 → 4 方法

```
_resolve_class_member_access (134 → 15 行)
_collect_class_names / _find_class_instances / _upgrade_class_instances / _link_member_access
```

### 3. `_emit_conditional_op_nodes`：ternary/case 去重

```
_emit_conditional_op_nodes (173 → 30 行)
_iter_op_nodes       先序遍历表达式树
_signal_refs         SignalRef label 去重
_add_op_node         建 OP_* 节点 (失败只 debug, 不中断 build)
_link_op_edge        条件边
_emit_ternary_op     BRANCH_*
_emit_case_op        CASE_*
```

> 两段原本各自带一份 `_walk` / `_collect_sigrefs` / 建节点 / 连边代码，现在共用同一套 helper。

## 📊 量化

| 指标 | 拆分前 | 拆分后 |
|---|---|---|
| 最大方法 | 173 | **73**（`_backfill_source_locations`，本轮未动） |
| `build_graph` | 153 | 68（其中一半是缓存读写） |
| 文件总行数 | 1,153 | 1,138 |
| 全量门禁 | 2348 | **2348 passed / 0 failed**（零变化） |

## ✅ 验证

- 图基线 6 fixture：零差异
- 条件分支相关测试（ternary/case/branch 关键字）：198 passed
- class 相关（`test_class_oop_truth` / evidence / semantic queries）：58 passed
- 全量：2348 passed

## 💡 说明

- 拆分只搬代码、不改逻辑；每个 step 现在可单独调用/单测
- `build_graph` 剩余 68 行里约 35 行是缓存读取/写回，属正常编排职责
- `_backfill_source_locations`（73 行）本轮未动，仍是下一轮可拆对象

## 🔗 相关

- 计划: [PLAN.md P3.1](../../../PLAN.md)
- 同类前作: [iter_281 拆 driver 递归](iter_281_split_driver_recursion.md)
