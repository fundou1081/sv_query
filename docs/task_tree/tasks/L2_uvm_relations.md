# Task: UVM sequence/factory 静态关系（P65）

**状态**: 进行中
**目标**: 在 `class --relations` 上补 UVM 特有静态关系，不解析运行时 factory/override。

## 交付

- role：sequence / sequence_item / component / object（按 UVM 祖先）
- factory registration：`uvm_*_utils` 宏
- factory_creates：`type_id::create` / `factory.create_by_name`
- sequence_calls：`uvm_do*` / start_item / finish_item
- p_sequencer：`uvm_declare_p_sequencer`
- tests/contract/docs

## 边界

- 宏/调用从类源码文本提取（preprocessor 会从 semantic syntax 去掉宏）；
- 不做 factory override / config_db / phase 执行；
- 不做 UVM package 依赖分析。
