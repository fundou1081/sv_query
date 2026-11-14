# P173 full status/evidence cleanup

**日期**: 2026-11-15
**状态**: ✅ 完成

来源：独立全盘 review（NEEDS CLEANUP）。

## 1. P173.1 CLI/exp truth

- `trace impact` 改为 `hidden=True`；
- `trace --help` 不再出现 impact；
- 注册表/CLI_SURFACE 删除虚假 `svq exp <组> <子>` 入口；
- `AGENT_FEATURE_MAP` 改为 **39 core**，impact 移到 exp 排除列表；
- `EXP_NAMESPACE.md` 重写为 **6 个 hidden 直接命令**；
- `test_cli_layering` 增加 impact 隐藏与“无 svq exp 文案”检查。

## 2. P173.2 status docs

- `CURRENT_TODO.md` 重写：当前 P173、真实基线、边界、已知清理项；
- `HANDOFF.md` 重写：主线/exp/历史/风险/接手命令；
- `PLAN.md`：P62.2 改为 gate 评估（no-go），补 P171/P172/P173 变更记录，修掉损坏行；
- README / KNOWN_LIMITATIONS / INDEX / TESTING / REPORT_STATUS 计数统一；
- `SEMANTIC_CONTRACTS` P158.12 标完成；
- `check_docs.py` 在 `run_gates.sh` 改为 `--strict`。

## 3. P173.3 examples/tests hygiene

- 删除 `test_e2e_rtl_to_coverage_suggest.py`（已退役 coverage-suggest 测试）；
- 退役 `test_cli_filelist_parity.py` 中 cdc/coverage/sva/timing/verify-gap 的 zombie 测试，只保留当前 dataflow/controlflow 一致性并加 rc 断言；
- coverage POC 在 unit conftest 改为 **lazy import**，不再是 canonical suite import-time 依赖；
- 重写 `docs/USER_GUIDE.md` 为当前命令；旧版归档到 `docs/archive/2026-11-15-status-cleanup/`；
- 修 README/USER_GUIDE/FILELIST/PRIMARY 的 broken imports、`kind`→`type`、退役 visualize 示例；
- `VISUALIZATION.md`、`CLI_COMMAND_CHEATSHEET.md`、`COVERAGE_GENERATOR.md` 加历史/退役声明；
- `EXPERIMENTAL_FEATURES.md` 改为当前 6 个 exp。

## 4. 最终基线

```text
canonical:  2737 passed / 0 failed / 123 deferred / 0 unexecuted
opensource: 112 passed / 11 skipped / 0 failed
```

计数减少来自删除 zombie/retired tests，不是功能回退。

`bash tools/run_gates.sh` 全绿（strict docs、plan、crap、CLI surface）。

## 5. 仍需注意

- coverage POC 工具本身仍调用已退役的 `exp risk analyze`；它是历史 POC，不恢复 CLI；
- `trace impact` 仍是未标定启发式；
- `check_crap` 依赖 crapper，缺失时 exit 3；
- 公开 skill 文档已修 claim 示例，但历史 validation 文档仍保留旧数字（有意不改）。
