#!/usr/bin/env python3
"""
Proof-of-Concept: Bypassing SemanticAdapter.get_assignments()
by walking the pyslang SyntaxTree directly.

Key insight:
  SemanticAdapter.get_assignments() uses the Semantic AST (RootSymbol),
  which swallows `$signed(g ? x0 : x1)` into a ConversionSymbol node.
  The raw SyntaxTree (from Compilation.getSyntaxTrees()) preserves
  ContinuousAssignSyntax nodes for ALL continuous assigns, including
  those whose RHS is wrapped in system-call invocations.

How to access the Compilation:
  - UnifiedTracer:  tracer._get_compiler().get_compilation()
  - SemanticAdapter: adapter._compiler.get_compilation()
  - SVCompiler:      compiler.get_compilation()

File: sim/tests/fixtures/golden_mini/nested_mux_demo.sv
"""

import sys
sys.path.insert(0, '/Users/fundou/my_dv_proj/slang/build/bindings')

from trace.core.compiler import SVCompiler


# ---------------------------------------------------------------------------
# Step 1: Set up the compiler (same path as teach command)
# ---------------------------------------------------------------------------
print("=" * 70)
print("STEP 1 — Compiler / SemanticAdapter initialization path")
print("=" * 70)

with open('sim/tests/fixtures/golden_mini/nested_mux_demo.sv') as f:
    source = f.read()

# This is exactly what UnifiedTracer.__init__ → _build_tracer does:
#   tracer = _build_tracer(file=Path(...), strict=False, ...)
#   comp = tracer._get_compiler().get_compilation()
compiler = SVCompiler({'nested_mux_demo.sv': source}, strict=False)
compiler._do_compile()        # same as tracer._get_compiler() lazily does
comp = compiler.get_compilation()

print(f"comp:                     {comp}")
print(f"comp type:                {type(comp).__name__}")
print(f"comp.__class__.__module__: {type(comp).__module__}")

# Also verify we can get it from a SemanticAdapter:
from trace.core.semantic_adapter import SemanticAdapter
root = compiler.get_root()
adapter = SemanticAdapter(root, compiler)
print(f"\nadapter.root:             {adapter.root}")
print(f"adapter._compiler:        {adapter._compiler}")
print(f"adapter._compiler.get_compilation(): {adapter._compiler.get_compilation()}")


# ---------------------------------------------------------------------------
# Step 2: Get raw SyntaxTrees from the Compilation
# ---------------------------------------------------------------------------
print("\n" + "=" * 70)
print("STEP 2 — Raw SyntaxTree access via Compilation.getSyntaxTrees()")
print("=" * 70)

trees = comp.getSyntaxTrees()
print(f"Number of SyntaxTrees: {len(trees)}")
for i, t in enumerate(trees):
    root_node = t.root
    print(f"  Tree[{i}]: module={getattr(root_node, 'name', 'N/A')}  "
          f"kind={root_node.kind}  type={type(root_node).__name__}")


# ---------------------------------------------------------------------------
# Step 3: Walk the SyntaxTree to find ALL ContinuousAssign nodes
# ---------------------------------------------------------------------------
print("\n" + "=" * 70)
print("STEP 3 — Walking SyntaxTree to find ALL ContinuousAssignSyntax nodes")
print("=" * 70)

def find_continuous_assigns(node):
    """Walk a pyslang SyntaxNode and return all ContinuousAssignSyntax nodes."""
    results = []
    def visitor(n):
        k = getattr(n, 'kind', None)
        if k and 'ContinuousAssign' in str(k):
            results.append(n)
    node.visit(visitor)
    return results

tree_root = trees[0].root
all_cas = find_continuous_assigns(tree_root)
print(f"Total ContinuousAssignSyntax nodes found: {len(all_cas)}")


# ---------------------------------------------------------------------------
# Step 4: Print lhs, rhs kind, and rhs text for every ContinuousAssign
# ---------------------------------------------------------------------------
print("\n" + "=" * 70)
print("STEP 4 — Details for every ContinuousAssign in nested_mux_demo.sv")
print("=" * 70)

for i, ca in enumerate(all_cas):
    for assignment in ca.assignments:
        lhs = assignment.left
        rhs = assignment.right
        lhs_text = str(lhs).strip()
        rhs_kind = str(rhs.kind)
        rhs_text = str(rhs).strip()
        print(f"\n[Assign {i}]")
        print(f"  LHS:       {lhs_text}")
        print(f"  RHS kind:  {rhs_kind}")
        print(f"  RHS text:  {rhs_text}")


# ---------------------------------------------------------------------------
# Step 5: Verify y_inside_func_call = $signed(g ? x0 : x1) is found
# ---------------------------------------------------------------------------
print("\n" + "=" * 70)
print("STEP 5 — Verify target assignment is found")
print("=" * 70)

TARGET = 'y_inside_func_call'
for i, ca in enumerate(all_cas):
    for assignment in ca.assignments:
        lhs_text = str(assignment.left).strip()
        if TARGET in lhs_text:
            rhs = assignment.right
            print(f"OK: Found target assignment!")
            print(f"  LHS:      {lhs_text}")
            print(f"  RHS:      {rhs}")
            print(f"  RHS kind: {rhs.kind}")
            print(f"  RHS type: {type(rhs).__name__}")


# ---------------------------------------------------------------------------
# Step 6: Extract signals from $signed(g ? x0 : x1)
#          Unwrapping path:
#            ContinuousAssignSyntax.assignments[0]
#              → BinaryExpressionSyntax
#                .right = InvocationExpressionSyntax  ($signed(...))
#                  .left  = '$signed'  (Token, the callee)
#                  .arguments[1] = OrderedArgumentSyntax
#                    .expr = SimplePropertyExprSyntax
#                      .expr = SimpleSequenceExprSyntax
#                        .expr = ConditionalExpressionSyntax
#                          .predicate → g   (selector)
#                          .left     → x0  (true branch)
#                          .right    → x1  (false branch)
# ---------------------------------------------------------------------------
print("\n" + "=" * 70)
print("STEP 6 — Extracting signals: $signed(g ? x0 : x1)")
print("=" * 70)

def extract_signals_from_invocation(rhs_node):
    """
    Given an InvocationExpressionSyntax node (e.g. $signed(g ? x0 : x1)),
    recursively unwrap through SimplePropertyExpr → SimpleSequenceExpr →
    ConditionalExpression and return (callee, selector, true_val, false_val).

    pyslang SyntaxTree layout for `$signed(g ? x0 : x1)`:
      InvocationExpressionSyntax
        .left   = '$signed'  (Token, the callee)
        .arguments = (g ? x0 : x1)
          OrderedArgumentSyntax[1].expr
            → SimplePropertyExprSyntax.expr
              → SimpleSequenceExprSyntax.expr
                → ConditionalExpressionSyntax
                    .predicate → g
                    .left     → x0
                    .right    → x1
    """
    # Callee is in .left for InvocationExpressionSyntax
    callee = str(rhs_node.left).strip() if hasattr(rhs_node, 'left') else 'unknown'

    # Walk arguments, skipping Token nodes (OpenParenthesis, etc.)
    for arg in rhs_node.arguments:
        kind = getattr(arg, 'kind', None)
        if kind is not None and 'Token' in str(kind):
            continue
        if not hasattr(arg, 'expr') or arg.expr is None:
            continue

        inner = arg.expr
        # SimplePropertyExprSyntax.expr → SimpleSequenceExprSyntax
        if not hasattr(inner, 'expr') or inner.expr is None:
            continue
        seq = inner.expr

        # SimpleSequenceExprSyntax.expr → ConditionalExpressionSyntax
        if not hasattr(seq, 'expr') or seq.expr is None:
            continue
        cond = seq.expr

        # ConditionalExpressionSyntax: .predicate, .left, .right
        if hasattr(cond, 'predicate'):
            return callee, str(cond.predicate).strip(), \
                   str(cond.left).strip(),  str(cond.right).strip()

    return callee, None, None, None


for i, ca in enumerate(all_cas):
    for assignment in ca.assignments:
        lhs_text = str(assignment.left).strip()
        if TARGET not in lhs_text:
            continue
        rhs = assignment.right

        print(f"Assignment: {lhs_text} = {rhs}")

        # The RHS of y_inside_func_call is an InvocationExpression ($signed)
        if hasattr(rhs, 'kind') and 'Invocation' in str(rhs.kind):
            callee, selector, true_val, false_val = extract_signals_from_invocation(rhs)
            print(f"\n  Unwrapped invocation:")
            print(f"    Callee (system func):  {callee}")
            print(f"    Selector  (condition):  {selector}")
            print(f"    True value  (g=1):     {true_val}")
            print(f"    False value (g=0):     {false_val}")

            # Verify
            assert selector == 'g',    f"Expected selector='g', got '{selector}'"
            assert true_val == 'x0',   f"Expected true_val='x0', got '{true_val}'"
            assert false_val == 'x1',  f"Expected false_val='x1', got '{false_val}'"
            print(f"\n  [OK] All assertions passed — signals correctly extracted!")


# ---------------------------------------------------------------------------
# Bonus: Generic recursive ConditionalExpression unwrapper
# ---------------------------------------------------------------------------
print("\n" + "=" * 70)
print("BONUS — Generic recursive ConditionalExpression unwrapper")
print("=" * 70)

def find_conditional_exprs(node):
    """Find all ConditionalExpressionSyntax nodes inside a syntax tree."""
    results = []
    def visitor(n):
        if 'ConditionalExpression' in str(getattr(n, 'kind', '')):
            results.append(n)
    node.visit(visitor)
    return results


for i, ca in enumerate(all_cas):
    for assignment in ca.assignments:
        rhs = assignment.right

        # Find all ConditionalExpression nodes inside this RHS
        conds = find_conditional_exprs(rhs)
        if not conds:
            continue

        print(f"\n  Conditional expressions inside '{assignment.left}':")
        for j, cond in enumerate(conds):
            print(f"    [{j}] selector={cond.predicate}  true={cond.left}  false={cond.right}")


print("\n" + "=" * 70)
print("COMPLETE — Syntax tree walk successfully bypasses get_assignments()")
print("=" * 70)
