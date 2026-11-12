# P167 opensource skip disposition

**日期**: 2026-11-12
**状态**: ✅ 完成
**输入**: HANDOFF §7 / P160 triage / P161 remediation

---

## 1. 结论

原记录：

```text
114 passed / 17 skipped / 0 failed
```

独立 worker 在隔离 worktree 中看到 **18 skipped**。额外 1 个不是产品差异，而是
`test_run_long_range_runner` 的 fallback 依赖仓库父目录 `openrtl/`；隔离 worktree 的
`ROOT.parent` 不再是用户 home，因此 pico 也被误跳过。

处置：

```text
- 8 个 retired exp 测试：归档（不是永久 skip）
- 1 个 portability bug：pico fallback 改用 SVQ_OPENRTL_ROOT / home
- 剩余 9 个：显式环境 skip
```

最终：

```text
114 passed / 9 skipped / 0 failed
```

---

## 2. 9 个 skip 的逐项处置

| # | 测试 | 类别 | 实际缺失 | 处置 |
|---|---|---|---|---|
| 1 | `test_workspace_filelist_is_local` | pilot fixture | `/tmp/lr_pilot/axi/*.v` 不存在 | 保留显式环境 skip |
| 2 | `test_fact_check_serv_path` | pilot fixture | `/tmp/lr_pilot/serv/*.v` 不存在 | 保留显式环境 skip |
| 3 | `test_benchmark_runs_successfully` | benchmark timeout | wrapper graph build > 300s | 保留显式 timeout skip |
| 4 | `test_benchmark_4_levels_present` | benchmark timeout | 同上 | 保留显式 timeout skip |
| 5 | `test_l1_instance_count_at_least_2` | benchmark timeout | 同上 | 保留显式 timeout skip |
| 6 | `test_p6_opentitan_tlul_controlflow_list_conditioned` | external fixture | `opentitan_tlul.f` 引用的 `tlul_xbar.sv` / `tlul_pkg` 依赖不全 | 保留显式环境 skip |
| 7 | `test_n3_opentitan_tlul_dataflow_unresolvable` | external fixture | 同上 | 保留显式环境 skip |
| 8 | `test_p3_latency_cva6_alu_0_cycle_combinational` | external fixture | `cva6/Flist.ariane` 的 incdir/依赖不存在 | 保留显式环境 skip |
| 9 | `test_real_opentitan_prim_fifo_sync_passthrough` | external fixture | `prim_util_pkg` / `prim_fifo_sync_cnt` 缺失 | 保留显式环境 skip |

所有 skip 都有显式 reason；没有把 fail 改成 skip。

---

## 3. 已归档的 8 个 retired exp 测试

`test_naplespu_filelist.py` 中：

```text
m02 risk
m03 cdc
m04 sva extract
m05 sva coverage
m06 sva timing
m07 timing
m08 verify gap
m09 coverage suggest
```

`exp` 子命令已不存在；这些测试从 collection 中移除（git 历史保留），
不是永久 `pytest.mark.skip`。剩余 m01 stats / m10 controlflow / m11 dataflow 继续运行。

---

## 4. 独立 worker 的作用

worker `svq-p167-skips` 在隔离 worktree 中：

- 完整跑 opensource 套件；
- 发现 **18 而不是 17**；
- 定位到 pico fallback 的 portability bug；
- 验证 benchmark 是 graph build >300s，不是 crash；
- 复核 `unexecuted = canonical deselected + opensource skip` 口径。

worker 未完成最终表格（在测量 benchmark 时超时/中断），主会话从其日志和复跑结果
完成处置。

---

## 5. 修复的 portability bug

`sim/tests/unit/test_run_long_range_runner.py`：

```python
openrtl = Path(os.environ.get("SVQ_OPENRTL_ROOT",
                              Path.home() / "my_dv_proj" / "openrtl"))
fallback = openrtl / "picorv32" / "picorv32.v"
```

隔离 worktree 现在不再因为 `ROOT.parent` 不同而多 skip 一个 pico 测试。

---

## 6. 当前口径

```text
canonical:   2722 passed / 0 skipped / 131 deselected
opensource:  114 passed / 9 skipped / 0 failed
unexecuted:  131 + 9 = 140
```

`unexecuted` 仍是显式状态，不是通过。

---

## 7. 维护规则

1. 只有三类可以保留 skip：外部 fixture 永久缺失、已知 timeout、显式环境限制；
2. retired 命令测试应归档/删除，不能长期 `skip`；
3. 新增 skip 必须写清实际缺失路径/超时/命令，并更新 REPORT_STATUS；
4. 不允许用 skip 掩盖 fail。
