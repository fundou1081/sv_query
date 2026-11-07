# A+D 严格协议尝试（P95）

**日期**: 2026-11-07
**状态**: 未完成，协议尝试放弃
**性质**: 不是模型对比结果；是失败实验记录

---

## 1. 目标

在 P94 发现 A+D agent 会绕过 CLI 后，尝试收紧：

- T2 sandbox deny repo；
- 删除 workspace 中的 source/filelist，只给 snapshot tag；
- prompt 要求只允许 `sv_query ... --from-snapshot`；
- 删除 fact-check 产生的 `.cache`；
- 用 DSH session telemetry 审计实际命令。

---

## 2. 实际发生

### 第一次 strict smoke

DeepSeek / `axi_araddr_neighbors`：

```text
duration: 434s
exact: true
protocol_ok: false
reasons: forbidden_path_or_json, python_bypass
```

agent 花了 40+ 次工具调用：

- 搜索 repo / site-packages / `_entry.py`；
- 读 `/tmp/lr_ad_snaps`；
- 试图理解 `--from-snapshot` 的实现；
- 最后才运行有效 CLI。

### 第二次 query-only smoke

去掉 source/filelist 后：

```text
运行 9.5 分钟后仍未结束，手动终止
```

它继续：

- 搜索整个 home；
- 试图 `pip download` / `git clone` 仓库；
- 直接读 snapshot JSON；
- 完全不是“用 CLI 查询”的路径。

**没有完成 24-cell 运行，也没有新的有效模型对比数据。**

---

## 3. 结论

收紧文件系统权限**不能**把 agent 限制到工具调用：

```text
deny repo       → 它搜索别处
no source       → 它读 snapshot JSON
prompt only     → 它不遵守
```

真正需要的是 **harness 级 tool allowlist**，例如：

- 只暴露一个 `svq_ad` 工具；
- 无 bash / read / grep / python；
- 或由外部服务代理 snapshot 查询；
- 不能让 agent 自由探索文件系统。

这不是当前 CLI/prompt 能可靠解决的。

---

## 4. 决策

```text
P95 严格 A/D agent 协议：放弃
```

- 不把 query-only workspace 作为默认；
- 不保留这次修改的 runner/profile（已回退）；
- A+D 只保留为显式工具 / 机器侧预构建能力；
- P94 的 24/24、但更慢的对比仍是有效记录；
- 不用严格尝试证明任何模型差异。

---

## 5. 下一步（如果还要做）

优先级：

1. 在 harness 层实现 tool allowlist；
2. 或做一个只接受 snapshot 查询的 `svq_ad` 服务；
3. 重新跑 1 个 cell 验证协议；
4. 再决定是否跑 24 cells。

否则停止 A/D agent 对比。
