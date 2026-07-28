# 开发纪律：基础组件必须彻底修复 (No Known-Limitations Discipline)

> **生效日期**: 2026-07-15
> **触发事件**: `_handle_normal_assign` 中 ternary 分支的 localparam 泄漏
> **签署人**: 方豆 + QClaw Agent

---

## 一、原则陈述

**基础组件的修复不接受 "Known Limitation"**。

具体含义:

1. **一旦发现 bug → 必须彻底修** — 不是 "加一行注释说以后再修"
2. **测试不能故意失败** — 不能写一个 `test_X_documented_leak` 来"记录"已知 bug
3. **修复分支完整** — 不能只修 `_create_always_edges` 而忽视 `_handle_normal_assign`
4. **修复所有等价入口** — 同一逻辑必须出现在所有路径上

---

## 二、禁止的反模式

### ❌ 反模式 1: "已知限制" 测试

```python
# 🚫 禁止 — 把 bug 当作 acceptance criteria
def test_ternary_localparam_documented_leak(self):
    """Documenting: continuous assign ternary localparam currently leaks."""
    drivers = _fanin_drivers(tracer, "ternary.result")
    # Document current behavior: S0 and S1 leak
    assert "ternary.S0" in drivers  # 🚫 故意让 bug 通过!
```

**为什么禁止**: 这种测试**降低了修复的优先级**。一旦有了 "documented leak" 的测试, 后续开发会把它当成"已知", 不再尝试修复。

### ❌ 反模式 2: 部分修复

```python
# 🚫 禁止 — 只修一条路径
def _expr_is_compile_time(self, ast_node, module=None):
    if hasattr(ast_node, "symbol"):  # 路径 1
        ...
    # 🚫 漏掉路径 2: Syntax AST 的 IdentifierNameSyntax
    if hasattr(ast_node, "identifier"):  # 后加的 path 2
        ...
```

**为什么禁止**: 同一语义问题在不同 AST 节点类型下都可能出现。只修一条路径等于没修。

### ❌ 反模式 3: "以后再修" 注释

```python
# 🚫 禁止 — 注释代替修复
# TODO: Continuous assign ternary localparam should be filtered
# See sim/tests/unit/test_localparam_driver_filter.py::test_ternary_localparam_documented_leak
```

**为什么禁止**: TODO 注释是给**未来**的人的, 不是给**当前**的 release 的。

---

## 三、强制规范

### ✅ 规范 1: 修复前必须写"未修复"测试

在写 fix **之前**, 写一个明确失败的测试:

```python
def test_ternary_localparam_excluded(self):
    """Localparam in continuous assign ternary must NOT appear as driver."""
    drivers = _fanin_drivers(tracer, "ternary.result")
    assert "ternary.S0" not in drivers  # 会失败, 证明 bug 存在
```

**目的**: 锁定 bug, 防止"假装修好了"。

### ✅ 规范 2: 修复后必须所有路径通过

修复代码后:

1. ✅ 新写的测试通过 (证明 bug 修好)
2. ✅ 同一组件的所有 regression test 通过 (证明没有引入新 bug)
3. ✅ 所有调用方的 path 都验证过

### ✅ 规范 3: 不能新增 "Known Limitations" 测试

如果发现某个 case 没被修复:

1. **修复它**, 然后**让它 pass** (体现"已修")
2. **不修复**, 但是**删掉这个 case 的测试** (不放进 test suite)
3. ❌ **不修复, 但写测试说"将来会修"** — 这是最糟的选择

---

## 四、例外情况 (有限的)

### 例外 1: 性能优化遗留

如果某个修复因为性能原因故意保留 (e.g. "这个 case 跑 10x 慢"), 应该:

1. 在代码注释里写明性能数据
2. 在 commit message 里解释 trade-off
3. 加 `issue/` 跟踪,但**不在测试里"document"**它的失败

### 例外 2: 第三方依赖限制

如果 bug 由 pyslang 的某个限制引起,**当前版本无解**:

1. 在 `KNOWN_ISSUES.md` 记录 (不是测试)
2. 在 `requirements.txt` 注释期望修复的 pyslang 版本
3. 写一个 `@pytest.mark.skip(reason="pyslang issue #N")` 而不是让它 fail

### 例外 3: 真正的"做不到"

如果一个 case 在硬件上**逻辑上就是做不到** (e.g. infinite loop 终止):

1. 这种 case 不应该出现在 trace_fanin 的输入
2. 用 `pytest.raises` 验证它**抛错**, 不是验证它**返回错误结果**

---

## 五、强制执行

### 5.1 CI 检查

新增 `.github/workflows/check_fix_completeness.py`:

```python
def test_no_documented_known_limitations():
    """扫描所有 test, 确保没有 'documented' / 'known' / 'limitation' 字样的失败断言。"""
    import re
    for test_file in Path("sim/tests").rglob("test_*.py"):
        content = test_file.read_text()
        # 匹配 "assert ... in drivers" 模式 (可能是有意让 bug 通过)
        for match in re.finditer(r'assert\s+["\'](.+?)["\']\s+(?:not\s+)?in\s+drivers', content):
            sig_name = match.group(1)
            # 如果是 test_*.py 中的 assert, 且文件提到 "known" / "limitation" / "leak"
            if re.search(r'known|limitation|leak|document', content, re.IGNORECASE):
                if re.search(r'known limitation|documented leak', content, re.IGNORECASE):
                    raise AssertionError(
                        f"{test_file} contains 'documented known limitation' - "
                        f"this violates FIX_COMPLETENESS discipline. "
                        f"Either FIX the bug or DELETE this test."
                    )
```

### 5.2 PR Review 检查清单

每个 PR 必须回答:

- [ ] 新增的 test 都 pass (不是 `assert X in Y` 让 bug 通过)
- [ ] 修复的代码覆盖了**所有等价入口**
- [ ] 没有新增 "Known Limitations" 测试
- [ ] 如果有 TODO, 关联了具体的 issue tracker

---

## 六、违反示例 (历史教训)

### 违反案例 1: Fix F.5 + ternary leak

**时间**: 2026-07-14 → 2026-07-15
**违反方式**: 写了 `test_ternary_localparam_documented_leak` 来"记录" ternary 路径的 bug
**后果**: 用户 (方豆) 立即指出 "基础组件要足够 stable, 不可妥协"
**修复**: 删除该测试, 修 ternary 路径 (comming soon)

---

## 七、签字

| 角色 | 承诺 |
|------|------|
| **方豆** | "基础组件要足够 stable, 不可妥协" |
| **QClaw Agent** | 修复基础组件前先写"未修复"测试, 修完不接受任何残留 bug |
