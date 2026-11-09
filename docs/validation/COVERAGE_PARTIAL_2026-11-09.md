# Coverage partial extraction（P131）

**日期**: 2026-11-09
**问题**: OpenTitan covergroup elaboration 失败，coverage 层无法查询
**结果**: 新增显式 `trace covergroups --partial`；I2C 11 个 covergroup 可列出，错误显式保留

---

## 1. 根因

Worker 隔离出不是 inherited base member，而是 **pyslang CovergroupBody 内建名遮蔽**：

```text
coverpoint start;
coverpoint stop;
```

`start`/`stop` 是 IEEE 1800 §19.6 covergroup body 的内建子程序名；
pyslang 在 covergroup body 的无限定名查找中先命中内建成员，把外层
module port / class member / sample 形参解析为 `void`：

```text
InvalidCoverageExpr
VoidAssignment
InvalidBinsTarget   (bin 名也叫 start/stop 时)
```

两个失败层：

```text
coverpoint 表达式       → InvalidCoverageExpr + VoidAssignment
binsof(cp_action.start) → InvalidBinsTarget
```

## 2. 为什么不能直接修

这是 pyslang 上游语义缺陷；当前 pyslang 11/12 都复现。  
sv_query 不改写用户 RTL/TB 源码，也不做全局标识符重命名。

## 3. 实现

利用 pyslang 在部分语义错误后**仍提供 partial RootSymbol** 的事实：

- `SVCompiler.get_partial_root()`：显式取 partial root；
- `CovergroupExtractor.extract(allow_partial=True)`：遍历 partial root，
  把 `CovergroupInfo.errors` 标为错误码；
- CLI：

```bash
sv_query trace covergroups --partial --filelist <tb.f> --json
```

返回：

```json
{
  "ok": true,
  "result": {
    "partial": true,
    "elaboration_errors": [...],
    "covergroups": [...]
  }
}
```

默认（不带 `--partial`）仍严格失败，不静默降级。

## 4. OpenTitan I2C 实测

filelist：

```text
uvm_stub_pkg.sv
i2c_cov_wrapper.sv  (includes i2c_env_cov.sv)
+incdir+ hw/ip/i2c/dv/env
```

结果：

```text
partial: true
covergroups: 11
elaboration_errors: 20
```

包括：

```text
i2c_interrupts_cg        30 coverpoints
i2c_fifo_reset_cg        10 coverpoints, 6 crosses
i2c_fmt_fifo_cg          12 coverpoints, 1 cross
i2c_fifo_level_cg         3 coverpoints, 1 cross
i2c_operating_mode_cg     5 coverpoints, 2 crosses
...
```

错误仍显式列出（`InvalidCoverageExpr` / `VoidAssignment` /
`InvalidBinsTarget`），不能把 partial 当作完整语义。

## 5. 测试

新增：

```text
sim/tests/regression/test_covergroup_partial.py
sim/tests/fixtures/covergroup_builtin_shadow.sv
sim/tests/fixtures/covergroup_builtin_shadow_bins.sv
sim/tests/fixtures/covergroup_inherited_member.sv
```

覆盖：

- builtin-shadow 输入：partial 返回定义 + 错误码；
- strict 模式仍抛 `CompilationError`；
- inherited member 对照：非 partial，base/derived cg 都正常。

结果：

```text
test_covergroup_partial.py: 3 passed
现有 covergroup regression: 87 passed
```

## 6. 边界

- partial 只保证 **定义/coverpoint/bins/cross 结构**；
- 被 shadow 的表达式语义仍是 `void`，不能声称完整类型解析；
- `trace covergroup <name>` / `coverpoints` 仍走 graph，未开放 partial；
- 没有 TB-inclusive snapshot；
- 尚未把 coverage 层接入受限 `svq_query` tool；
- 不是 coverage 数据库/仿真结果。

## 7. 意义

这一步把：

```text
coverage 完全不可查
```

变成：

```text
coverage 定义可查，但显式标记 partial + 错误
```

它足够支撑下一步 testbench-angle pilot 的 **coverage 定义层**，
但还不足以宣称 random→constraint→RTL→coverage 端到端已验证。
