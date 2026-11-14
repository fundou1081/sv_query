# P171.6 benchmark fail->fail

**日期**: 2026-11-14
**状态**: 部分完成（mutation gate 待做）

## 1. 修改

`test_benchmark_pr5.py` / `test_benchmark_picorv32.py`：

- 外部 corpus 缺失：**module-level explicit skip**（环境缺失，不是产品失败）
- benchmark 非零退出码：`pytest.skip` → `pytest.fail`
- output 缺失：`pytest.skip` → `pytest.fail`
- 300s timeout 仍是显式环境 skip（不是产品通过）

这样“benchmark crash”不会再被隐藏成 skip；timeout 仍需要在报告中单独看。

## 2. 未完成

- 把 mutation corpus 纳入独立 gate（当前只在单元测试里跑局部 mutation）；
- benchmark timeout 的最终处置（环境 vs 产品预算）。

## 3. 边界

opensource suite 中的 3 个 benchmark timeout 仍会显示 skip；这不是 pass。
