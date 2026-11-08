# Snapshot/evidence 一键化（P111）

**日期**: 2026-11-08
**状态**: 完成
**结果**: 重新建 snapshot 后 5 任务 10/10，false-confident 0

---

## 1. 新增脚本

```bash
python3 tools/agent/setup_snapshot.py \
  --path /tmp/lr_ad_prep/axi \
  --filelist /tmp/lr_ad_prep/axi/axi.f \
  --tag p111_axi \
  --snapshot-dir /tmp/p111_snaps \
  --install-tool --json
```

source root 由 filelist 的实际文件路径自动推导；需要时可用
`--source-root` 覆盖。

它做四件事：

1. 调 `sv_query snapshot save`；
2. 校验 snapshot 文件非空；
3. 写 `<tag>.meta.json` + `<tag>.env.sh`（`SVQ_SNAPSHOT_DIR` / `SVQ_SOURCE_ROOT`）；
4. 可选安装 DSH tool。

不修改项目文件。

## 2. 重新建 snapshot

| design | snapshot | size |
|---|---:|---:|
| AXI | p111_axi | 19.3MB |
| SERV | p111_serv | 4.5MB |
| Pico | p111_pico | 2.8MB |

用 full filelist，不是旧的 pruned snapshot。

## 3. 端到端复测

使用同一 5 个 P110 任务，但换新 snapshot：

| 模型 | exact | false-confident | mean wall |
|---|---:|---:|---:|
| MiniMax-M3 | **5/5** | **0** | 6.6s |
| DeepSeek-Flash | **5/5** | **0** | 8.9s |

合计：

```text
10/10 exact
0/10 false-confident
```

## 4. 第一次失败的说明

第一次 P111 e2e 全失败：

```text
Snapshot not found: p111_axi / p111_serv / p111_pico
```

原因是 runner 仍固定读 `/tmp/lr_ad_snaps`，不是 setup 脚本的 `/tmp/p111_snaps`。  
给 task 加 `snapshot_dir` 后重跑 10/10。  
这不是 snapshot 生成失败，是 harness 路径 bug。

## 5. 边界

- 仍是 5 个手工任务，不是外部 fault set；
- 不是 fresh clone；使用已有设计目录；
- `SVQ_SOURCE_ROOT` 目前由 env 文件提供；
- DSH profile 安装仍是 opt-in；
- 不是 fault localization / patch。

## 6. 结论

```text
P111 的核心验收通过：
新 snapshot 目录 + env + tool install 可以脱离旧 /tmp 资产；
5 任务 10/10，零 false-confident。
```

下一步 P112：unknown/abstention/confidence 合同。
