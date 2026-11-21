# Repository layout — where to develop

> **状态**: 强制规则
> **日期**: 2026-11-21

## 两个仓库

| 仓库 | 用途 | 是否开发 |
|---|---|---|
| `fundou1081/sv_query`（public） | 产品代码、测试、用户文档、release | **唯一开发主线** |
| `fundou1081/sv_query_private`（private） | 旧历史、agents/memory/task_tree/archive | **冻结归档，只读** |

## Agent / contributor 规则

```text
开发、提交、PR、CI、release 都在 public sv_query。
private 只用于查旧 commit / 旧文档，不从 private 继续开发。
```

- 不要在 private 上修改产品代码；
- 不要把 private 的历史合并回 public；
- 内部笔记放本地私有目录或 private 的独立分支，不合回 public；
- 客户 RTL / 凭据 / 内部讨论不得进入 public；
- 公开仓库的隐私门禁：
  ```bash
  python3 tools/check_privacy.py
  python3 tools/check_repo_hygiene.py
  ```

## 为什么

public 已经重写为干净历史，并配置了 CI / PyPI trusted publishing；
private 保留重写前的完整历史。两边继续并行开发会产生不可合并的双历史，
并可能把已清理的私有资产重新带回 public。
