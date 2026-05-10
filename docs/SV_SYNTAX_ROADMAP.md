# SV Query 语法扩展路线图

**创建日期:** 2026-05-10  
**最后更新:** 2026-05-10  
**状态:** 规划中

---

## 项目当前状态

### 已支持语法

| 类别 | 语法 |
|------|------|
| 模块 | module 定义/例化 |
| 端口 | input/output/inout 声明 |
| 类型 | wire/reg/logic |
| 赋值 | assign 语句 |
| 过程块 | always_ff/always_comb/always_latch |
| 连接 | 命名/位置端口连接 |
| 生成 | generate for/if/case 块 |
| 参数 | parameterized modules |

**测试覆盖:** 485 tests passed

---

## 语法扩展计划

### P0 - 核心必需

#### 1. Interface 点号访问
- **目标:** 支持 `ifc.data` 信号追踪
- **难度:** 中
- **依赖:** 无
- **测试文件:** `test_interface.py`
- **状态:** 未开始

#### 2. Generate if/else 块
- **目标:** 支持条件 generate 块
- **难度:** 低
- **依赖:** 现有 generate for 实现
- **测试文件:** `test_generate_if.py`
- **状态:** 部分支持 (需完善)

#### 3. Modport 方向解析
- **目标:** 解析 `modport.master/slave` 方向
- **难度:** 中
- **依赖:** Interface 支持
- **测试文件:** `test_modport.py`
- **状态:** 未开始

---

### P1 - 重要功能

#### 4. Clocking Block
- **目标:** 支持 `@clk` 同步接口
- **难度:** 高
- **依赖:** Interface
- **测试文件:** `test_clock_block.py`
- **状态:** 未开始

#### 5. Package/import 处理
- **目标:** 支持 `pkg::symbol` 跨文件解析
- **难度:** 高
- **依赖:** 跨文件解析能力
- **测试文件:** `test_package.py`
- **状态:** 未开始

#### 6. Virtual Interface
- **目标:** 支持 `virtual interface` 处理
- **难度:** 高
- **依赖:** Interface + Variable 追踪
- **测试文件:** `test_virt_if.py`
- **状态:** 未开始

---

### P2 - 高级特性

| 语法 | 目标 | 难度 | 依赖 | 状态 |
|------|------|------|------|------|
| Covergroup | 覆盖率收集 | 高 | 无 | 未开始 |
| SVA Property/Sequence | 断言验证 | 高 | 无 | 未开始 |
| Class/OOP | class 定义和继承 | 高 | Package | 未开始 |
| Randsequence | 随机生成 | 高 | 无 | 未开始 |

---

## 开发顺序建议

```
P0 (核心)
  ├─ 1. Interface 点号访问
  ├─ 2. Generate if/else
  └─ 3. Modport 方向

P1 (重要)
  ├─ 4. Clocking Block
  ├─ 5. Package/import
  └─ 6. Virtual Interface

P2 (高级)
  ├─ 7. Covergroup
  ├─ 8. SVA Property/Sequence
  ├─ 9. Class/OOP
  └─ 10. Randsequence
```

---

## 实现检查清单

### Interface 点号访问
- [ ] 解析 interface 定义
- [ ] 解析 interface 信号
- [ ] 建立 ifc.signal -> actual_signal 映射
- [ ] 添加测试用例

### Generate if/else
- [ ] 完善 generate if 块解析
- [ ] 处理条件分支
- [ ] 添加测试用例

### Modport 方向
- [ ] 解析 modport 声明
- [ ] 识别 master/slave/arbitration 方向
- [ ] 与 interface 信号关联
- [ ] 添加测试用例

---

## 备注

- P0 优先级: 直接影响核心验证流程
- P1 优先级: 复杂设计需要
- P2 优先级: 高级验证场景

---

*此文档将随着开发进展持续更新*
