# Iteration 454: P140 worker nits

**状态**: ✅
**日期**: 2026-11-09

## 来源

DeepSeek worker `svq-p140-review`：APPROVE WITH NITS。

## 修复

- `proven:false` / `asserted_relation` / `boundary_hops`；
- CLI 错误保留 stdout 结构化原因；
- 多 boundary 返回 `ambiguous`；
- map 校验和 malformed 输入；
- 6 个正/负/歧义测试；
- 文档 cwd、退出码、evidence 说明；
- 删除 core docstring 的 OpenTitan 示例。

## 验证

`test_project_adaptation.py: 6 passed`；targeted regression 继续通过。
