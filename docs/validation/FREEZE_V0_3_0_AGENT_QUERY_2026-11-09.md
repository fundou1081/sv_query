# Freeze: v0.3.0-agent-query

**日期**: 2026-11-09
**状态**: frozen baseline
**Tag**: annotated `v0.3.0-agent-query`

---

## 1. 冻结内容

这个基线冻结的是：

```text
sv_query core
  + constrained svq_query DSH tool
  + snapshot/edge evidence
  + verify claim
  + canonical path
  + unknown/abstain contract
```

不冻结：

```text
新功能
新任务类型
新 block onboarding
fault localization
patch generation
```

## 2. 基线

```text
Python: 2571 passed / 0 failed
        7 skipped / 119 deselected
Node tool tests: 73 passed
```

工具 intent：

```text
fanin / fanout / neighbors
path (canonical) / deep_path (alias)
neighborhood
evidence (node + edge)
verify (verified/contradicted/unknown)
```

## 3. 已验证项目

```text
OpenTitan UART: continuous 10/10
OpenTitan I2C:  6/6
P125 DV intake: 6/6
P127 DV intake: initial 2/4 -> schema 4/4
false-confident: 0 on final runs
false-found: 0 on final runs
```

## 4. 已知边界

- snapshot-only；`SVQ_SNAPSHOT_DIR` / `SVQ_SOURCE_ROOT` 需要配置；
- snapshot 没有源码原文，只有位置/表达式；
- 旧 snapshot 没有 edge evidence；
- 无 MIG / connections / instances；
- 依赖闭包仍手工整理（UART 60 files / I2C 67 files）；
- path 是 canonical，不是 shortest；没有 shortest intent；
- alias（如 `ovrd_tx_en` vs `reg2hw.ovrd.txen.q`）需要 task 明确 root；
- 任务语料自撰，不是用户研究；
- 不是 fault localization / patch；
- 不是通用 RTL debugger。

## 5. 安装/使用

```bash
# optional
python3 tools/agent/setup_snapshot.py \
  --path /path/to/project \
  --filelist /path/to/filelist.f \
  --tag my_snapshot \
  --snapshot-dir ~/.svq/snapshots \
  --source-root /path/to/project \
  --install-tool

source ~/.svq/snapshots/my_snapshot.env.sh
```

Agent profile：

```yaml
- id: tool-bash
  disabled: true
- id: tool-fs
  disabled: true
- id: tool-fs-search
  disabled: true
- id: tool-skill
  disabled: true
- insert:
    - id: svq-query-tool
      name: '@svq/query-tool'
```

## 6. 冻结规则

从这个 tag 之后：

```text
允许：
  - 文档修正
  - 真实用户任务 intake
  - 新 block 验证
  - 不改变 query/verify 语义的 bugfix

不允许：
  - 改 path/evidence/verify 的语义
  - 新 intent
  - 默认接口切换
  - fault localization / patch
```

## 7. 下一步迭代

> P131 coverage limitation schema 是冻结后的**诊断输出**，不属于
> `v0.3.0-agent-query` tag；不改变 coverage 提取能力。

冻结后进入 **v0.3.x**：

```text
P129: clean-clone/tag install smoke
  - 从 tag 干净 clone
  - setup_snapshot
  - 一个 query + verify smoke
  - 确认不依赖本机 /tmp 资产
```

这是版本可复现性验证，不是新功能。
