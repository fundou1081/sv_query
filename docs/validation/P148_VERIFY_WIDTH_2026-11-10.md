# P148 verify consistency: single-bit width

**日期**: 2026-11-10
**来源**: P147 SPI_HOST worker 发现 width mismatch 728 条

---

## 1. 根因

`verify consistency --checks bit` 对 bit-select 节点使用：

```python
nbits = abs(width_msb - width_lsb) + 1
```

但图里单 bit 节点可能保存 `(1, 0)` 默认 sentinel，实际是 1 bit；
这会把 `cfg_en[4]` / `test[5]` 等节点误判为 2 bit。

## 2. 修复

对以下情况用显式 span：

```text
bit_range 是单 bit（不含 ":"）
或 parent_bit_start == parent_bit_end
→ nbits = 1
```

其余多 bit 仍用 width 公式。

## 3. SPI_HOST 实测

```text
before: 718 bit violations
after:  171 bit violations
```

减少 547 条 false `width_mismatch`；剩余 `id_parent_mismatch` 已由 P150 修复。

Connection check：

```text
pass, 0 violations / 1734 checked
```

## 4. 测试

```text
test_verify_bit_width.py: 2 passed
```

## 5. 边界

- 不把 `(1,0)` 一律当 1 bit；真实多 bit 仍检查 width；
- `verify consistency --from-snapshot` 仍不可用：snapshot 不含 MIG，
  connection check 无法执行；
- 剩余 `id_parent_mismatch` 另立任务。
