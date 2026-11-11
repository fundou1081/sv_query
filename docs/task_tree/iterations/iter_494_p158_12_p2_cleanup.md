# iter_494 — P158.12 P2 清理（硬编码路径 / no:randomly / 空表达式自环）

- **日期**: 2026-11-12 凌晨
- **任务**: [PLAN] P158.12 P2 清理（current item；12.1 impact 降级已于 iter_492 完成）
- **触发**: HANDOFF §5.3 六项清单
- **结果**: 见"验证"；canonical 全量证据见下

## 1. 完成项

### 12.2 测试硬编码路径（26 文件 → 0 残留）

实测 `grep -rl "/Users/fundou" sim/tests --include=*.py` = 26（旧文档写 20/23 都不准）。
两类处理（pitfalls F-2 预防措施）：

- **仓库内路径**（~24 处）→ `Path(__file__).resolve().parents[3]` 推导；
- **外部 openrtl corpus**（~13 处）→ `SVQ_OPENRTL_ROOT` 环境变量
  （默认 `~/my_dv_proj/openrtl`，本机行为不变）+ 缺失时**显式 skip**
  （`pytest.mark.skipif(not OPENRTL_ROOT.exists(), reason=...)`），
  实测 `SVQ_OPENRTL_ROOT=/nonexistent` → 14 skipped 0 failed（不假失败）。

工具：`tools/fix_hardcoded_paths.py` + `tools/fix_openrtl_imports.py`
（每处替换断言原文存在；ast 语法校验；残留 grep 归零）。

### 12.3 `-p no:randomly` no-op（R-024 前半）

`pytest-randomly` 5.1.0 装入 dev 依赖（pyproject）；`addopts` 增加
`-p no:randomly` 默认禁用随机（本机/CI 顺序确定，行为不变）；
canonical 命令中的 flag 从"无效字面量"变为"显式禁用已装插件"。
需要随机压力时 CLI 传 `-p randomly` 覆盖（已实测两种模式均生效）。

R-024 后半（auto-bless）核查：`tools/graph_snapshot.py` 与
`test_graph_baseline.py` 早已显式"不做自动 bless，缺失即失败"——**非问题**，
本轮仅确认。

### 12.4 空 expression DRIVER 自环（R-026，408 条）

**根因**（fixture 级复现，无需大图）：`connection_extractor.py:679`
对每个实例 output port 加 `child_signal_id → inst_port_id` 的 DRIVER 边，
而两者同为 `f"{inst_path}.{port_name}"`——**恒为自环**且 expression 恒空，
零信息量。minimal_3module（31 节点）就有 4 条；大图 408 条同模式。

**修法**：跳过 `child_signal_id == inst_port_id` 的边（与同文件
另外三处 SELFLOOP 守卫对称）。原"模块内部驱动实例输出"标记的依赖
断言已随 2026-08-13 test_cross_module_tracking 更新移除（测试注释自证）。
真实自依赖（`assign a = a + 1`，带 expression，来自 assign/always
extractor）不受影响。

**回归锁定**：`test_p158_12_selfloop.py` 4 项——408 模式归零 /
fixture 覆盖确认 / 带表达式自环仍被图接受 / 实例端口上游不断链。

### 12.5 task 异常计数（R-027 最小面）

`run_intake_tasks.py` / `run_opentitan_tasks.py` 的 `run_one` 原本只捕获
`TimeoutExpired`——其他异常（如 dsh 拉起失败）会让**整轮跑挂、该任务
行丢失**。补 `except Exception` → 留行（rc=130 + task_error 标记），
异常必须计数不得静默蒸发。

## 2. 验证

**canonical 全量第一轮**（自环修复后）：2698 passed / 12 failed。
逐项分诊（12 → 12 全部闭环，无一真回归）：

| 失败 | 分诊 | 处置 |
|---|---|---|
| `graph_baseline[×6]` | 预期涟漪：图少了假自环边 | 显式 `graph_snapshot.py capture` 重捕（如 minimal_3module 72→68 边） |
| `test_trace_batch` fanin golden | **假自环伪装的 cycle**：`cycles_detected true→false`，false 才是真相 | golden 删除后显式重建（遵守"无自动 bless"） |
| `test_drivers_dominate` | 30% 阈值原靠假自环虚增 DRIVER 计数 | 重校 >25%（实测 28.6%），注释说明 |
| `test_output_port_driven_by_module` | 断言恒自环本身（弱断言：接受零信息边） | 改为分层契约：connection_extractor 层不得产出自环；真 DRIVER 边归 assign_extractor（cross_module 回归锁定） |
| `test_accuracy_a1_a2::A3` | **设计决策冲突**：A3(iter_127)"图保留标记边+查询层过滤" vs R-026"去除" | **裁决支持 R-026**：标记边零信息，其可观测效果全为害（假 cycles_detected / DRIVER 虚增 / 快照膨胀）；真实模块内驱动边（带 expression）独立存在（实测 `top.u_dut.data → top.u_dut.out, DRIVER, expr='data'`）；A3 查询层过滤保留（兼容含旧自环的历史快照）。断言翻转 |
| `test_cross_module_tracking::multi_hop` | 旧断言允许 self-loop 掩盖真答案 | 真实 driver = 字面量 `8'd165`（`assign data = 8'hA5`），断言改为更强语义 + 恒自环不得计为 driver |
| `bit_bridge_cache[×3]` | 预存在（HEAD 复现）：`tmp_path.mkdir(exist_ok=True)` 撞 WorkBuddy 沙箱 shim EEXIST | 顺手修：删冗余 no-op mkdir（pytest tmp_path 必已存在），3 失败→0 |

**决定性证据**（支持去自环）：dut 场景全边清单显示真实驱动边
`top.u_dut.data → top.u_dut.out (DRIVER, assign_type='continuous', expr='data')`
独立存在——恒自环是它的零信息冗余副本，删除不损失任何语义。

其余：
- 三个更新测试文件 + 基线 + golden：99 + 10 + 16 + 5 passed；
- 新增/修改文件 collection：2837 collected / 0 error；
- 受影响 canonical 子集（21 个被改文件）：121 passed + poc 5 passed；
- 缺失 corpus 模拟：14 skipped / 0 failed（显式 reason）；
- `test_p158_12_selfloop.py`：4 passed；
- 最终 canonical 全量：**2710 passed / 0 failed / 131 deselected / 35 subtests**
  （rc=0，26min，收口后干净工作树独立复核）；INDEX 基线行已更新；
- 8 门禁 + `check_plan` 589 项：全绿。

## 3. 边界与诚实声明

- R-028（"绿色"口径统一）**未做**：属 benchmark 报告语义（P159 域），
  与 17 个 skip 处置一起留给下轮；
- R-027 只修了"整轮挂/行丢失"最小面；"false_confident 分母语义重定义"
  （无答案算不算 false_confident）需要方豆拍板口径，未擅自改；
- benchmark runner 改动无测试覆盖（该层无 pytest 门禁），仅 ast 校验 +
  逻辑最小面；P158.4 corpus runner 下次跑真实任务时验证。

## 4. 交接

- current item → 17 个 opensource skip 最终处置（或 R-028 口径统一）
- 外部 corpus 用户须知：`SVQ_OPENRTL_ROOT`（默认 `~/my_dv_proj/openrtl`）
