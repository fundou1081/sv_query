# P136.1 false missing-file warning

**日期**: 2026-11-09
**问题**: `prim_secded_inv_64_57_dec.sv` 已在 filelist，却报“可能缺少文件/没有端口定义”
**结果**: 已修；I2C baseline stderr 中该 warning = 0

---

## 1. 根因

`prim_secded_pkg.sv` 里有一个**同名 function**：

```systemverilog
function automatic secded_inv_64_57_t
    prim_secded_inv_64_57_dec (logic [63:0] data_i);
```

与 RTL module 同名。pyslang 的 module/package 符号解析在该场景下没有把
module 端口面放进 `get_modules()`；`ConnectionExtractor` 因此拿不到
`all_module_ports[prim_secded_inv_64_57_dec]`。

但源文件确实在 `SVCompiler.sources` 里，而且明确包含：

```systemverilog
module prim_secded_inv_64_57_dec (
```

旧逻辑只看“端口表为空”就推断“文件缺失”，于是 false warning。

## 2. 修复

新增：

```text
_module_source_known(module_name)
  → 扫 compiler.sources 里的 \bmodule <name>\b
```

判定：

```text
module 源文件已加载 → 不报 missing-file warning
module 源文件也没有 → 才报
```

同时把 warning 文案改中性：

```text
[sv_query] 模块端口未解析: ...
  → 可能是 filelist 缺少该 module，也可能是同名 package 函数/宏遮蔽了模块名
  → 先用 filelist 确认 module 是否存在；若已存在，按端口提取限制处理
```

`ExtractorResult.warnings` 从 `"Missing module"` 改为
`"Unresolved module ports"`，避免下游误判。

## 3. 验证

I2C baseline：

```text
stderr 中 "可能缺少文件" = 0
stderr 中 "模块端口未解析" = 0
```

其他正常 warning（parameterized port width fallback）保留。

## 4. 边界

- 这只修**告警分类**，不修 pyslang 同名函数遮蔽 module 的端口提取；
- 该模块端口在图中可能仍不完整；
- 真实缺失文件仍会 warning；
- 不改变任何 query/verify 语义。

## 5. 测试

```text
check_docs / check_plan / check_crap / check_cli_layers: ✅
I2C live build warning smoke: 0 false missing-file warnings
```
