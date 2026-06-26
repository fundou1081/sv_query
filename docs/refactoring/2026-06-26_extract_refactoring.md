# DriverExtractor.extract() 拆解详细 Plan (2026-06-26)

## 当前状态

`DriverExtractor.extract()` (L331-1147, 817 lines) 是**单 method, 9 个 linear phase**:
- 大量 duplicate code (TraceNode/TraceEdge 创建在 6+ 处复制)
- 1 个 200 行 closure (`find_invocations`)
- 难 debug, 改 1 行要 5 分钟找上下文

## 拆解目标

`extract()` 30 行 dispatch, 9 个 private method 各自 <150 行, 1 个 closure 变 public method.

---

## Phase 1-7 实际范围 (从代码分析得出)

| Phase | L range | 行数 | 职责 |
|-------|---------|------|------|
| 1. port_nodes | 338-396 | 59 | 创建 PORT_IN/OUT/INOUT TraceNode |
| 2. var_nodes | 397-426 | 30 | 创建非端口 SIGNAL TraceNode |
| 3. net_aliases | 427-479 | 53 | alias 语句: source → target DRIVER 边 |
| 4. net_decls | 480-518 | 39 | wire X = expr; 创 SIGNAL + DRIVER 边 |
| 5. assignments | 519-884 | 366 | 5a 5b 5c 5d 4 sub-phase |
| 5a. assign_concat | 519-619 | 101 | LHS/RHS Concatenation 处理 |
| 5b. assign_call | 620-649 | 30 | CallExpression 直接分发 _handle_invocation |
| 5c. assign_find_invocations | 650-700 | 51 | find_invocations closure (Binary+Invocation) |
| 5d. assign_normal | 701-884 | 184 | 普通 parse + ScopedName + 三元 + edges |
| 6. always_blocks | 885-1129 | 245 | 6a 6b 2 sub-phase |
| 6a. always_stmts | 885-947 | 63 | collect stmts + Invocation dispatch |
| 6b. always_assign | 948-1129 | 182 | 块内赋值 + clock/reset edges |
| 7. post_process | 1130-1147 | 18 | 给 condition_ast 填 source_location |

**共 9 个 phase (1-7) + 6 个 sub-phase (5a-6b)**

## 抽 method 计划 (Level 1)

```python
def extract(self) -> ExtractorResult:
    """主入口: 7 phase 串行"""
    result = ExtractorResult()
    self._current_module = None
    self._current_source_file = ""

    for module in self.adapter.get_modules():
        module_name = self.adapter.get_module_name(module)
        self._current_module = module
        self._current_source_file, src_line, _, _ = self.adapter.get_source_location(module)

        # Phase 1-4: TraceNode creation
        self._create_port_nodes(module, result, module_name)
        port_names = self._collect_port_names(module)
        self._create_var_nodes(module, result, module_name, port_names)
        self._create_net_alias_edges(module, result, module_name)
        self._create_net_decl_edges(module, result, module_name, port_names)

        # Phase 5: Continuous assignments
        self._create_assign_edges(module, result, module_name)

        # Phase 6: Always blocks
        self._create_always_edges(module, result, module_name)

    # Phase 7: Post-process
    self._post_process_source_locations(result)
    return result
```

**7 个新 private method**, 每个 < 250 行 (含 sub-phase inline).

## 抽 method 计划 (Level 2, 进一步)

如果 Level 1 不够, 把 5d (assign_normal 184 行) 跟 6b (always_assign 182 行) 进一步拆:

```python
def _create_assign_edges(self, module, result, module_name):
    for assign in self.adapter.get_assignments(module):
        raw_lhs, raw_rhs = self._extract_assign_lr(assign)
        if not raw_lhs or not raw_rhs:
            continue
        if self._is_concatenation_assign(raw_lhs, raw_rhs):
            self._handle_concatenation_assign(...)
            continue
        if self._is_call_expression(raw_rhs):
            self._handle_call_assign(...)
            continue
        invocations = self._find_invocations(raw_rhs)  # 抽 closure
        if invocations:
            self._handle_invocation_assign(...)
            continue
        self._handle_normal_assign(...)  # 184 行 — 内部含 4 sub-method
```

`find_invocations` closure → 抽 `_find_invocations(expr) -> list` public method, 可单测.

`_handle_normal_assign` 184 行可再拆:
- `_extract_scoped_name_hierarchy(lhs, module_name, result)` 
- `_extract_ternary_signals(rhs_expr, module_name, result)`
- `_make_signal_node_if_missing(name, module_name, result)`
- `_make_edge_from_signal(signal, dst_id, ...)`

## 收益预估

| 维度 | Before | After |
|------|--------|-------|
| extract() 行数 | 817 | 30 |
| 顶层 method | 1 | 8 (1 extract + 7 phase) |
| find_invocations | 200 行 closure | public method (可单测) |
| 改 1 行平均时间 | 5 min | 1 min |
| 单测能力 | extract 整段测 | 7 phase 独立测 |
| 重复代码 | TraceNode/Edge 6+ 处 | helper 化 |

## 风险评估

🟢 LOW:
- **行为等价**: 抽 method 不改逻辑, 只搬代码
- **测试覆盖**: 7 unit test 验证 extract 行为, 跑确认 0 regression
- **可分阶段**: Level 1 跟 Level 2 可拆 2-3 PR, 每次 PR 跑测试

## 实施步骤 (1-2 周)

1. **Day 1-2**: 抽 _collect_port_names, _create_port_nodes, _create_var_nodes (phase 1-2, 风险最低)
2. **Day 3-4**: 抽 _create_net_alias_edges, _create_net_decl_edges (phase 3-4, 简单)
3. **Day 5-7**: 抽 _create_assign_edges + 4 sub-method (phase 5, 风险中, 最大块)
4. **Day 8-9**: 抽 _create_always_edges + 2 sub-method (phase 6, 风险中)
5. **Day 10**: 抽 _post_process_source_locations (phase 7, 简单)
6. **Day 11-14**: 测试 + 跑 7 test 验证 + commit

每步后跑 test, 0 regression 才能下一步.

## 配套

- **同步拆 _handle_invocation 462 行**: 抽 4 个 sub-method (args_parse, task_search, param_map, function_handle)
  - Day 12-14 并行做
- **同步抽 helper**: TraceNode/Edge 创建在 6+ 处重复, 抽 _make_node(name, kind, module_name, **kwargs) 跟 _make_edge(src, dst, kind, **kwargs)
  - 1-2 天, 跟 phase 5 同步做
