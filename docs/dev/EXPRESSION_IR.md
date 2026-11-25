# Expression IR — typed semantic expression DAG (P198)

> **Status**: implementation contract; P198.1 in progress.
> **Problem**: expressions are flattened into `SignalSource` leaf summaries and
> `expression` strings. Composite LHS/RHS, concatenation layout, X/Z literals,
> and width/signedness cannot be represented reliably.
> **Rule**: semantic AST is the only source; no expression-text regex in the
> query/bit-mapping path.

## 1. Goals

- Preserve the full typed expression tree for both assignment sides.
- Preserve four-state literals (X/Z) and explicit unknown reasons.
- Represent width, signedness, casts, concat, slices, shifts, ternary, calls.
- Make concat pairing bit-layout based, not leaf `zip`.
- Provide one canonical expression representation for query, cache, snapshot,
  viz, and const/function extraction.
- Keep old snapshots readable; missing IR is explicit `unknown`, not a silent
  text fallback.

## 2. Non-goals

- Do not evaluate runtime values.
- Do not replace graph nodes/edges; the IR is referenced by them.
- Do not reimplement pyslang parsing.
- Do not make syntax-token `ExpressionTree` the source of truth.
- Do not solve dynamic part-select/function inlining beyond explicit unknown.

## 3. Core data model

Module: `src/sv_query/trace/core/expression_ir.py`.

```python
@dataclass(frozen=True)
class Expr:
    op: str                         # SignalRef/Literal/Concat/Slice/...
    width: int | None = None
    signed: bool = False
    children: tuple["Expr", ...] = ()
    signal: str = ""               # SignalRef
    literal: str = ""              # canonical SVInt text, X/Z preserved
    bit_range: tuple[int, int] | None = None
    reason: str = ""               # Unknown/unsupported reason
    source_line: int = 0
```

`op` is a stable string (JSON-friendly). Allowed initial ops:

```text
SignalRef Literal Concat Slice ShiftLeft ShiftRight Add Sub Mul Div Mod
And Or Xor Not Neg Cast Ternary Call Unknown
```

`literal` is **text**, not int:

```text
4'b10x  stays 4'b10x
4'd2    stays 4'd2 (value available through a literal parser)
```

This prevents `SVInt -> int` from silently converting X/Z to 0.

```python
@dataclass(frozen=True)
class AssignmentExpr:
    lhs: Expr
    rhs: Expr
    condition: Expr | None = None
    assign_type: str = ""
```

An assignment always stores both sides. LHS may be `SignalRef`, `Concat`,
`Slice`, or `Unknown`; RHS is any expression.

## 4. Expression store / identity

Expressions are interned in an `ExpressionStore`:

```python
store.add(expr) -> "expr:ab12cd34"
store.get(expr_id) -> Expr
store.to_dict() / ExpressionStore.from_dict()
```

Identity is a SHA-256 of the canonical JSON of `Expr.to_dict()`, truncated to
16 hex chars. Identical subtrees share one id (DAG) in memory. **P198.1 uses an
inline tree wire format**; P198.3 must switch to flat `expr_id` child/root
references before IR is persisted. Until then this serialization duplicates
shared subtrees and must not be used as the final cache/snapshot schema.

`Expr.to_dict()` is canonical: sorted keys, tuple children serialized as lists,
no absolute paths. `from_dict()` is strict: unknown `op` or missing required
fields raise `ValueError`; it does not guess.

## 5. Semantic builder (P198.2)

Build with pyslang semantic AST, not syntax tokens:

| Semantic node | IR |
|---|---|
| `NamedValueExpression` | `SignalRef(signal=...)` |
| `IntegerLiteralExpression` | `Literal(literal=str(value))` |
| `BinaryExpression` | `Add/Sub/.../ShiftLeft/ShiftRight` with `left,right` |
| `UnaryExpression` | `Not/Neg` with operand |
| `ConversionExpression` | `Cast` with operand |
| `ConcatenationExpression` | `Concat(operands)` |
| `ConditionalExpression` | `Ternary(condition,true,false)` |
| `ElementSelectExpression` | `Slice` or `SignalRef` with bit range |
| `RangeSelectExpression` | `Slice(base, msb, lsb)` |
| `CallExpression` | `Call(name, args)`; bit mapping defaults unknown |

Width/signedness come from `expr.type.bitWidth` / `expr.type.isSigned` when
available; otherwise `width=None` and bit mapping must return unknown.

X/Z values are kept as `Literal` text. A literal is only usable for fixed bit
mapping when it is fully known; a helper may parse it with unknown detection.

## 6. Assignment storage and graph linkage (P198.3)

- `SignalGraph` gets `expression_store` and `assignments` maps.
- `TraceEdge` gets optional `expr_id` and `assignment_id`.
- One assignment is stored once; multiple leaf edges reference it.
- Edges keep current `source`/`expression` for display/backward compatibility.
- Old edges without `expr_id` are explicitly "no IR": bit mapping is `unknown`
  where IR is required, not a fallback to regex.
- Cache/snapshot schema version is bumped when IR is first persisted.

## 7. Concat bit layout (P198.4)

Do not `zip(lhs_leaves, rhs_leaves)`.

Flatten each side into ordered segments:

```python
Segment(lvalue: Expr, expr: Expr, width: int, offset: int)
```

Rules:

- LSB-first or MSB-first must be documented and consistent; use pyslang
  semantic operand order (MSB-first) and convert offsets explicitly.
- A concat segment may be a signal, slice, literal, or nested concat.
- Pair segments by overlapping absolute bit ranges.
- Width mismatch => explicit `unknown` with reason, unless a defined
  truncate/zero-extend rule applies.
- Dynamic selects => `unknown` for that segment.
- The resulting mapping is a list of `(lhs_bit_range, rhs_expr_bit)` records;
  query bit mapping consumes it.

## 8. Recursive bit mapping (P198.5)

`map_bit(expr, output_bit) -> BitMapResult`:

```text
SignalRef   -> that signal bit
Literal     -> known constant bit, or unknown if X/Z
Concat      -> select child by offset
Slice       -> adjust index
ShiftLeft/Right -> constant k: offset; dynamic: unknown
Cast        -> width/signedness rule
Ternary     -> union of branches; incomplete if condition unknown
Call        -> unknown unless semantic inline support exists
Unknown     -> unknown
```

`BitMapResult` carries `bits`, `unknown_reason`, and `complete`. A partial result
must never be reported as verified.

The existing `_expr_source_bits`/`_expr_dst_bits` become thin consumers of this
function; their per-op regex/branch logic is removed.

## 9. Migration phases

### P198.1 — model + store

- Add `Expr`, `AssignmentExpr`, `ExpressionStore`.
- Strict canonical serialization + interning.
- Unit tests for round-trip, X/Z preservation, nested concat/shift, unknown ops.
- No graph behavior change.

### P198.2 — semantic builder

- Build IR from pyslang semantic AST for the table in §5.
- Tests with actual semantic AST for shift, concat, cast, ternary, slice.
- Unsupported/call => `Unknown`, never guessed.

### P198.3 — graph/cache integration

- Add `expression_store`/`assignments` to `SignalGraph`.
- Annotate driver edges with `expr_id`.
- Cache/snapshot serialize/restore; old data => no IR.
- Round-trip and old-snapshot tests.

### P198.4 — concat layout

- Implement `flatten_concat` and segment pairing.
- Replace `_handle_concat_assign` leaf `zip`.
- Tests: both-side concat, different widths, nested concat, slices.
- No regression in graph baselines.

### P198.5 — shift query routing (scoped milestone)

- Route **shift** fanin/fanout bit mapping through `map_bit`.
- Dynamic shift/unknown literal/call => explicit unknown.
- If an edge has IR, an unmappable IR subtree must NOT fall back to legacy text.
- Slice/Cast/Ternary/Concat are enabled after parity; array-element endpoints
  remain on legacy. Source-text fallback removal for struct/memory is tracked
  separately.
- Shift parity tests CLI/session.

### P198.6 — completion

- **Target (not yet wired)**: make viz/expression_tree consume IR and make the
  syntax tree display-only.
- **Target (not yet wired)**: const/function extraction from IR. Deferred to
  P198.11+ with parity tests; the legacy syntax tree remains authoritative.
- Docs/CLAIMS/cache schema update.
- Worker-only review + re-audit for all P0/P1 findings.

## 9a. P198.6 status (viz bridge)

- `expression_ir_bridge.ir_to_tree()` and `collect_ir()` are available hooks
  for IR-backed visualization and const/call extraction.
- `DriverInfo.expression_ir` exposes the typed RHS snapshot alongside the legacy
  syntax `expression_tree`.
- **These hooks are not yet wired into production viz/const extraction.** The
  legacy syntax tree remains functionally live (including OP_TERNARY/OP_CASE
  emission) until P198.11+ performs the migration with parity tests.
- Cache wire schema is already 3.2; no new field was added here.

## 10. Acceptance tests

- `{a,b} = {c,d}` maps c→a, d→b.
- `{y, a[3:0]} = {b[7:4], c}` maps by bit offsets.
- Nested `{a,{b,c}}` layout correct.
- `a << 4'd2`, `a << 4'dx`, `a << b` behavior as P197.4.
- LHS/RHS trees both present and serialize.
- X/Z literal never becomes 0.
- Old snapshot without IR => explicit unknown.
- Cache round-trip preserves full tree/DAG.
- Revert of any stage fails its tests.
- Full gate + worker review green.

## 11. Risks

- Semantics of signed/width extension can differ from pyslang; use semantic type
  metadata, not guesses.
- Concat ordering is easy to reverse; tests must assert MSB/LSB explicitly.
- IR storage increases cache size; interning and one-copy-per-assignment bound it.
- Old snapshots must not silently use text fallback; explicit unknown is required.

## 9b. P198.9 parity status (scoped)

Broad Slice/Cast/Ternary/Concat IR routing is enabled after fixing source-name
normalization, relative-vs-absolute bit handling, and array-element guards.
Packed struct/memory cases that use array elements stay on the legacy path
explicitly. `Concat` bit routing is enabled in P198.11 after the direction-aware concat
layout and array-element guard proved parity.
