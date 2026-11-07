# sv_query skill pilot（P96）

**日期**: 2026-11-07
**范围**: 3 个代表 cell ×2 条件 ×DeepSeek-Flash ×seed1
**性质**: skill 可用性 pilot，不是模型排名
**数据**: [skill_pilot_2026-11-07.json](skill_pilot_2026-11-07.json)

---

## 1. 条件

- A `prompt`：原有 A+D prompt，source 存在，snapshot 可用；
- B `skill`：workspace 安装 `.dsh/skills/svq-query-protocol`，prompt 要求先加载 skill。

Skill 内容：

- 只允许 `sv_query ... --from-snapshot`；
- direct 查询必须 `--depth 1`；
- 禁止 repo / JSON / cache / python；
- 最多 8 条命令；
- 固定最终 JSON schema。

3 个 cell：

```text
axi_araddr_neighbors
serv_clk_path
pico_adapter_mem_valid_fanout
```

---

## 2. 结果

| cell | prompt | skill |
|---|---:|---:|
| AXI araddr | 31.9s ✅ | 102.3s ✅ |
| SERV clk path | 32.5s ✅ | 55.2s ✅ |
| Pico mem_valid | 75.0s ✅ | 30.5s ✅ |

均值：

```text
prompt: 46.5s
skill:  62.7s
```

准确率：

```text
prompt 3/3
skill  3/3
```

---

## 3. 关键事实：skill 没有被加载

检查 DSH session 的 `tool/call`：

```text
prompt 条件：skill calls = 0
skill 条件：skill calls = 0
```

三个 skill cell 的最终 session 都没有调用 `skill` 工具。  
它们仍然用 bash 搜索、读文件、跑命令。

所以这次不能说明“skill 有效”；只能说明：

> **模型没有按 prompt 去加载 skill。**

之前单独 smoke 曾出现过一次 `skill` 调用，但最终 3-cell 运行没有复现。

---

## 4. 结论

```text
skill 内容本身没有进入上下文；
skill 条件 ≈ prompt + 多一个可用但没用的 skill；
因此 latency 差异来自模型行为，不是 skill。
```

skill 不能靠“放在 workspace + prompt 提醒”保证加载。  
需要：

- system-level 强制注入 skill；
- 或 harness 把 skill 作为固定上下文；
- 或工具 allowlist / 单一 `svq_ad`。

## 5. 决策

- 不扩到 24 cells；
- 不把 skill 作为默认；
- skill 文件保留，作为未来强制注入的材料；
- 下一步优先做 harness 强制，而不是继续写更多 skill。

## 6. 边界

- 1 模型，1 seed，3 cells；
- skill 未实际加载；
- 不作为模型能力对比；
- prompt/skill 条件不是完全受控的 skill 效果实验。
