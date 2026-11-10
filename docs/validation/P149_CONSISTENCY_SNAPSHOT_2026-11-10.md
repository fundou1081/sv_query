# P149 verify consistency from snapshot

**日期**: 2026-11-10
**状态**: ✅

## 1. 问题

`verify consistency` 没有 `--from-snapshot`；P147 worker 在 SPI_HOST
上只能用 `--filelist` 重新建图。

## 2. 实现

新增：

```bash
sv_query verify consistency --from-snapshot <tag> --checks bit,reciprocity,connection
```

- 复用 `_load_tracer_from_snapshot`；
- `bit` / `reciprocity` 可在 SignalGraph 上运行；
- `connection` 需要 MIG，而 snapshot **不存 MIG**：
  返回 `status:"unknown"` + `"module instance graph missing"`；
- 不伪造 pass；`verified` 在 unknown check 时为 false。

## 3. SPI_HOST 实测

```bash
SVQ_SNAPSHOT_DIR=/tmp/opentitan_svq_spi/snapshots \
  sv_query verify consistency --from-snapshot opentitan_spi \
  --checks bit,connection --json
```

结果：

```text
bit_mapping: fail, 171 violations
connection: unknown, module instance graph missing
verified: false
unknown_checks: ["connection"]
```

这与 P148 修复后的 live 结果一致（bit violations 171）。

## 4. 测试

```text
test_verify_consistency_snapshot.py: 1 passed
```

## 5. 边界

真正支持 `connection` 需要 snapshot 存 MIG，或从 snapshot 重建
instance/port 映射；本轮只做显式 unknown，不伪装成功。
