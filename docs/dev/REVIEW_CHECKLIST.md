# 提交前检查清单 (Review Checklist)

> **本文是 `AGENTS.md` 的细则文件之一。** 入口/索引见 [AGENTS.md](../../AGENTS.md)。
> 规则本体见 [DISCIPLINE.md](DISCIPLINE.md)、[SEMANTIC_CONTRACTS.md](SEMANTIC_CONTRACTS.md)
> 与 [CODING_STYLE.md](CODING_STYLE.md)；
> 流程见 [WORKFLOW.md](WORKFLOW.md)。
> **最后修订**: 2026-11-11 (P158 语义检查)

---

## 1. 机械检查 (必须全部 0 退出码)

```bash
python3 -m pytest sim/tests/ -m "not opensource" -q -p no:randomly   # 全量门禁
python3 tools/check_docs.py                                          # 文档卫生
python3 tools/check_except_pass.py                                   # 禁 except:pass
python3 tools/check_semantic_regex.py                                # 语义 regex 纪律
python3 tools/check_cli_layers.py                                    # CLI 分层 R1~R8
python3 tools/gen_cli_surface.py --check                             # CLI 清单一致性
python3 tools/check_crap.py                                          # 复杂度棘轮 (CC>10)
git status --porcelain                                               # 应为空 (或只含预期改动)
```

涉及查询 / 图 / CLI 语义的改动，**额外**跑真实多文件项目冒烟：

```bash
python3 run_cli.py <命令> --filelist sim/tests/fixtures/scheduler_minimal/filelist.f --json
```

> 只跑 fixture 单文件已经三次漏掉真实形态的 bug，别省这一步。

---

## 2. 纪律检查 (违反任一项 = 不许提交)

- [ ] 有没有用 `--no-strict`？ → 有就删掉，改诊断根因
- [ ] 有没有用 `-f` / `--file` 传 filelist？ → 改成 `--filelist`
- [ ] 有没有 silent fallback（异常兜底返回假数据）？ → 改成显式错误 / sentinel
- [ ] 有没有新引入 `except ...: pass`？ → 见 [DISCIPLINE.md](DISCIPLINE.md) §3
- [ ] 有没有为了让测试通过而改断言 / 改 fixture？
- [ ] 有没有改 `src/` 让原本失败的 case "意外通过"？
- [ ] 有没有在 `core` 层写文件？（`core` 只读，写能力只能进 `tools/`）
- [ ] 有没有修改用户的 RTL / 工程文件？

---

## 3. 设计检查

- [ ] 我"了解"这段代码吗（架构位置 / 作用 / 要解决的问题 / 相关代码，4 条全中）？
- [ ] 我是先诊断、出 ≥2 个方案、评估成本收益，才动手的吗？
- [ ] 改法是通用的，还是只针对当前 case 的特判？特判有注释说明为什么天然特殊吗？
- [ ] 修的是根因还是症状？"同类 bug 还会不会再出现"能答"不会"并给出依据吗？
- [ ] 有没有引入/保留**第二份实现**？同一个语义只允许一份
- [ ] 有没有写过长的 / 职责混杂的函数？按职责拆
- [ ] 有没有用字符串承载结构信息？改用 dataclass / Enum / dict
- [ ] 新增/修改的注释与 docstring 是否准确（没有引用已删除的符号）？
- [ ] 失败路径是否**可见**（warning/error/raise）而不是静默？

---

## 3.5 语义检查 (P158 起强制)

只要改动查询 / 图 / verify / snapshot / 写文件：

- [ ] 是否改了某个 [GLOSSARY](../GLOSSARY.md) 术语的含义？→ 先改契约，再改代码
- [ ] 数据边是否仍只含 `DRIVER` + `CONNECTION`？CLOCK/RESET 没有被当成数据路径？
- [ ] `paths --directed` / `dataflow` / `verify claim type=path` 是否共用同一 edge 策略？
- [ ] `verified` 是否考虑了 `truncated` / `sample` / `unknown`？sample 不可能 verified？
- [ ] 预算耗尽是否返回 `unknown`/`truncated`，而不是 `not_found` 或静默截断？
- [ ] 路径/图遍历是否有 work budget + timeout？超限是否可见？
- [ ] 构建/图变化是否有 determinism 测试（同输入至少 3 次 canonical hash 相同）？
- [ ] 是否有 true-positive 测试（构造真实错误，检查必须报）？
- [ ] 是否有 mutation 测试（关闭检查实现，测试必须红）？
- [ ] expected 是否来自独立 oracle，而不是同一实现反向生成？
- [ ] snapshot/MIG 能力是否在矩阵中明确？旧 snapshot 缺 MIG 是否显式 unknown？
- [ ] 写用户文件是否默认 dry-run、`--apply`、已有文件需 `--force`/备份？
- [ ] 公开 claim 是否更新 [CLAIMS.md](CLAIMS.md)，并标 `verified`/`known-broken`/`unverified`？
- [ ] 是否只跑了一次 fresh parse / 一次 worker 证据就声称 deterministic/real-project？
- [ ] 是否用“0 skipped / 门禁全绿”代替语义正确？

**判定**：任一语义检查答不上来 → 不许标完成；只能标进行中/实验。

---

## 4. 影响面检查

- [ ] 调用方都查过了吗（全仓 grep + `tools/find_module_refs.py`）？
- [ ] 改返回类型 / 语义后，下游会不会静默出错？
- [ ] 受影响路径有测试覆盖吗？没有 → 是否已向方豆说明？
- [ ] 影响 truth / baseline / 基准数字吗？
- [ ] 受影响测试的期望值**是被验证后更新**的，还是被改成"能过"的？

---

## 5. 记录检查

- [ ] 迭代记录写了吗（`docs/task_tree/iterations/iter_NNN_*.md`）？
- [ ] 失败的尝试、自伤、误判**如实写了**吗？
- [ ] `CURRENT_TODO.md` 同步了吗（当前任务位 / 最近完成）？
- [ ] `docs/task_tree/overview.md` 的汇总表加了一行吗？
- [ ] 新增/改名文档登记进 `docs/INDEX.md` 了吗？
- [ ] 计数变化只写在 `docs/INDEX.md`，没在别处写死吗？
- [ ] 未修的缺口登记到 `docs/KNOWN_LIMITATIONS.md` 了吗（**按输入形态枚举**，不是只写一个场景）？
- [ ] **我是不是只做完代码就想说"完成了"？** → 代码 ✅ + 测试 ✅ + 文档 ✅ 才算完成

---

## 6. 常见反模式 → 后果

| 反模式 | 后果 | 正确做法 |
|---|---|---|
| "先写代码，文档以后补" | 以后 = 永远不补 | 同一 commit 里写 |
| 为过测试改断言 | 断言是 spec，改了就没人守 | 修功能或改 fixture 源码 |
| 两份实现"分别对齐" | 下次改动只改一处 → 分叉 | 删一份，另一份做适配层 |
| 兜底补丁（零结果时才触发） | 部分结果掩盖真实路径 | 兜底变成遍历的一步 |
| 只跑 fixture 单文件 | 真实 filelist 形态漏测 | 加真实项目冒烟 |
| 登记局限只写一个场景 | 漏掉同函数的其他输入形态 | 按输入形态逐个枚举 |
| 提交信息凭印象写"已更新 X" | 实际没改 → 文档漂移 | 更新后核验 diff |
| 长对话压缩后凭印象继续 | 在过期前提上开发 | 重读 AGENTS.md + CURRENT_TODO.md |

---

## 7. "完成"的定义

最低：

```text
代码 ✅ + 测试 ✅ + 文档 ✅
```

语义能力/公开 claim 还要求：

```text
+ 语义契约影响说明
+ true-positive / mutation 测试
+ 独立 oracle（或说明为何不适用）
+ claim ledger 更新
+ 声称 real-project 时执行可复现 corpus
```

三者缺一 = 未完成。**"我知道还差文档/反例" 不是完成，是进行中。**
