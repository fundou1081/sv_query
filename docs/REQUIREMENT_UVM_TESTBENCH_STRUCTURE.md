# UVM Testbench 静态结构提取需求

> 创建时间: 2026-05-28
> 状态: 已实现
> 关联: sv_query Class OOP + 函数调用图

---

## 背景

UVM testbench 有固定的结构模式：
- env 包含 agent、scoreboard、sub_env
- agent 包含 driver、monitor、sequencer
- sequence 挂在 sequencer 上
- test 例化 env，配置 default_sequence

理解这个结构是理解验证环境的第一步，但目前只能靠人工读代码。

---

## 核心目标

从 UVM testbench 源码中提取静态组件结构图：

```
my_test (uvm_test)
└── my_env (uvm_env)
    ├── my_agent (uvm_agent)
    │   ├── my_driver (uvm_driver)
    │   ├── my_monitor (uvm_monitor)
    │   └── my_sequencer (uvm_sequencer)
    └── my_scoreboard (uvm_scoreboard)
```

---

## 需要提取的信息

### 1. 组件层次 (Component Hierarchy)

从 `uvm_component` 派生的类，通过 `new()` 和 `create()` 构建层次：

```systemverilog
class my_env extends uvm_env;
    my_agent      agent;
    my_scoreboard sb;

    function void build_phase(uvm_phase phase);
        agent = my_agent::type_id::create("agent", this);
        sb = my_scoreboard::type_id::create("sb", this);
    endfunction
endclass
```

提取：
- my_env 包含 my_agent 和 my_scoreboard
- 创建方式：`type_id::create` (UVM factory)

### 2. Port/Export 连接 (TLM Connections)

```systemverilog
class my_env extends uvm_env;
    function void connect_phase(uvm_phase phase);
        agent.monitor.ap.connect(sb.analysis_imp);
    endfunction
endclass
```

提取：
- agent.monitor.ap → sb.analysis_imp (TLM 连接)

### 3. Factory Override

```systemverilog
class my_test extends uvm_test;
    function void build_phase(uvm_phase phase);
        my_transaction::type_id::set_type_override(my_special_transaction::get_type());
    endfunction
endclass
```

提取：
- factory override 关系

### 4. Config DB 设置

```systemverilog
class my_test extends uvm_test;
    function void build_phase(uvm_phase phase);
        uvm_config_db#(virtual my_if)::set(this, "env.agent.driver", "vif", vif);
    endfunction
endclass
```

提取：
- config_db set/get 关系
- 虚接口传递路径

### 5. Sequence 注册

```systemverilog
class my_test extends uvm_test;
    function void build_phase(uvm_phase phase);
        uvm_config_db#(uvm_object_wrapper)::set(this,
            "env.agent.sequencer.run_phase",
            "default_sequence",
            my_sequence::get_type());
    endfunction
endclass
```

提取：
- default_sequence → sequencer 的映射

---

## 数据结构建议

```python
@dataclass
class UVMComponent:
    """UVM 组件"""
    name: str                     # 组件名
    class_name: str               # 类名
    base_class: str               # 父类 (uvm_driver, uvm_monitor, etc.)
    parent: str = ""              # 父组件名
    children: List[str] = field(default_factory=list)
    component_type: str = ""      # "driver" | "monitor" | "sequencer" | "agent" | "env" | "test" | "scoreboard"

@dataclass
class TLMConnection:
    """TLM 连接"""
    source: str                   # 源端口路径 (agent.monitor.ap)
    target: str                   # 目标端口路径 (sb.analysis_imp)
    port_type: str = ""           # "analysis" | "put" | "get" | "master" | "slave"

@dataclass
class FactoryOverride:
    """Factory Override"""
    original: str                 # 原始类型
    override_type: str            # 覆盖类型
    scope: str = ""               # 覆盖范围

@dataclass
class ConfigDBEntry:
    """Config DB 条目"""
    context: str                  # 上下文路径
    field_name: str               # 字段名
    value_type: str               # 值类型
    target_path: str = ""         # 目标路径

@dataclass
class UVMTestbench:
    """UVM Testbench 完整结构"""
    components: List[UVMComponent]
    connections: List[TLMConnection]
    overrides: List[FactoryOverride]
    config_entries: List[ConfigDBEntry]
    sequence_map: Dict[str, str]  # sequencer_path → sequence_class
```

---

## 与现有架构的关系

```
UVMTestbenchExtractor (新增)
       ↓
UVMTestbench (独立数据模型)
       ↓
UnifiedTracer.get_uvm_testbench() → 查询入口
```

**关键决策**：UVM 结构独立于 SignalGraph，与 CallGraph/Covergroup 同级。

---

## 依赖的 UVM 特定用法识别

| 用法 | 识别方式 |
|------|---------|
| `type_id::create("name", this)` | 工厂创建，建立父子关系 |
| `super.build_phase(phase)` | phase 调用链 |
| `.connect(` | TLM 连接 |
| `uvm_config_db#(T)::set(...)` | Config DB 设置 |
| `set_type_override` / `set_inst_override` | Factory override |
| `default_sequence` | Sequence 注册 |
| `uvm_analysis_port` / `uvm_put_port` | Port 类型识别 |

---

## 实现路径建议

### Phase 1: 组件层次提取
- 识别 uvm_component 派生类
- 提取 type_id::create 调用
- 构建父子层次

### Phase 2: TLM 连接提取
- 识别 connect_phase 中的 .connect() 调用
- 提取端口路径

### Phase 3: Config/Factory/Sequence
- uvm_config_db set/get
- factory override
- default_sequence 注册
