# P176 skill re-review fixes

**日期**: 2026-11-15
**状态**: ✅ 完成

独立 worker 对 P175 skill 的复审结论：FAIL。
核心协议可保留，但示例/字段仍有可运行性和语义错误。

## 修复

### 可运行示例

- `class` 删除不存在的 `--instance`；`--instance` 属于 `trace covergroup`；
- class 名改为 `packet`；单文件用 `-f`，不把 `.sv` 当 `--filelist`；
- deep_chain id 改为 `top.u_mid.u_stage.u_leaf.d`；
- driver claim 明确 **signal=target, driver=source**，示例方向纠正；
- UART 注释区分 primary 1 driver / empty-side 2 drivers；
- snapshot tag 统一 `$TAG`；
- 新增 branch/mux workflow：`graph subgraph --edge-kinds branch`、
  `graph nodes --kind OP_TERNARY`。

### 字段契约

- `driver_count` = distinct direct DRIVER sources（排除 CLOCK/RESET，
  不受 `--max-results` 影响）；`count` = 返回项（含 clock/reset/const，post-cap）；
- `paths` 是 direct envelope；`filelist prune` 不属于该例外；
- 删除 `compare_status`；
- `credibility_score` 集合改为 `{0.0,0.2,0.4,0.6,1.0}`（0.8 不可达）；
- `trace evidence --from-snapshot` 可用但可能 null；
- `verify consistency` 补 `checked/violations` 与 legacy MIG caveat；
- `trace frontier` 字段；
- 精确 JSON 任务：任务指定键优先，不要额外包装；
- `hierarchy --depth 3` 可能不够深。

## 验证

- `test_skill_surface.py` 扩到 7 项，含 broken-template guard；
- full gate: green；
- canonical: 2741 passed / 0 failed / 123 deferred。
