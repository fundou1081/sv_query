# Iteration 085: workflow/subagent 写文件失败根因 — sandbox delegation + approval never

**Metadata**:
- **Iteration #**: 085
- **Task Tree Level**: L2
- **Parent Task**: 工具链调查 (方豆 "搞清楚为啥 子agent 不能写入")
- **Created**: 2026-09-01 GMT+8
- **Author**: AI 助手
- **Outcome**: ✅ 根因确认 (DHS sandbox delegation 机制)

## 🎯 本次目标

iter_081 时 workflow 派 9 个 subagent 写测试文件全失败 (9 个 null, 只产出 1 文件)。
方豆: "写入迭代记录, 搞清楚为啥 子agent 不能写入"。

## 📊 当前状态 / 预期结果

- 已知现象: workflow 的 agent() 9 个全 null; 复现实验: 单 subagent 写文件被拒
- 预期: 从 DSH session 记录 + 源码找到精确根因

## 🔬 实际结果 — 根因链 (session 记录实证)

### 1. 子 agent 会话的沙箱/审批配置 (delegation)

从子 agent 会话的 session.jsonl (zstd 解压) 第一条记录:

```json
{"type": "sandbox/mode",  "data": {"mode": "workspace-write", "source": "delegation"}}
{"type": "approval/policy", "data": {"policy": "never", "source": "delegation"}}
```

- **sandbox mode = workspace-write** (继承主 agent)
- **approval policy = never** (delegation) — 关键!子 agent 不能发起审批请求

### 2. write 被拒的完整时序 (repro 会话 4ff57c7c)

```
tool/result:  Error: sandbox escalation to "workspace-write" is not st...   ← 首次 write 被沙箱拒
approval/asked: toolName=write, reason="escalate sandbox to danger-full-access:
                当前写入权限被固定为 workspace-write, 但需要创建用户指定文件"
approval/decided: outcome=rejected   ← policy=never 自动拒绝 (无用户弹窗)
tool/result:  Error: the user rejected escalating this operation to "danger-full-access"
```

子 agent 的 write 触发沙箱 escalation → policy=never 直接 rejected → 写失败。

### 3. 为什么"明明写工作区内文件"还要 escalation

子 agent 会话的 workspace 边界与主 agent 不同 — DSH 对子 agent 的 write 判定
"需要创建用户指定文件"并请求 danger-full-access, 说明子 agent 的工作区上下文
未完整继承 (或 write 工具在 delegation 下保守判越界)。

### 4. workflow 9 个 agent 的失败形态 (23:25 批, 4 个抽查)

| agent 会话 | 行数 | 形态 |
|---|---|---|
| 9eb1051c (assign) | 38 | 未到 write 步骤即停 (早期失败) |
| b0a0500f | 38 | 同上 |
| faa1bd0d | 38 | 同上 |
| cbfead54 (ternary) | 243 | 做了探针+读样板, 到 write 被 approval never 拒 |

**两种失败**: 一部分 agent 很快终止 (38 行 = 可能上下文/并发问题), 一部分
做到了 write 但被 approval never 拒。共同结果 = agent 失败 → workflow null。

## 💡 关键发现 / 决策

1. **approval policy "never" (delegation) 是写失败的直接原因**: 子 agent 继承
   policy=never, 任何需要审批的 escalation 自动拒绝 — 主 agent 是 ask (可弹窗),
   子 agent 无此通道。
2. **这是 DSH 沙箱 delegation 设计**, 不是 sv_query 代码问题, 也不是 workflow
   脚本逻辑问题。
3. **workaround (当前会话已用)**: 主 agent 直接写文件 (主 agent 的 write 走
   workspace-write 允许路径 + ask 审批), 子 agent 只做"读/分析/设计/审查"类
   不需要写盘的任务。
4. **若需子 agent 写盘**: 需在 DSH 侧让子 agent 继承 ask policy 或放宽子 agent
   的 sandbox — 超出本会话权限 (settings.yaml 在 workspace 外, 需方豆手动改)。

## 📌 状态

- ✅ 根因确认并记录
- 提交: 本迭代记录
- 遗留: 若要"子 agent 能写盘", 需方豆在 ~/.dsh/settings.yaml 或 DSH 配置侧调整
  (delegation policy), 本会话无法自行修改 (workspace 外)

---

## 🔬 追加实证 (同日): 真正根因 = 子 agent 误带 escalation 参数 (非硬性禁止)

### 决定性对比 (session 记录)

| agent | write 调用 | sandbox_permissions 参数 | 结果 |
|---|---|---|---|
| **主 agent** (5 次抽查) | write(file_path, content) | **无** | ✅ 一次成功 |
| **子 agent** (repro) | write(file_path, content) | **有** (`"sandbox_permissions": null`) | ❌ escalation → approval never 拒 |

子 agent 的 write 调用带了 `sandbox_permissions` 字段 (值为 null) → 触发沙箱
escalation 路径 → `approval/policy: never` (delegation) 自动拒。主 agent 从不带
该参数 → workspace-write 直接写成功。

### 二次验证 (命令子 agent 不带 escalation)

给子 agent 明确指令 "**绝对不要带 sandbox_permissions 参数, 直接 write(file_path, content)**" 后:
- ✅ write 一次成功, 无任何 sandbox/escalation 错误 (test_repro_workflow2.py 创建成功)

### 最终结论

**子 agent 完全能写文件** — 之前 workflow 9 个全 null 是因为子 agent 在任务执行中
**误判自己需要权限升级**, 主动带 sandbox_permissions 触发 escalation, 而 delegation
会话 approval=never 自动拒绝。**不是 DSH 禁止子 agent 写盘**, 是子 agent 行为误解
+ approval never 的组合。

### 解决方案 (零代码改动)

在派给子 agent 的任务指令里明确写:
```
你的会话是 workspace-write 沙箱, 写 <workspace>/ 下文件完全允许,
不需要任何权限升级。绝对不要在 write/edit 工具调用里带 sandbox_permissions
参数。若收到 "sandbox escalation" 错误说明你误加了权限参数 — 去掉重试。
```
或干脆让子 agent 用 bash 写 (`cat > file <<'EOF'`), bash 走同一沙箱无此问题。
