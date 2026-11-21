# P174 independent-review follow-up

**日期**: 2026-11-15
**状态**: ✅ 完成

来源：独立 subagent 对 HEAD 98e3b3c7 的全盘 review（NEEDS CLEANUP）。

## 1. CLI/help truth

- `connections` 帮助/参数/docstring 改为**只接受实例路径**；不再宣传模块名/四类边；
- 代码帮助/示例中的 `svq` 改为实际安装的 `sv_query`；
- USER_GUIDE `trace manifest --path-file` → `--paths-file`；
- 新增 `test_cli_layering`：
  - connections help 不得出现“模块名”；
  - trace help 不得出现 `` `svq ``。

## 2. Boundary docs

- `PLAN.md` P61 标题改为“对称性；typo 为独立项目”；
- `structural_review_plan` 加 typo 历史边界提示；
- `structural_findings_contract` 删除 `typo.candidate` 的未来承诺，补 `verified/coverage_*` 字段；
- coverage 文档改为：`ControlCoverageGenerator` 源码已归档/删除；
  `tools/coverage_gen_demo.py` 是不可用历史残留，不宣称 POC retained；
- INDEX 中 COVERAGE_GENERATOR/RANDOMIZE 标历史。

## 3. Structural coverage semantics

`coverage_complete` 以前仅等于 `not truncated`，零 group 时仍 true。
现在：

```text
coverage_complete = (not truncated) and checked_groups > 0
```

并补 zero-group 测试。

## 4. Status/count/example hygiene

- `CURRENT_TODO`/`private archive` 去掉“P173 处理中”；
- INDEX 测试行数改为实测；iterations 511（新 P174 后再 +1）；
- INDEX 的 EXPERIMENTAL_FEATURES 描述改为当前；
- TESTING 的 OpenTitan marker 从归档 test 改为当前测试；
- KNOWN_LIMITATIONS 删除“当前 _pyslang_compat”；修正 distance/snapshot 矛盾；
- docs/README 加 visualize 退役 banner；VIEW 层注明当前无命令。

## 5. 当前

最终 canonical/gate 通过：
核心 query/verify 健康；CLI/边界文档/结构语义已对齐。
