# 函数调用图需求

> 创建时间: 2026-05-28
> 状态: 需求收集
> 关联: sv_query Class OOP + SubroutineExpander

---

## 背景

在理解 UVM 验证环境时，需要快速掌握：
- sequence 的 body() 方法调用了哪些 task/function
- driver 的 run_phase 中信号驱动的完整流程
- 期间哪些地方调用了 randomize()，哪些信号被随机化
- fork/join 的并发执行结构

当前 sv_query 已有 SubroutineExpander（函数内联展开），但只处理串行调用链，不处理 fork 并发。

---

## 核心需求

### 1. 函数调用图 (Call Graph)

从指定入口（如 `my_sequence::body`）出发，提取完整的调用树：

```
my_sequence::body
├── req = my_transaction::type_id::create("req")
├── start_item(req)
├── req.randomize() with { addr inside {[0:63]}; }
│   └── [RANDOMIZE] addr, data
├── finish_item(req)
│   ├── m_sequencer.send_request(req)
│   │   └── driver::seq_item_port.get_next_item()
│   └── wait_for_item_done()
└── `uvm_info("SEQ", "Done", UVM_LOW)
```

### 2. Fork 处理

UVM 验证中大量使用 fork/join_none：

```systemverilog
task run_phase(uvm_phase phase);
    fork
        collect_responses();   // 并发线程 1
        monitor_timeouts();    // 并发线程 2
    join_none
    
    fork
        drive_item(req_a);
    join
    
    // fork with multiple threads
    fork
        begin
            drive_item(req_b);
            wait(data_valid);
        end
        begin
            #1000;
            `uvm_error("TIMEOUT", "...")
        end
    join_any
    disable fork;
endtask
```

调用图需要：
- 标记 fork 分支（并发执行）
- 区分 join / join_none / join_any
- 标记 disable fork 的作用范围
- 嵌套 fork 的处理

### 3. Randomize 行为标记

在调用图中标记所有 randomize 调用：

```
[CALL] my_sequence::body
  [RANDOMIZE] req.randomize()
    → 随机变量: addr (bit[7:0]), data (bit[31:0])
    → 约束块: c_addr (inline constraint)
  [RANDOMIZE] cfg.randomize() with { ... }
    → 随机变量: mode (bit[1:0])
```

需要提取：
- randomize() 调用位置
- 被 randomize 的对象类型
- 随机变量列表（从 class 定义中获取 rand 变量）
- inline constraint（`with { ... }` 块）

### 4. Sequence/Driver 行为提取

UVM 特定的行为模式识别：

```
[SEQUENCE] my_sequence::body
  → 创建 transaction: req (my_transaction)
  → start_item → finish_item (标准 UVM 流程)
  → randomize → drive (激励生成流程)

[DRIVER] my_driver::run_phase
  → get_next_item (从 sequencer 获取)
  → drive 信号驱动
  → item_done (完成通知)
```

---

## 数据结构建议

```python
@dataclass
class CallNode:
    """调用图节点"""
    caller: str              # 调用者 (如 "my_sequence::body")
    callee: str              # 被调用者 (如 "req.randomize")
    kind: str                # "function" | "task" | "randomize" | "fork" | "builtin"
    line: int                # 源码行号
    children: List['CallNode']  # 子调用
    fork_branch: int = 0     # fork 分支编号 (0=非 fork)
    join_type: str = ""      # "join" | "join_none" | "join_any"
    randomize_vars: List[str] = field(default_factory=list)  # randomize 的变量
    inline_constraint: str = ""  # inline constraint 文本

@dataclass
class CallGraph:
    """完整调用图"""
    entry_point: str         # 入口函数/任务
    root: CallNode           # 根节点
    randomize_calls: List[CallNode]  # 所有 randomize 调用
    fork_points: List[CallNode]      # 所有 fork 点
```

---

## 与现有架构的关系

```
现有:
  SubroutineExpander → 展开函数体，生成信号图边

新增:
  CallGraphBuilder → 构建调用图（不修改 SignalGraph）
       ↓
  CallNode / CallGraph → 独立数据模型
       ↓
  UnifiedTracer.get_call_graph(entry_point) → 查询入口
```

**关键决策**：调用图独立于 SignalGraph，与 CovergroupExtractor 同级。

---

## 已有的基础

| 组件 | 能力 | 限制 |
|------|------|------|
| SubroutineExpander | 函数体展开、参数替换 | 不处理 fork |
| SignalExpressionVisitor | 表达式解析 | 不处理调用链 |
| ConstraintVisitor | 约束解析 | 不处理 randomize with |
| ClassGraphBuilder | class 结构 | 不处理方法调用 |

---

## 实现路径建议

### Phase 1: 基础调用图（串行）
- 从 entry_point 出发，递归提取函数/任务调用
- 标记 randomize() 调用
- 提取 inline constraint

### Phase 2: Fork 处理
- 识别 fork/join/join_none/join_any
- 构建并发分支
- 处理 disable fork

### Phase 3: UVM 行为模式
- 识别 sequence body 模式 (create → randomize → start_item → finish_item)
- 识别 driver run_phase 模式 (get_next_item → drive → item_done)
- 标记信号驱动点

---

## 相关文件

- `src/trace/core/builder/subroutine_expander.py` — 已有函数展开
- `src/trace/core/visitors/statement_collector_visitor.py` — 语句收集
- `src/trace/core/visitors/signal_expression_visitor.py` — 表达式解析
