# Iteration 444: P136.1 false missing-file warning

**状态**: ✅
**日期**: 2026-11-09

## 根因

`prim_secded_pkg.sv` 的同名 function 遮蔽 module 端口提取；
文件实际已在 source list。

## 修复

`_module_source_known()` 扫 `compiler.sources` 的 `module <name>`；
已加载则不报 missing-file warning，warning 文案改中性。

## 验证

I2C live build：false missing-file warning = 0。剩余 P136.2。
